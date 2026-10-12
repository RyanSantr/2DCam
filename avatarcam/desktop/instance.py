"""Uma instância por biblioteca; reabertura por um sinal local pequeno."""
import hashlib
import os
from pathlib import Path
import time
from PySide6.QtCore import QLockFile, QElapsedTimer, QCoreApplication, QTimer, QThread
from avatarcam.core.persistence import atomic_write_text


class InstanceGuard:
    def __init__(self, data_dir):
        directory = Path(data_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256(os.path.normcase(str(directory)).encode()).hexdigest()[:24]
        self.name = '2DCam-' + identity
        self.lock = QLockFile(str(directory / 'studio-instance.lock'))
        self.lock.setStaleLockTime(0)
        self.mailbox = directory / 'studio-activation'
        self.poll_timer = None; self.polls = 0; self.accepts = 0
        self.primary = self.lock.tryLock(0)

    def listen(self, activate):
        if not self.primary: return False
        try: self.mailbox.mkdir(exist_ok=True)
        except OSError: return False

        def poll():
            self.polls += 1
            try:
                names = os.listdir(self.mailbox)
                requests = [self.mailbox / name for name in names[:16] if name.endswith('.request')]
            except OSError: return
            for request in requests:
                token = request.stem
                if len(token) != 24 or any(char not in '0123456789abcdef' for char in token): continue
                try:
                    with request.open('rb') as stream: content = stream.read(65)
                    if content == b'activate' and time.time() - request.stat().st_mtime < 60:
                        activate(); self.accepts += 1
                    request.unlink(missing_ok=True)
                except OSError: continue

        self.poll_timer = QTimer()
        self.poll_timer.setInterval(200); self.poll_timer.timeout.connect(poll); self.poll_timer.start()
        return True

    def notify(self, timeout_ms=10000):
        request = self.mailbox / (os.urandom(12).hex() + '.request')
        try:
            atomic_write_text(request, 'activate')
            elapsed = QElapsedTimer(); elapsed.start()
            while elapsed.elapsed() < timeout_ms:
                if QCoreApplication.instance(): QCoreApplication.processEvents()
                if not request.exists(): return True
                QThread.msleep(10)
            return False
        except OSError: return False
        finally:
            try: request.unlink(missing_ok=True)
            except OSError: pass

    def close(self):
        if self.poll_timer:
            self.poll_timer.stop()
            try: self.poll_timer.timeout.disconnect()
            except RuntimeError: pass
        if self.primary: self.lock.unlock()
