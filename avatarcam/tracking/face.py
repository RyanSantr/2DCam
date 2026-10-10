"""Rastreamento local. Nenhuma imagem sai do computador ou e gravada."""
from pathlib import Path
import math
import threading
import time
import numpy as np

MODEL = Path(__file__).resolve().parents[1] / 'assets/tracking/face_landmarker.task'


def empty_face():
    return dict(detected=False, jaw=0., blinkLeft=0., blinkRight=0., smile=0.,
                frown=0., surprise=0., yaw=0., pitch=0., roll=0., gazeX=0., gazeY=0.)


def face_values(result):
    """Converte coeficientes MediaPipe para movimentos do avatar."""
    values = empty_face()
    if not result.face_landmarks:
        return values
    scores = {c.category_name: c.score for c in result.face_blendshapes[0]} if result.face_blendshapes else {}
    values.update(detected=True, jaw=scores.get('jawOpen', 0),
                  blinkLeft=scores.get('eyeBlinkLeft', 0), blinkRight=scores.get('eyeBlinkRight', 0),
                  smile=(scores.get('mouthSmileLeft', 0)+scores.get('mouthSmileRight', 0))/2,
                  frown=(scores.get('mouthFrownLeft', 0)+scores.get('mouthFrownRight', 0))/2,
                  surprise=max(scores.get('browInnerUp', 0), scores.get('browOuterUpLeft', 0)),
                  gazeX=(scores.get('eyeLookOutLeft', 0)+scores.get('eyeLookInRight', 0)
                         -scores.get('eyeLookInLeft', 0)-scores.get('eyeLookOutRight', 0))/2,
                  gazeY=(scores.get('eyeLookUpLeft', 0)+scores.get('eyeLookUpRight', 0)
                         -scores.get('eyeLookDownLeft', 0)-scores.get('eyeLookDownRight', 0))/2)
    if result.facial_transformation_matrixes:
        matrix = np.asarray(result.facial_transformation_matrixes[0])[:3, :3]
        rotation = matrix / np.maximum(np.linalg.norm(matrix, axis=0), 1e-8)
        values['yaw'] = math.asin(float(np.clip(-rotation[2, 0], -1, 1)))
        values['pitch'] = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        values['roll'] = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    return values


class FaceSmoother:
    def __init__(self):
        self.values = empty_face()
        self.neutral = {k: 0. for k in ('yaw', 'pitch', 'roll')}
        self.raw_head = dict(self.neutral)

    def calibrate(self):
        if not self.values['detected']:
            return False
        for key in self.neutral:
            self.neutral[key] = self.raw_head[key]
            self.values[key] = 0.
        return True

    def update(self, sample, dt=.04, smoothing=.55, strength=1.):
        keep = min(.95, max(.05, smoothing)) ** (max(.001, dt)/.04)
        self.values['detected'] = bool(sample.get('detected'))
        if self.values['detected']:
            self.raw_head = {key: float(sample.get(key,0.)) for key in self.neutral}
        for key in self.values:
            if key == 'detected':
                continue
            target = float(sample.get(key, 0.)) if sample.get('detected') else 0.
            if key in self.neutral and sample.get('detected'):
                target -= self.neutral[key]
            limit = .8 if key in self.neutral else 1.
            target = max(-limit if key in ('yaw','pitch','roll','gazeX','gazeY') else 0., min(limit, target*strength))
            self.values[key] = self.values[key]*keep + target*(1-keep)
        return dict(self.values)


def create_landmarker(video=True):
    import mediapipe as mp
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO if video else mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1, output_face_blendshapes=True, output_facial_transformation_matrixes=True)
    return mp.tasks.vision.FaceLandmarker.create_from_options(options)


class FaceTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.sample = empty_face()
        self.frame = None
        self.timestamp = 0.
        self.status = 'Câmera desligada'
        self.error = ''
        self.fps=20; self.width=480; self.height=360; self.preview_enabled=True

    def configure(self, fps=20, width=480, height=360, preview=False):
        self.fps=max(8,min(30,int(fps))); self.width=int(width); self.height=int(height)
        self.preview_enabled=bool(preview)
        if not preview:
            with self.lock: self.frame=None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive() and not self.stop_event.is_set()

    def start(self, device=0):
        if self.thread and self.thread.is_alive():
            return False
        self.stop_event.clear()
        with self.lock:
            self.error = ''; self.status = 'Iniciando câmera…'
        self.thread = threading.Thread(target=self._run, args=(device,), name='FaceTracking', daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        with self.lock:
            self.sample = empty_face(); self.frame = None; self.timestamp = 0.
            if not self.error: self.status = 'Câmera desligada'

    def latest(self):
        with self.lock:
            sample = dict(self.sample) if time.monotonic()-self.timestamp < .5 else empty_face()
            return sample, self.frame, self.status, self.error

    def _run(self, device):
        capture = detector = None
        try:
            import cv2
            import mediapipe as mp
            detector = create_landmarker()
            if self.stop_event.is_set(): return
            capture = cv2.VideoCapture(device, cv2.CAP_DSHOW)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_FPS, self.fps)
            if not capture.isOpened():
                raise RuntimeError('Câmera indisponível. Selecione outra câmera ou libere o acesso nas configurações do Windows.')
            start = time.monotonic(); last_ms = -1; failures = 0
            while not self.stop_event.is_set():
                iteration=time.monotonic()
                ok, bgr = capture.read()
                if not ok:
                    failures += 1
                    if failures >= 10: raise RuntimeError('A câmera foi desconectada ou deixou de responder.')
                    self.stop_event.wait(.05); continue
                failures = 0
                # Algumas webcams ignoram a resolucao solicitada.
                if bgr.shape[1] > self.width:
                    bgr=cv2.resize(bgr,(self.width,max(1,round(bgr.shape[0]*self.width/bgr.shape[1]))),interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                ms = max(last_ms+1, int((time.monotonic()-start)*1000)); last_ms = ms
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms)
                sample = face_values(result)
                with self.lock:
                    self.sample = sample; self.frame = rgb if self.preview_enabled else None; self.timestamp = time.monotonic()
                    self.status = 'Rosto detectado' if sample['detected'] else 'Posicione o rosto diante da câmera'
                self.stop_event.wait(max(0,1/self.fps-(time.monotonic()-iteration)))
        except Exception as exc:
            with self.lock:
                self.error = str(exc); self.status = 'Não foi possível iniciar o rastreamento'
        finally:
            if capture is not None: capture.release()
            if detector is not None: detector.close()
            with self.lock:
                self.sample = empty_face(); self.frame = None; self.timestamp = 0.
