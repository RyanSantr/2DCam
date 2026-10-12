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
from avatarcam.core.image_sequence import image_paths
from avatarcam.core.speech_detector import SpeechDetector
from avatarcam.core.timing import calibrate_noise
from avatarcam.audio.microphone import MicrophoneInput
from avatarcam.tracking.face import FaceTracker, FaceSmoother, empty_face
from avatarcam.desktop.inputs import InputRecovery
from avatarcam.desktop.library import avatar_id, update_library, clean_name
from avatarcam.desktop.creative import History, AdaptiveQuality, GESTURES, expression_config, helpful_issues
from avatarcam.desktop.recovery import capture_state, apply_state, SessionRecovery
from avatarcam.desktop.motion import IdleMotion, MotionPreview
from avatarcam.core.avatar_config import motion_config

from avatarcam.desktop.resources import asset_directory, restore_builtin_paths
ASSETS = asset_directory()
PACK_SETTINGS = ('avatar_scale','avatar_offset_x','avatar_offset_y','avatar_rotation','animation_fps','camera3d',
                 'auto_rotate3d','pet_enabled','pet_size','pet_offset_x','pet_offset_y')


class StudioController(QObject):
    changed = Signal()
    notice = Signal(str)
    imported = Signal()

    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        from dataclasses import asdict
        self.settings = Settings.from_dict(restore_builtin_paths(asdict(self.settings), ASSETS))
        try:
            self.preferences = json.loads((APP_DIR/'studio-desktop.json').read_text(encoding='utf-8'))
            if not isinstance(self.preferences, dict): self.preferences = {}
        except (OSError, ValueError): self.preferences = {}
        from avatarcam.desktop.preferences import sanitize_preferences
        self.preferences = sanitize_preferences(restore_builtin_paths(self.preferences, ASSETS))
        self.mode = self.preferences.get('mode', '3D')
        if self.mode not in ('2D','3D','Live2D'): self.mode = '3D'
        self.model_path = self.settings.avatar3d_path
        if not self.model_path or not Path(self.model_path).is_file():
            self.model_path = str(ASSETS/'AvatarHumanoide.vrm')
        if self.mode == 'Live2D':
            from avatarcam.desktop.live2d import runtime_available
            if not runtime_available():
                self.mode = '3D'; self.model_path = str(ASSETS/'AvatarHumanoide.vrm')
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
        self.visual_face = empty_face(); self.motion_source = 'none'
        self.idle_motion = IdleMotion(); self.motion_preview = MotionPreview()
        self.smoother.neutral = dict(self.preferences['face_neutral'])
        self.level = 0.; self.speaking = False; self.tracking_status = 'Câmera desligada'; self.error_seen = ''
        self.test_until = 0.; self.calibration_until = 0.; self.noise_samples = []
        self.camera_revision = 0; self.animation_epoch = time.time()
        self.library_revision=0
        self.history = History(); self.adaptive = AdaptiveQuality(); self.tick_lag = 0.; self.quiet_since = None
        self.gesture = None; self.gesture_at = 0.; self.expression_preview = None
        self.recovery = SessionRecovery(APP_DIR); self.recovery_started = False
        self.spout_error = ''; self.transparent_active = False
        self.manual_expression = None; self.renderer_report = {}; self.camera_frame = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ImportAvatar')
        self.inputs = InputRecovery(self)
        self.jobs = []; self.closing = False; self.last_tick = time.monotonic()
        self.save_timer = QTimer(self); self.save_timer.setSingleShot(True); self.save_timer.timeout.connect(self.save)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(33)
        self.set_performance(self.preferences.get('performance','balanced'), save=False)

    @property
    def output_color(self):
        return {'green':'#00ff00','blue':'#0000ff','dark':'#202124'}.get(self.preferences.get('output_background'),'#00ff00')

    def set_performance(self, key, save=True):
        if not isinstance(key,str) or key not in (*PRESETS, 'auto'): key='balanced'
        self.preferences['performance']=key
        self.adaptive.reset()
        self.apply_performance('balanced' if key == 'auto' else key)
        if save: self.defer_save(); self.changed.emit()

    def apply_performance(self, key):
        self.performance=preset(key)
        self.settings.fps3d=self.performance['fps']
        self.timer.setInterval(round(1000/min(30,self.performance['fps'])))
        self.store.configure(self.performance['cache_mb']*1048576,self.performance['image_side'])
        self.tracker.configure(self.performance['tracking_fps'],self.performance['camera_width'],self.performance['camera_height'],self.tracker.preview_enabled)
        self.set_render_active(self.render_active)

    def adapt_performance(self, now):
        if self.preferences['performance'] != 'auto': return
        fps = self.renderer_report.get('fps') if self.mode != '2D' and self.renderer_report.get('loaded') else None
        key = self.adaptive.sample(now, fps, self.performance['fps'], self.tick_lag,
                                   self.render_active and not self.paused and (self.mode == '2D' or self.renderer_report.get('loaded', False)))
        if key:
            self.apply_performance(key); self.changed.emit()
            self.notice.emit('Desempenho automático: ' + self.performance['name'])

    @property
    def identity(self): return avatar_id(dict(mode=self.mode, path=self.model_path, sets=self.sets))

    @property
    def expression_mapping(self): return self.preferences['expression_profiles'].get(self.identity, {})

    def set_expression_mapping(self, mapping):
        self.record_change(); self.preferences['expression_profiles'][self.identity] = expression_config(mapping)
        self.preferences['expression_profiles'] = dict(list(self.preferences['expression_profiles'].items())[-48:])
        self.defer_save(); self.changed.emit()

    def record_change(self): self.history.push(capture_state(self))

    def travel_history(self, redo=False):
        old = capture_state(self)
        state = self.history.forward(old) if redo else self.history.back(old)
        if state is None: return False
        try: apply_state(self, state)
        except ValueError as error:
            # Mantém a operação no histórico se um arquivo ficou indisponível.
            if redo: self.history.undo.pop(); self.history.redo.append(state)
            else: self.history.redo.pop(); self.history.undo.append(state)
            self.notice.emit(str(error)); return False
        self.notice.emit('Alteração refeita.' if redo else 'Alteração desfeita.'); self.changed.emit(); return True

    def play_gesture(self, key):
        if key not in GESTURES or self.paused: return False
        if self.mode != '2D' and key not in self.renderer_report.get('gestures', []):
            self.notice.emit('Esta ação não está disponível neste personagem.'); return False
        self.gesture = key; self.gesture_at = time.monotonic(); self.changed.emit(); return True

    def gesture_state(self):
        progress = (time.monotonic() - self.gesture_at) / 2.5
        return dict(name=self.gesture, progress=progress) if self.gesture and 0 <= progress <= 1 else None

    def issues(self): return helpful_issues(self)

    def preview_motion(self, values=None, sequence=False):
        if self.paused or self.inputs.wanted['camera']:
            self.notice.emit('Retome o personagem e desligue o rastreamento para testar sem câmera.')
            return False
        self.motion_preview.start(values, time.monotonic(), sequence)
        self.update_motion(0., time.monotonic())
        self.changed.emit(); return True

    def stop_motion_preview(self):
        self.motion_preview.stop(); self.update_motion(0., time.monotonic()); self.changed.emit()

    def update_motion(self, dt, now):
        if self.paused: return
        if self.inputs.wanted['camera']: self.motion_preview.stop()
        preview = self.motion_preview.sample(now)
        if preview is not None:
            self.visual_face = preview; self.motion_source = 'preview'
        elif self.face['detected']:
            self.visual_face = dict(self.face); self.motion_source = 'camera'
        elif self.preferences['idle_motion']:
            self.visual_face = self.idle_motion.advance(dt if self.render_active else 0., self.preferences['idle_strength'], self.level, self.speaking)
            for key in ('yaw', 'pitch', 'roll', 'gazeX', 'gazeY'):
                limit = .8 if key in ('yaw', 'pitch', 'roll') else 1.
                self.visual_face[key] = max(-limit, min(limit, self.visual_face[key] + self.face[key]))
            self.motion_source = 'idle'
        else:
            self.visual_face = dict(self.face); self.motion_source = 'none'

    def start_recovery(self, restore=False):
        if restore and self.recovery.previous:
            try: apply_state(self, self.recovery.previous); self.notice.emit('Sessão recuperada. Entradas permanecem desligadas.')
            except ValueError as error: self.notice.emit(str(error))
        self.recovery_started = True; self.recovery.checkpoint(capture_state(self))

    def toggle_pause(self):
        self.motion_preview.stop()
        if not self.paused:
            self.resume_inputs=(self.inputs.wanted['audio'],self.inputs.wanted['camera'])
            self.inputs.request('audio',False); self.inputs.request('camera',False)
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
        self.remember_avatar()
        self.preferences['mode'] = self.mode
        self.settings.avatar3d_path = self.model_path
        self.settings.idle_images = self.sets['idle']; self.settings.speaking_images = self.sets['talk']
        self.settings.blink_images = self.sets['blink']
        self.settings.pet_images = self.sets['pet']; self.settings.pet_speaking_images = self.sets['pet_talk']
        self.settings.save()
        atomic_write_text(APP_DIR/'studio-desktop.json', json.dumps(self.preferences, indent=2, ensure_ascii=False))
        if self.recovery_started and not self.closing: self.recovery.checkpoint(capture_state(self))

    def model_route(self):
        path = Path(self.model_path)
        if not path.is_file(): return ''
        stat = path.stat()
        if self.mode == 'Live2D': return 'live2d/' + path.name
        return f'model/{stat.st_mtime_ns}-{stat.st_size}/{path.name}'

    @property
    def expression(self):
        face = self.visual_face if self.motion_source == 'preview' else self.face
        if self.motion_source != 'preview' and self.manual_expression: return self.manual_expression
        if face['detected']:
            if face['smile'] > .35: return 'happy'
            if face['frown'] > .35: return 'sad'
            if face['surprise'] > .5: return 'surprised'
        return 'neutral'

    def snapshot(self):
        return dict(model=self.model_route(), level=self.level, speaking=self.speaking,
                    microphone=self.microphone.is_running, expression=self.expression,
                    fps=self.performance['fps'], pixelRatio=self.performance['pixel_ratio'],
                    active=self.render_active, paused=self.paused, capture=self.output_active, background=self.output_color, rotate=self.settings.auto_rotate3d,
                    camera=self.settings.camera3d, cameraRevision=self.camera_revision,
                    animationEpoch=self.animation_epoch, face=self.visual_face, motionSource=self.motion_source, expressionMapping=self.expression_mapping,
                    expressionPreview=self.expression_preview, gesture=self.gesture_state(), kind=self.mode)

    def command(self, action, value=None):
        if action == 'camera':
            self.record_change()
            self.settings.camera3d = Settings.from_dict({'camera3d': value}).camera3d
        elif action == 'reset_camera':
            self.record_change()
            self.settings.camera3d = None; self.camera_revision += 1
        elif action == 'expression':
            if value not in ('auto','neutral','happy','angry','sad','relaxed','surprised'): return False
            self.manual_expression = None if value == 'auto' else value
        elif action == 'test':
            self.test_until = time.monotonic()+3
            self.changed.emit(); return True
        elif action == 'microphone':
            self.toggle_microphone()
            return True
        else: return False
        if action != 'expression': self.defer_save()
        self.changed.emit(); return True

    def switch_mode(self, mode):
        if mode in ('2D','3D','Live2D'):
            self.motion_preview.stop()
            changed = mode != self.mode
            self.mode = mode
            if mode!='2D': self.store.clear()
            if changed: self.renderer_report={}; self.gesture=None
            self.defer_save(); self.changed.emit()

    def toggle_microphone(self):
        self.paused=False
        self.set_render_active(self.render_active)
        self.inputs.request('audio', not self.inputs.wanted['audio'])
        self.changed.emit()

    def toggle_tracking(self):
        self.motion_preview.stop()
        self.paused=False
        self.set_render_active(self.render_active)
        self.inputs.request('camera', not self.inputs.wanted['camera'])
        if not self.inputs.wanted['camera']:
            self.face = empty_face(); self.smoother = FaceSmoother()
            self.smoother.neutral = dict(self.preferences['face_neutral'])
        self.changed.emit()

    def calibrate_face(self):
        if not self.smoother.values['detected']:
            self.notice.emit('Ligue a câmera e posicione o rosto antes de calibrar.'); return
        self.record_change(); self.smoother.calibrate()
        self.preferences['face_neutral'] = dict(self.smoother.neutral); self.remember_avatar(); self.defer_save()
        self.notice.emit('Posição neutra calibrada e salva para este personagem.')

    def calibrate_audio(self):
        if not self.microphone.is_running:
            self.notice.emit('Ative o microfone antes de calibrar.'); return
        self.record_change()
        self.noise_samples = []; self.calibration_until = time.monotonic()+3
        self.notice.emit('Fique em silêncio por 3 segundos…')

    def submit(self, worker, success, message='Importando avatar…'):
        if self.jobs:
            self.notice.emit('Aguarde a operação atual.'); return False
        self.jobs.append((self.executor.submit(worker), success))
        self.notice.emit(message)
        return True

    def avatar_name(self):
        current = dict(mode=self.mode, path=self.model_path, sets=self.sets)
        entry = next((entry for entry in self.preferences['avatar_library'] if avatar_id(entry) == avatar_id(current)), None)
        if entry and entry.get('renamed'): return entry['name']
        if self.mode=='2D': return self.preferences.get('avatar2d_name','Avatar 2D')
        name=Path(self.model_path).stem
        suffix=name.rsplit('_',1)[-1]
        if len(suffix)==12 and all(ch in '0123456789abcdef' for ch in suffix): name=name.rsplit('_',1)[0]
        return 'Avatar de exemplo' if name=='AvatarHumanoide' else name

    def remember_avatar(self):
        entry=dict(mode=self.mode,name=self.avatar_name())
        if self.mode!='2D': entry['path']=self.model_path
        else:
            entry['sets']={key:list(paths) for key,paths in self.sets.items() if not key.startswith('_')}
            entry['expressions']=dict(self.preferences.get('expressions2d',{}))
        entry['tuning'] = {key: getattr(self.settings, key) for key in (*PACK_SETTINGS, 'sensitivity', 'smoothing', 'noise_floor')}
        entry['tuning'].update(face_smoothing=self.preferences['face_smoothing'], face_strength=self.preferences['face_strength'], face_neutral=dict(self.preferences['face_neutral']))
        entry['tuning'].update(motion_config(self.preferences))
        recent=self.preferences.get('recent_avatars',[])
        if not isinstance(recent,list): recent=[]
        identity=entry.get('path') or entry.get('sets',{}).get('idle')
        recent=[old for old in recent if isinstance(old,dict) and (old.get('path') or old.get('sets',{}).get('idle'))!=identity]
        self.preferences['recent_avatars']=[entry]+recent[:11]
        self.preferences['avatar_library'] = update_library(self.preferences['avatar_library'], entry)
        self.library_revision+=1

    def edit_library(self, identity, name=None, favorite=None):
        entry = next((entry for entry in self.preferences['avatar_library'] if avatar_id(entry) == identity), None)
        if entry is None: return False
        if name is not None:
            name = clean_name(name)
            if not name: return False
            entry['name'] = name; entry['renamed'] = True
        if favorite is not None: entry['favorite'] = bool(favorite)
        self.library_revision += 1; self.defer_save(); self.changed.emit()
        return True

    def load_library(self, identity):
        entry = next((entry for entry in self.preferences['avatar_library'] if avatar_id(entry) == identity), None)
        if entry is not None: self.load_entry(entry)

    def load_recent(self, index):
        entries=self.preferences.get('recent_avatars',[])
        if not isinstance(index,int) or index<0 or index>=len(entries): return
        entry=entries[index]
        self.load_entry(entry)

    def load_entry(self, entry):
        tuning = entry.get('tuning', {})
        if entry.get('mode') in ('3D', 'Live2D'):
            path=entry.get('path','')
            if Path(path).is_file():
                if entry['mode'] == 'Live2D':
                    if not self.use_live2d(path): return
                else: self.use_model(path)
            else: self.notice.emit('Arquivo não encontrado. Importe o avatar novamente.'); return
        else:
            sets=entry.get('sets',{})
            if not sets.get('idle') or not all(Path(path).is_file() for path in sets['idle']):
                self.notice.emit('Imagens não encontradas. Importe o avatar novamente.'); return
            self.use_sets(sets)
            self.preferences['avatar2d_name']=entry.get('name','Avatar 2D')
            self.preferences['expressions2d']=entry.get('expressions',{})
            self.remember_avatar(); self.changed.emit(); self.defer_save()
        if isinstance(tuning, dict) and tuning:
            checked = Settings.from_dict(tuning)
            for key in (*PACK_SETTINGS, 'sensitivity', 'smoothing', 'noise_floor'):
                if key in tuning: setattr(self.settings, key, getattr(checked, key))
            from avatarcam.desktop.preferences import sanitize_preferences
            prefs = sanitize_preferences(tuning)
            for key in ('face_smoothing', 'face_strength', 'face_neutral', 'idle_motion', 'idle_strength'):
                if key in tuning: self.preferences[key] = prefs[key]
            self.smoother.neutral = dict(self.preferences['face_neutral'])
            self.camera_revision += 1; self.remember_avatar(); self.defer_save(); self.changed.emit()

    def use_model(self, path):
        self.motion_preview.stop()
        self.record_change()
        self.manual_expression=None
        self.renderer_report = {}
        self.model_path = path; self.settings.camera3d = None; self.camera_revision += 1
        self.switch_mode('3D'); self.remember_avatar(); self.notice.emit('Avatar 3D pronto na janela do app.')

    def import_3d(self, path):
        def success(result): self.use_model(result); self.imported.emit()
        self.submit(lambda: import_model(path), success)

    def use_live2d(self, path):
        from avatarcam.desktop.live2d import runtime_available
        if not runtime_available():
            self.notice.emit('Integração Live2D preparada. O Cubism Core licenciado ainda não está disponível nesta distribuição.'); return False
        self.record_change(); self.manual_expression = None; self.model_path = path
        self.settings.camera3d = None; self.camera_revision += 1
        self.switch_mode('Live2D'); self.remember_avatar(); return True

    def import_live2d(self, path):
        from avatarcam.desktop.live2d import import_live2d, runtime_available
        if not runtime_available():
            self.notice.emit('Live2D aguarda autorização de distribuição e instalação do Cubism Core.'); return False
        def success(result):
            if self.use_live2d(result): self.imported.emit()
        return self.submit(lambda: import_live2d(path), success)

    def use_sets(self, sets):
        self.record_change()
        self.manual_expression=None
        for key in self.sets: self.sets[key] = sets.get(key, [])
        self.preferences['expressions2d'] = {}
        self.preferences['avatar2d_name'] = 'Avatar 2D'
        self.store.clear(); self.switch_mode('2D'); self.remember_avatar()
        self.notice.emit('Avatar 2D pronto. Adicione imagens de fala e piscar se desejar.')

    def import_2d(self, paths, role='idle'):
        paths = image_paths(paths)
        budget, side = self.store.max_bytes, self.store.max_side
        def copy_images():
            if not paths: raise ValueError('Escolha imagens PNG, GIF ou WebP.')
            if len(paths) > 256: raise ValueError('Use até 256 arquivos por pose.')
            folder = APP_DIR/'images'; folder.mkdir(parents=True, exist_ok=True)
            result = []
            for source in paths:
                p = Path(source)
                with p.open('rb') as stream:
                    digest = hashlib.file_digest(stream,'sha256').hexdigest()[:16]
                target = folder/(digest+p.suffix.lower())
                if not target.exists(): copy_optimized_image(p, target)
                result.append(str(target))
            self.validate_sequences([result], budget, side)
            return result
        def success(result):
            self.record_change()
            if role == 'idle':
                self.sets['talk'] = []; self.sets['blink'] = []
                self.preferences['expressions2d'] = {}
                self.preferences['avatar2d_name'] = Path(paths[0]).stem if paths else 'Avatar 2D'
            self.sets[role] = result; self.store.clear(); self.switch_mode('2D'); self.remember_avatar()
            self.notice.emit('Imagens 2D importadas.')
            if role == 'idle': self.imported.emit()
        return self.submit(copy_images, success)

    @staticmethod
    def validate_sequences(groups, budget, side):
        store = AssetStore(); store.configure(budget, side)
        for paths in groups:
            if paths: store.load(paths)
        store.clear()

    def import_folder(self, path):
        budget, side = self.store.max_bytes, self.store.max_side
        def worker():
            result = import_avatar_folder(path, Path(path).name)
            self.validate_sequences(result.values(), budget, side)
            return result
        return self.submit(worker, self.use_sets)

    def import_pose_set(self, poses, animation_fps=None):
        from copy import deepcopy
        poses = deepcopy(poses)
        fps = self.settings.animation_fps if animation_fps is None else Settings.from_dict({'animation_fps': animation_fps}).animation_fps
        budget, side = self.store.max_bytes, self.store.max_side
        def worker():
            folder = APP_DIR/'images'; folder.mkdir(parents=True, exist_ok=True); result = {}
            for role, paths in poses.items():
                if role not in ('idle', 'talk', 'blink', 'happy', 'angry', 'sad', 'relaxed', 'surprised'): continue
                if len(paths) > 256: raise ValueError('Use até 256 arquivos por pose.')
                result[role] = []
                for source in paths:
                    source = Path(source)
                    if source.is_file() and source.resolve().parent == folder.resolve():
                        result[role].append(str(source)); continue
                    with source.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()[:16]
                    target = folder/(digest+source.suffix.lower())
                    if not target.exists(): copy_optimized_image(source, target)
                    result[role].append(str(target))
            if not result.get('idle'): raise ValueError('Adicione uma imagem parada.')
            self.validate_sequences(result.values(), budget, side)
            return result
        def success(result):
            self.use_sets({role: result.get(role, []) for role in ('idle','talk','blink')})
            self.settings.animation_fps = fps
            self.preferences['expressions2d'] = {key: paths for key, paths in result.items() if key not in ('idle','talk','blink') and paths}
            self.remember_avatar(); self.defer_save(); self.changed.emit(); self.notice.emit('Personagem 2D montado e salvo.')
        return self.submit(worker, success, 'Montando personagem 2D…')

    def import_pack(self, path):
        def success(result):
            if result['model_path']: self.use_model(result['model_path'])
            else: self.use_sets(result['sets'])
            for key,value in result['settings'].items():
                if key in PACK_SETTINGS: setattr(self.settings,key,value)
            if self.mode=='2D':
                self.preferences['expressions2d']=result.get('expressions',{})
                self.preferences['avatar2d_name']=result['name']
            elif result['settings'].get('expression3d') not in (None,'neutral'):
                self.manual_expression=result['settings']['expression3d']
            setup = result.get('studio', {})
            if setup:
                self.preferences.update(motion_config(setup))
                self.preferences['expression_profiles'][self.identity] = expression_config(setup.get('expression_mapping'))
                self.preferences['expression_profiles'] = dict(list(self.preferences['expression_profiles'].items())[-48:])
            self.camera_revision+=1; self.remember_avatar(); self.changed.emit()
            self.notice.emit('Pacote importado com poses, expressões e enquadramento.')
        self.submit(lambda: import_avatar_pack(path), success)

    def export_pack(self, path):
        model = self.model_path if self.mode == '3D' else ''
        sets = {} if self.mode == '3D' else dict(self.sets)
        from copy import deepcopy
        config={key:deepcopy(getattr(self.settings,key)) for key in PACK_SETTINGS}
        config['expression3d']=self.manual_expression or 'neutral'
        mappings=deepcopy(self.preferences.get('expressions2d',{})) if self.mode=='2D' else {}
        name=self.avatar_name()
        setup = dict(expression_mapping=deepcopy(self.expression_mapping), **motion_config(self.preferences))
        self.submit(lambda: export_avatar_pack(path, name, sets, config, model, mappings, setup),
                    lambda _: self.notice.emit('Pacote salvo com sucesso.'), 'Salvando pacote de avatar…')

    def tick(self):
        now = time.monotonic(); elapsed = now-self.last_tick
        self.tick_lag = max(0., elapsed-self.timer.interval()/1000)
        dt = min(.2, elapsed); self.last_tick = now
        self.inputs.poll(now)
        raw = self.microphone.read_level() if self.inputs.wanted['audio'] and not self.paused else 0.
        self.speech.sensitivity = self.settings.sensitivity; self.speech.smoothing = self.settings.smoothing
        state = self.speech.update(raw, self.microphone.voice_allowed)
        self.level, self.speaking = state.level, state.speaking
        if raw > .003 or not self.inputs.wanted['audio']: self.quiet_since = None
        elif self.quiet_since is None: self.quiet_since = now
        if now < self.test_until and not self.paused: self.level = .7; self.speaking = True
        if self.calibration_until:
            self.noise_samples.append(raw)
            if now >= self.calibration_until:
                self.calibration_until = 0
                self.settings.noise_floor, self.settings.sensitivity = calibrate_noise(self.noise_samples)
                self.defer_save(); self.notice.emit('Microfone calibrado.')
        sample, self.camera_frame, self.tracking_status, error = self.tracker.latest()
        self.face = self.smoother.update(sample, dt, self.preference('face_smoothing',.55,.1,.9), self.preference('face_strength',1.,.2,2.))
        self.update_motion(dt, now)
        if error and error != self.error_seen: self.error_seen = error; self.notice.emit(error)
        if not error: self.error_seen = ''
        for future, success in list(self.jobs):
            if future.done():
                self.jobs.remove((future,success))
                try: success(future.result()); self.defer_save()
                except Exception as exc: self.notice.emit(f'Operação não concluída: {exc}')
        self.changed.emit()

    def close(self):
        if self.closing: return
        self.closing = True; self.timer.stop(); self.save_timer.stop()
        self.motion_preview.stop()
        self.inputs.close()
        try: self.microphone.stop()
        except Exception: pass
        self.executor.shutdown(wait=True, cancel_futures=True); self.save()
        self.recovery.finish(capture_state(self))
