"""Uma instancia por biblioteca local, sem abrir outro renderizador."""
import hashlib
import os
from pathlib import Path
from PySide6.QtCore import QLockFile, QElapsedTimer, QCoreApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceGuard:
    def __init__(self, data_dir):
        directory = Path(data_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256(os.path.normcase(str(directory)).encode()).hexdigest()[:24]
        self.name = '2DCam-' + identity
        self.lock = QLockFile(str(directory / 'studio-instance.lock'))
        self.server = None
        self.clients = set()
        self.primary = self.lock.tryLock(0)

    def listen(self, activate):
        if not self.primary:
            return False
        # A trava pertence a este processo; um endpoint antigo pode ser removido.
        QLocalServer.removeServer(self.name)
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)

        def accept():
            while self.server.hasPendingConnections():
                client = self.server.nextPendingConnection()
                self.clients.add(client)
                client.buffer = bytearray()

                def receive(socket=client):
                    socket.buffer.extend(bytes(socket.readAll()))
                    if len(socket.buffer) > 64:
                        socket.abort()
                    elif b'\n' in socket.buffer:
                        if bytes(socket.buffer) == b'activate\n':
                            activate()
                        socket.disconnectFromServer()

                def cleanup(socket=client):
                    self.clients.discard(socket)
                    socket.deleteLater()

                client.readyRead.connect(receive)
                client.disconnected.connect(cleanup)
                receive()

        self.server.newConnection.connect(accept)
        return self.server.listen(self.name)

    def notify(self, timeout_ms=2500):
        elapsed = QElapsedTimer()
        elapsed.start()
        while elapsed.elapsed() < timeout_ms:
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if socket.waitForConnected(min(150, timeout_ms - elapsed.elapsed())):
                socket.write(b'activate\n')
                QCoreApplication.processEvents()
                socket.flush()
                sent = socket.bytesToWrite() == 0 or socket.waitForBytesWritten(1000)
                socket.disconnectFromServer()
                return sent
            # Aguarda eventos locais, sem criar uma segunda janela na corrida de abertura.
            from PySide6.QtCore import QThread
            QThread.msleep(50)
        return False

    def close(self):
        for client in list(self.clients):
            client.abort()
        if self.server:
            self.server.close()
        if self.primary:
            self.lock.unlock()
