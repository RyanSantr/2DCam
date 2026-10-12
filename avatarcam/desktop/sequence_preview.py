"""Prévia 2D com a mesma linha de tempo da saída, carregada fora da interface."""
from concurrent.futures import ThreadPoolExecutor
import time
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel
from avatarcam.core.asset_store import AssetStore


class SequencePreview(QLabel):
    progress = Signal(int, int)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__('Escolha uma pose', parent)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='pose-preview')
        self.future = None; self.sequence = None; self.fps = 8
        self.started = 0.; self.elapsed = 0.; self.paused = False; self.frame_index = -1
        self.timer = QTimer(self); self.timer.setInterval(33); self.timer.timeout.connect(self.tick)

    def play(self, paths):
        self.stop(); self.setText('Carregando animação…')
        def decode():
            store = AssetStore(); store.configure(32 * 1048576, 320)
            return store.load(paths)
        self.future = self.pool.submit(decode); self.timer.start()

    def stop(self):
        self.timer.stop()
        if self.future: self.future.cancel()
        self.future = None; self.sequence = None; self.frame_index = -1
        self.elapsed = 0.; self.paused = False; self.clear()

    def release(self):
        self.stop(); self.pool.shutdown(wait=False, cancel_futures=True)

    def set_fps(self, fps):
        self.fps = max(1, fps)
        if self.sequence: self.restart()

    def restart(self):
        self.elapsed = 0.; self.started = time.monotonic(); self.paused = False
        if self.sequence: self.timer.start(); self.tick()

    def toggle_pause(self):
        if not self.sequence: return
        self.paused = not self.paused
        if self.paused:
            self.elapsed = time.monotonic() - self.started; self.timer.stop()
        else:
            self.started = time.monotonic() - self.elapsed; self.timer.start()

    def tick(self):
        if self.future:
            if not self.future.done(): return
            future, self.future = self.future, None
            try: self.sequence = future.result()
            except (OSError, ValueError) as error:
                self.timer.stop(); self.setText('Não foi possível abrir esta sequência.'); self.failed.emit(str(error)); return
            if not self.sequence.frames: self.timer.stop(); return
            self.started = time.monotonic()
        if not self.sequence: return
        index = self.sequence.index(time.monotonic() - self.started, self.fps)
        if index != self.frame_index:
            self.frame_index = index
            pixmap = QPixmap.fromImage(ImageQt(self.sequence.frames[index]))
            self.setPixmap(pixmap.scaled(min(320,self.width()), min(400,self.height()),
                                         Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.progress.emit(index + 1, len(self.sequence.frames))
        if len(self.sequence.frames) == 1: self.timer.stop()
