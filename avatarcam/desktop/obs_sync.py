"""Acompanha a cena em programa do OBS pelo protocolo WebSocket 5, localmente."""
import base64
import hashlib
import json
import time
from PySide6.QtCore import QObject, Signal, QTimer, QUrl
from PySide6.QtWebSockets import QWebSocket


def obs_config(value):
    value = value if isinstance(value, dict) else {}
    port = value.get('port', 4455)
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535: port = 4455
    links = value.get('links', {})
    links = {key: name for key, name in list(links.items())[:256]
             if isinstance(key, str) and 0 < len(key) <= 160 and isinstance(name, str) and len(name) <= 80} if isinstance(links, dict) else {}
    secret = value.get('secret', '')
    if not isinstance(secret, str) or len(secret) > 8192: secret = ''
    return dict(enabled=value.get('enabled') is True, port=port, links=links,
                remember=value.get('remember') is True, secret=secret if value.get('remember') is True else '')


def authentication(password, salt, challenge):
    secret = base64.b64encode(hashlib.sha256((password + salt).encode('utf-8')).digest()).decode('ascii')
    return base64.b64encode(hashlib.sha256((secret + challenge).encode('utf-8')).digest()).decode('ascii')


def protect_password(value, decrypt=False):
    """DPAPI vincula a senha ao usuário do Windows; o texto não vai ao disco."""
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]
    raw = base64.b64decode(value, validate=True) if decrypt else value.encode('utf-8')
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))); output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    func = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    func.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    func.restype = wintypes.BOOL
    if not func(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)): raise OSError('Não foi possível proteger a senha neste Windows.')
    kernel = ctypes.WinDLL('kernel32'); kernel.LocalFree.argtypes = [ctypes.c_void_p]; kernel.LocalFree.restype = ctypes.c_void_p
    try:
        data = ctypes.string_at(output.data, output.size)
        return data.decode('utf-8') if decrypt else base64.b64encode(data).decode('ascii')
    finally: kernel.LocalFree(output.data)


class ObsSync(QObject):
    status_changed = Signal(str)
    scenes_changed = Signal()
    program_changed = Signal()
    availability_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QWebSocket(); self.socket.setParent(self)
        self.socket.setMaxAllowedIncomingMessageSize(2 * 1024 * 1024)
        self.socket.setMaxAllowedIncomingFrameSize(2 * 1024 * 1024)
        self.socket.textMessageReceived.connect(self.message)
        self.socket.disconnected.connect(self.disconnected)
        self.socket.errorOccurred.connect(lambda _: self.network_error())
        self.socket.pong.connect(lambda *_: self.watchdog.stop())
        self.retry = QTimer(self); self.retry.setSingleShot(True); self.retry.timeout.connect(self.open)
        self.watchdog = QTimer(self); self.watchdog.setSingleShot(True); self.watchdog.timeout.connect(self.timeout)
        self.heartbeat = QTimer(self); self.heartbeat.setInterval(15000); self.heartbeat.timeout.connect(self.ping)
        self.request_watch=QTimer(self); self.request_watch.setInterval(1000); self.request_watch.timeout.connect(self.expire_requests)
        self.enabled = False; self.ready = False; self.password = ''; self.port = 4455
        self.scenes = []; self.program = {}; self.collection = ''; self.status = 'Sincronização desligada'
        self.pending = {}; self.sequence = 0; self.failures = 0; self.collection_revision = 0
        self.program_revision = 0; self.collection_changing = False; self.scene_list_dirty = False

    def set_status(self, text):
        self.status = text; self.status_changed.emit(text)

    def connect_obs(self, port=4455, password=''):
        self.disconnect_obs()
        self.port = obs_config({'port': port})['port']; self.password = password
        self.enabled = True; self.failures = 0; self.open()

    def open(self):
        if not self.enabled: return
        self.set_status('Conectando ao OBS…')
        self.socket.open(QUrl(f'ws://127.0.0.1:{self.port}')); self.watchdog.start(8000)

    def disconnect_obs(self):
        self.enabled = False; self.ready = False
        self.retry.stop(); self.watchdog.stop(); self.heartbeat.stop(); self.socket.abort()
        self.pending.clear(); self.request_watch.stop(); self.scenes = []; self.program = {}; self.password = ''
        self.collection = ''; self.collection_changing = False; self.scene_list_dirty = False
        self.availability_changed.emit(False); self.scenes_changed.emit(); self.set_status('Sincronização desligada')

    def disconnected(self):
        self.ready = False; self.watchdog.stop(); self.heartbeat.stop(); self.request_watch.stop(); self.pending.clear()
        self.program = {}; self.scenes = []; self.collection = ''; self.collection_revision += 1
        self.collection_changing = False; self.scene_list_dirty = False
        self.availability_changed.emit(False); self.scenes_changed.emit()
        code = self.socket.closeCode().value
        if code in (4005, 4006, 4009, 4010):
            self.enabled = False
            self.set_status('Confira a senha e a versão do servidor WebSocket do OBS.'); return
        if self.enabled:
            self.set_status('OBS indisponível. Aguardando reconexão…')
            self.failures += 1; self.retry.start(min(30000, 1000 * 2 ** min(5, self.failures - 1)))

    def network_error(self):
        if self.enabled and not self.retry.isActive():
            self.set_status('Abra o OBS e habilite o servidor WebSocket em Ferramentas.')
            self.retry.start(min(30000, 1000 * 2 ** min(5, self.failures)))
            self.failures += 1

    def timeout(self):
        if self.enabled:
            self.socket.abort(); self.network_error()

    def ping(self):
        if self.ready:
            self.socket.ping(b'2DCam'); self.watchdog.start(8000)

    def send(self, op, data):
        self.socket.sendTextMessage(json.dumps(dict(op=op, d=data), ensure_ascii=False))

    def request(self, kind):
        if not self.ready or len(self.pending) >= 8: return
        if any(item[0] == kind for item in self.pending.values()): return
        self.sequence += 1; identity = str(self.sequence)
        self.pending[identity] = (kind, self.collection_revision, self.program_revision, time.monotonic())
        self.request_watch.start()
        self.send(6, dict(requestType=kind, requestId=identity))

    def expire_requests(self):
        if not self.pending: self.request_watch.stop(); return
        if any(time.monotonic()-item[3]>8 for item in self.pending.values()): self.timeout()

    def refresh(self):
        if any(item[0] == 'GetSceneList' for item in self.pending.values()):
            self.scene_list_dirty = True; return
        self.request('GetSceneList')

    def scene(self, name, uuid=None):
        if not isinstance(name, str) or not name or len(name) > 512: return {}
        if not uuid:
            match=next((item for item in self.scenes if item['name']==name),None)
            if match: return dict(match)
        key = 'uuid:' + uuid if isinstance(uuid, str) and 0 < len(uuid) <= 128 else 'name:' + hashlib.sha256((self.collection + '\0' + name).encode()).hexdigest()
        return dict(name=name, key=key)

    def current(self, name, uuid=None):
        self.program = self.scene(name, uuid)
        self.set_status('OBS: ' + self.program['name'] if self.program else 'OBS conectado')
        self.program_changed.emit()

    def message(self, raw):
        if not self.enabled or len(raw) > 2 * 1024 * 1024: return
        try:
            message = json.loads(raw); op = message['op']; data = message['d']
            if not isinstance(data, dict): return
            if op == 0:
                if not isinstance(data.get('rpcVersion'), int) or data['rpcVersion'] < 1: raise ValueError('Protocolo OBS incompatível.')
                identify = dict(rpcVersion=1, eventSubscriptions=6)  # Configurações + cenas; sem eventos de vídeo/áudio.
                challenge = data.get('authentication')
                if challenge:
                    if not self.password:
                        self.enabled = False; self.socket.abort(); self.set_status('Informe a senha exibida pelo OBS.'); return
                    identify['authentication'] = authentication(self.password, challenge['salt'], challenge['challenge'])
                self.send(1, identify)
            elif op == 2:
                self.watchdog.stop(); self.heartbeat.start(); self.ready = True; self.failures = 0
                self.collection_changing = False; self.set_status('OBS conectado'); self.availability_changed.emit(True)
                self.request('GetSceneCollectionList')
            elif op == 7 and self.ready:
                pending = self.pending.pop(data.get('requestId'), None)
                if not pending or pending[1] != self.collection_revision: return
                kind, _, revision, _ = pending
                if data.get('requestType') != kind: return
                if not data.get('requestStatus', {}).get('result'):
                    self.set_status('O OBS não retornou as cenas. Confira a conexão.'); return
                response = data.get('responseData', {})
                if kind == 'GetSceneCollectionList':
                    self.collection = str(response.get('currentSceneCollectionName', ''))[:512]; self.refresh()
                elif kind == 'GetSceneList':
                    self.scenes = [self.scene(item.get('sceneName'), item.get('sceneUuid')) for item in response.get('scenes', [])[:256] if isinstance(item, dict)]
                    self.scenes = [item for item in self.scenes if item]; self.scenes_changed.emit()
                    if revision == self.program_revision:
                        self.current(response.get('currentProgramSceneName'), response.get('currentProgramSceneUuid'))
                    if self.scene_list_dirty:
                        self.scene_list_dirty = False; self.refresh()
            elif op == 5 and self.ready:
                event = data.get('eventType'); event_data = data.get('eventData', {})
                if event == 'CurrentProgramSceneChanged' and not self.collection_changing:
                    self.program_revision += 1; self.current(event_data.get('sceneName'), event_data.get('sceneUuid'))
                elif event == 'CurrentSceneCollectionChanging':
                    self.collection_changing = True; self.collection_revision += 1; self.pending.clear()
                    self.scene_list_dirty = False
                    self.scenes = []; self.program = {}; self.scenes_changed.emit()
                elif event == 'CurrentSceneCollectionChanged':
                    self.collection_changing = False; self.request('GetSceneCollectionList')
                elif event in ('SceneCreated', 'SceneRemoved', 'SceneNameChanged'): self.refresh()
        except (ValueError, KeyError, TypeError, AttributeError):
            self.enabled = False; self.socket.abort(); self.set_status('Resposta do OBS incompatível. Use OBS 28 ou posterior.')

    def target(self, links, names):
        if not self.ready or not self.program: return None
        key = self.program['key']; name = self.program['name']
        target = links[key] if key in links else name if name in names else None
        return target if target in names else None

    def close(self):
        self.disconnect_obs()
