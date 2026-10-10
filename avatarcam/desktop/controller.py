from pathlib import Path
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, QTimer, Signal
from avatarcam.core.settings import Settings, APP_DIR
from avatarcam.desktop.performance import PRESETS, preset
from avatarcam.core.persistence import atomic_write_text
from avatarcam.core.model3d import import_model
from avatarcam.core.avatar_pack import import_avatar_pack, import_avatar_folder, copy_optimized_image, export_avatar_pack
from avatarcam.core.asset_store import AssetStore
from avatarcam.core.speech_detector import SpeechDetector
from avatarcam.core.timing import calibrate_noise
from avatarcam.audio.microphone import MicrophoneInput
from avatarcam.tracking.face import FaceTracker, FaceSmoother, empty_face

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


class StudioController(QObject):
    changed = Signal()
    notice = Signal(str)

    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        try:
            self.preferences = json.loads((APP_DIR/'studio-desktop.json').read_text(encoding='utf-8'))
            if not isinstance(self.preferences, dict): self.preferences = {}
        except (OSError, ValueError): self.preferences = {}
        from avatarcam.desktop.preferences import sanitize_preferences
        self.preferences = sanitize_preferences(self.preferences)
        self.mode = self.preferences.get('mode', '3D')
        if self.mode not in ('2D','3D'): self.mode = '3D'
        self.model_path = self.settings.avatar3d_path
        if not self.model_path or not Path(self.model_path).is_file():
            self.model_path = str(ASSETS/'AvatarHumanoide.vrm')
        self.settings.avatar3d_path = self.model_path
        self.store = AssetStore()
        demo = ASSETS/'StudioBot2D'
        self.sets = {'idle': self.settings.idle_images or [str(demo/'idle/001.png')],
                     'talk': self.settings.speaking_images or [str(demo/'talk/001.png')],
                     'blink': self.settings.blink_images or [str(demo/'blink/001.png')],
                     'pet': self.settings.pet_images or [], 'pet_talk': self.settings.pet_speaking_images or []}
        self.microphone = MicrophoneInput()
        self.microphone.device_index = self.settings.microphone_device
        self.microphone.speech_mode = self.settings.speech_mode
        self.speech = SpeechDetector(self.settings.sensitivity, self.settings.smoothing, self.settings.mouth_hold_ticks)
        self.output_active=False; self.render_active=True; self.paused=False; self.resume_inputs=(False,False)
        self.tracker = FaceTracker(); self.smoother = FaceSmoother(); self.face = empty_face()
        self.level = 0.; self.speaking = False; self.tracking_status = 'Câmera desligada'; self.error_seen = ''
        self.test_until = 0.; self.calibration_until = 0.; self.noise_samples = []
        self.camera_revision = 0; self.animation_epoch = time.time()
        self.library_revision=0
        self.manual_expression = None; self.renderer_report = {}; self.camera_frame = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ImportAvatar')
        self.jobs = []; self.closing = False; self.last_tick = time.monotonic()
        self.save_timer = QTimer(self); self.save_timer.setSingleShot(True); self.save_timer.timeout.connect(self.save)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(33)
        self.set_performance(self.preferences.get('performance','balanced'), save=False)

    @property
    def output_color(self):
        return {'green':'#00ff00','blue':'#0000ff','dark':'#202124'}.get(self.preferences.get('output_background'),'#00ff00')

    def set_performance(self, key, save=True):
        if not isinstance(key,str) or key not in PRESETS: key='balanced'
        self.preferences['performance']=key; self.performance=preset(key)
        self.settings.fps3d=self.performance['fps']
        self.timer.setInterval(round(1000/min(30,self.performance['fps'])))
        self.store.configure(self.performance['cache_mb']*1048576,self.performance['image_side'])
        self.tracker.configure(self.performance['tracking_fps'],self.performance['camera_width'],self.performance['camera_height'],self.tracker.preview_enabled)
        self.set_render_active(self.render_active)
        if save: self.defer_save(); self.changed.emit()

    def toggle_pause(self):
        if not self.paused:
            self.resume_inputs=(self.microphone.is_running,self.tracker.running)
            self.tracker.stop()
            try: self.microphone.stop()
            except Exception as error: self.notice.emit(str(error))
            self.face=empty_face(); self.level=0.; self.speaking=False
            self.paused=True; self.calibration_until=0.; self.noise_samples=[]; self.test_until=0.
            self.notice.emit('Pausado. Câmera e microfone desligados.')
        else:
            self.paused=False; audio,camera=self.resume_inputs
            if audio: self.toggle_microphone()
            if camera: self.toggle_tracking()
            self.notice.emit('Retomado.')
        self.set_render_active(self.render_active); self.changed.emit()

    def set_render_active(self, active):
        self.render_active=bool(active)
        self.timer.setInterval(round(1000/min(30,self.performance['fps'])) if active and not self.paused else 200)
        self.tracker.fps=self.performance['tracking_fps'] if active else 8

    def preference(self, key, default, low, high):
        value = self.preferences.get(key, default)
        return max(low, min(high, value)) if isinstance(value, (int,float)) and math.isfinite(value) else default

    def defer_save(self):
        self.save_timer.start(400)

    def save(self):
        self.preferences['mode'] = self.mode
        self.settings.avatar3d_path = self.model_path
        self.settings.idle_images = self.sets['idle']; self.settings.speaking_images = self.sets['talk']
        self.settings.blink_images = self.sets['blink']
        self.settings.pet_images = self.sets['pet']; self.settings.pet_speaking_images = self.sets['pet_talk']
        self.settings.save()
        atomic_write_text(APP_DIR/'studio-desktop.json', json.dumps(self.preferences, indent=2, ensure_ascii=False))

    def model_route(self):
        path = Path(self.model_path)
        if not path.is_file(): return ''
        stat = path.stat()
        return f'model/{stat.st_mtime_ns}-{stat.st_size}/{path.name}'

    @property
    def expression(self):
        if self.manual_expression: return self.manual_expression
        if self.face['detected']:
            if self.face['smile'] > .35: return 'happy'
            if self.face['frown'] > .35: return 'sad'
            if self.face['surprise'] > .5: return 'surprised'
        return 'neutral'

    def snapshot(self):
        return dict(model=self.model_route(), level=self.level, speaking=self.speaking,
                    microphone=self.microphone.is_running, expression=self.expression,
                    fps=self.performance['fps'], pixelRatio=self.performance['pixel_ratio'],
                    active=self.render_active, paused=self.paused, capture=self.output_active, background=self.output_color, rotate=self.settings.auto_rotate3d,
                    camera=self.settings.camera3d, cameraRevision=self.camera_revision,
                    animationEpoch=self.animation_epoch, face=self.face)

    def command(self, action, value=None):
        if action == 'camera':
            self.settings.camera3d = Settings.from_dict({'camera3d': value}).camera3d
        elif action == 'reset_camera':
            self.settings.camera3d = None; self.camera_revision += 1
        elif action == 'expression':
            if value not in ('auto','neutral','happy','angry','sad','relaxed','surprised'): return False
            self.manual_expression = None if value == 'auto' else value
        elif action == 'test':
            self.test_until = time.monotonic()+3
        elif action == 'microphone':
            self.toggle_microphone()
        else: return False
        self.defer_save(); self.changed.emit(); return True

    def switch_mode(self, mode):
        if mode in ('2D','3D'):
            self.mode = mode
            if mode=='3D': self.store.clear()
            self.renderer_report={}
            self.defer_save(); self.changed.emit()

    def toggle_microphone(self):
        self.paused=False
        self.set_render_active(self.render_active)
        try:
            if self.microphone.is_running: self.microphone.stop()
            else: self.microphone.start()
        except Exception as exc: self.notice.emit(str(exc))
        self.changed.emit()

    def toggle_tracking(self):
        self.paused=False
        self.set_render_active(self.render_active)
        if self.tracker.running:
            self.tracker.stop(); self.face = empty_face(); self.smoother = FaceSmoother()
        else:
            self.tracker.start(int(self.preference('camera_device',0,0,20)))
        self.changed.emit()

    def calibrate_face(self):
        self.notice.emit('Posição neutra calibrada.' if self.smoother.calibrate() else 'Ligue a câmera e posicione o rosto antes de calibrar.')

    def calibrate_audio(self):
        if not self.microphone.is_running:
            self.notice.emit('Ative o microfone antes de calibrar.'); return
        self.noise_samples = []; self.calibration_until = time.monotonic()+3
        self.notice.emit('Fique em silêncio por 3 segundos…')

    def submit(self, worker, success):
        if self.jobs:
            self.notice.emit('Aguarde a importação atual.'); return
        self.jobs.append((self.executor.submit(worker), success))
        self.notice.emit('Importando avatar…')

    def remember_avatar(self):
        entry=dict(mode=self.mode,name=Path(self.model_path).stem if self.mode=='3D' else self.preferences.get('avatar2d_name','Avatar 2D'))
        if self.mode=='3D': entry['path']=self.model_path
        else:
            entry['sets']={key:list(paths) for key,paths in self.sets.items() if not key.startswith('_')}
            entry['expressions']=dict(self.preferences.get('expressions2d',{}))
        recent=self.preferences.get('recent_avatars',[])
        if not isinstance(recent,list): recent=[]
        identity=entry.get('path') or entry.get('sets',{}).get('idle')
        recent=[old for old in recent if isinstance(old,dict) and (old.get('path') or old.get('sets',{}).get('idle'))!=identity]
        self.preferences['recent_avatars']=[entry]+recent[:11]
        self.library_revision+=1

    def load_recent(self, index):
        entries=self.preferences.get('recent_avatars',[])
        if not isinstance(index,int) or index<0 or index>=len(entries): return
        entry=entries[index]
        if entry.get('mode')=='3D':
            path=entry.get('path','')
            if Path(path).is_file(): self.use_model(path)
            else: self.notice.emit('Arquivo não encontrado. Importe o avatar novamente.')
        else:
            sets=entry.get('sets',{})
            if not sets.get('idle') or not all(Path(path).is_file() for path in sets['idle']):
                self.notice.emit('Imagens não encontradas. Importe o avatar novamente.'); return
            self.use_sets(sets)
            self.preferences['avatar2d_name']=entry.get('name','Avatar 2D')
            self.preferences['expressions2d']=entry.get('expressions',{})
            self.remember_avatar(); self.changed.emit(); self.defer_save()

    def use_model(self, path):
        self.model_path = path; self.settings.camera3d = None; self.camera_revision += 1
        self.switch_mode('3D'); self.remember_avatar(); self.notice.emit('Avatar 3D pronto na janela do app.')

    def import_3d(self, path):
        self.submit(lambda: import_model(path), self.use_model)

    def use_sets(self, sets):
        for key in self.sets: self.sets[key] = sets.get(key, [])
        self.preferences['expressions2d'] = {}
        self.preferences['avatar2d_name'] = 'Avatar 2D'
        self.store.clear(); self.switch_mode('2D'); self.remember_avatar()
        self.notice.emit('Avatar 2D pronto. Adicione imagens de fala e piscar se desejar.')

    def import_2d(self, paths, role='idle'):
        def copy_images():
            folder = APP_DIR/'images'; folder.mkdir(parents=True, exist_ok=True)
            result = []
            for source in paths:
                p = Path(source)
                with p.open('rb') as stream:
                    digest = hashlib.file_digest(stream,'sha256').hexdigest()[:16]
                target = folder/(digest+p.suffix.lower())
                if not target.exists(): copy_optimized_image(p, target)
                result.append(str(target))
            return result
        def success(result):
            if role == 'idle':
                self.sets['talk'] = []; self.sets['blink'] = []
                self.preferences['expressions2d'] = {}
                self.preferences['avatar2d_name'] = Path(paths[0]).stem if paths else 'Avatar 2D'
            self.sets[role] = result; self.store.clear(); self.switch_mode('2D'); self.remember_avatar()
            self.notice.emit('Imagens 2D importadas.')
        self.submit(copy_images, success)

    def import_folder(self, path):
        self.submit(lambda: import_avatar_folder(path, Path(path).name), self.use_sets)

    def import_pack(self, path):
        def success(result):
            if result['model_path']: self.use_model(result['model_path'])
            else: self.use_sets(result['sets'])
        self.submit(lambda: import_avatar_pack(path), success)

    def export_pack(self, path):
        model = self.model_path if self.mode == '3D' else ''
        sets = {} if self.mode == '3D' else dict(self.sets)
        self.submit(lambda: export_avatar_pack(path, 'Meu_avatar', sets, {'expression3d':self.expression}, model),
                    lambda _: self.notice.emit('Pacote salvo com sucesso.'))

    def tick(self):
        now = time.monotonic(); dt = min(.2, now-self.last_tick); self.last_tick = now
        raw = self.microphone.read_level()
        self.speech.sensitivity = self.settings.sensitivity; self.speech.smoothing = self.settings.smoothing
        state = self.speech.update(raw, self.microphone.voice_allowed)
        self.level, self.speaking = state.level, state.speaking
        if now < self.test_until and not self.paused: self.level = .7; self.speaking = True
        if self.calibration_until:
            self.noise_samples.append(raw)
            if now >= self.calibration_until:
                self.calibration_until = 0
                self.settings.noise_floor, self.settings.sensitivity = calibrate_noise(self.noise_samples)
                self.defer_save(); self.notice.emit('Microfone calibrado.')
        sample, self.camera_frame, self.tracking_status, error = self.tracker.latest()
        self.face = self.smoother.update(sample, dt, self.preference('face_smoothing',.55,.1,.9), self.preference('face_strength',1.,.2,2.))
        if error and error != self.error_seen: self.error_seen = error; self.notice.emit(error)
        if not error: self.error_seen = ''
        if self.microphone.is_running and now-self.microphone.last_audio_time > 3:
            try: self.microphone.stop()
            except Exception: pass
            self.notice.emit('Microfone desconectado. Selecione o dispositivo e ative novamente.')
        for future, success in list(self.jobs):
            if future.done():
                self.jobs.remove((future,success))
                try: success(future.result()); self.defer_save()
                except Exception as exc: self.notice.emit(f'Importação não concluída: {exc}')
        self.changed.emit()

    def close(self):
        if self.closing: return
        self.closing = True; self.timer.stop(); self.save_timer.stop(); self.tracker.stop()
        try: self.microphone.stop()
        except Exception: pass
        self.executor.shutdown(wait=True, cancel_futures=True); self.save()
