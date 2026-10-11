"""Saída RGBA optativa pelo Spout; uma imagem e uma requisição por vez."""
import base64
import time
from PySide6.QtCore import QObject, QTimer, QSize, Qt
from PySide6.QtGui import QImage, QOpenGLContext, QOffscreenSurface


class TransparentOutput(QObject):
    def __init__(self, owner):
        super().__init__(owner); self.owner = owner; self.sender = None; self.context = None; self.surface = None
        self.pending = False; self.pending_since = 0.; self.generation = 0; self.frames = 0
        self.timer = QTimer(self); self.timer.timeout.connect(self.capture)

    def start(self):
        self.stop()
        try:
            import SpoutGL
            self.surface = QOffscreenSurface(); self.surface.create()
            self.context = QOpenGLContext()
            if not self.context.create() or not self.context.makeCurrent(self.surface): raise RuntimeError('A GPU não criou a saída transparente.')
            self.sender = SpoutGL.SpoutSender(); self.sender.setSenderName('2DCam - Transparente')
            self.context.doneCurrent(); self.owner.controller.transparent_active = True
            self.owner.controller.spout_error = ''; self.timer.start(1000 // 24)
            self.owner.controller.notice.emit('Saída transparente ligada. No OBS, use Captura Spout2 → 2DCam - Transparente.')
            return True
        except Exception as error:
            self.stop(); self.owner.controller.spout_error = str(error)[:180]
            self.owner.controller.notice.emit('Não foi possível ligar a saída transparente: ' + str(error)); return False

    def stop(self):
        self.timer.stop(); self.generation += 1; self.pending = False
        if self.sender:
            if self.context: self.context.makeCurrent(self.surface)
            self.sender.releaseSender(); self.sender = None
        if self.context: self.context.doneCurrent(); self.context = None
        if self.surface: self.surface.destroy(); self.surface = None
        self.owner.controller.transparent_active = False

    def capture(self):
        c = self.owner.controller
        if self.pending and time.monotonic()-self.pending_since > 3:
            self.fail(RuntimeError('O renderizador não respondeu. Recarregue a prévia e ligue a saída novamente.')); return
        if self.pending or not self.sender or c.paused or not c.render_active: return
        if c.mode == '2D':
            self.send(self.owner.avatar2d.transparent_image()); return
        view = self.owner.avatar3d
        if not view or not c.renderer_report.get('loaded'): return
        self.pending = True; self.pending_since = time.monotonic(); generation = self.generation; identity = c.identity
        def received(data):
            if generation != self.generation: return
            self.pending = False
            if identity != c.identity: return
            if isinstance(data, str) and data.startswith('data:image/png;base64,') and len(data) <= 4_000_000:
                try: self.send(QImage.fromData(base64.b64decode(data.split(',', 1)[1], validate=True)))
                except (ValueError, RuntimeError) as error: self.fail(error)
        view.page().runJavaScript('window.studioExportFrame ? window.studioExportFrame(640) : null', received)

    def send(self, image):
        if image.isNull() or not self.sender: return
        try:
            if max(image.width(), image.height()) > 640:
                image = image.scaled(QSize(640, 640), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image = image.convertToFormat(QImage.Format.Format_RGBA8888)
            if not self.context.makeCurrent(self.surface): raise RuntimeError('A saída perdeu a conexão com a GPU.')
            ok = self.sender.sendImage(image.constBits(), image.width(), image.height(), 0x1908, False, 0)
            self.context.doneCurrent()
            if not ok: raise RuntimeError('A GPU não aceitou o compartilhamento Spout.')
            self.frames += 1
        except Exception as error: self.fail(error)

    def fail(self, error):
        self.stop(); self.owner.controller.spout_error = str(error)[:180]
        self.owner.controller.notice.emit('Saída transparente interrompida: ' + str(error))
