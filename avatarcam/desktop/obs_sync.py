"""Acompanha a cena em programa do OBS pelo protocolo WebSocket 5, localmente."""
import base64
import hashlib
import json
import time
from PySide6.QtCore import QObject, Signal, QTimer, QUrl
from PySide6.QtNetwork import QNetworkProxy, QAbstractSocket
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
    capture_status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = None
        self.retry = QTimer(self); self.retry.setSingleShot(True); self.retry.timeout.connect(self.open)
        self.watchdog = QTimer(self); self.watchdog.setSingleShot(True); self.watchdog.timeout.connect(self.timeout)
        self.heartbeat = QTimer(self); self.heartbeat.setInterval(15000); self.heartbeat.timeout.connect(self.ping)
        self.request_watch=QTimer(self); self.request_watch.setInterval(1000); self.request_watch.timeout.connect(self.expire_requests)
        self.enabled = False; self.ready = False; self.password = ''; self.port = 4455
        self.scenes = []; self.program = {}; self.collection = ''; self.status = 'Sincronização desligada'
        self.pending = {}; self.sequence = 0; self.failures = 0; self.collection_revision = 0
        self.program_revision = 0; self.collection_changing = False; self.scene_list_dirty = False
        self.capture_queue = None; self.capture_fixed = 0
        self.replace_socket()

    def replace_socket(self):
        if self.socket is not None:
            self.socket.blockSignals(True); self.socket.abort(); self.socket.deleteLater()
        socket = QWebSocket(parent=self)
        # A conexão é local, inclusive quando o Windows tem proxy ou VPN.
        socket.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        socket.setMaxAllowedIncomingMessageSize(2 * 1024 * 1024)
        socket.setMaxAllowedIncomingFrameSize(2 * 1024 * 1024)
        socket.textMessageReceived.connect(self.message)
        socket.disconnected.connect(self.disconnected)
        socket.errorOccurred.connect(self.network_error)
        socket.pong.connect(lambda *_: self.watchdog.stop())
        self.socket = socket

    def set_status(self, text):
        self.status = text; self.status_changed.emit(text)

    def connect_obs(self, port=4455, password=''):
        self.disconnect_obs()
        self.port = obs_config({'port': port})['port']; self.password = password
        self.enabled = True; self.failures = 0; self.open()

    def open(self):
        if not self.enabled: return
        self.retry.stop(); self.watchdog.stop(); self.replace_socket()
        self.set_status(f'Conectando ao OBS na porta {self.port}…')
        self.watchdog.start(8000); self.socket.open(QUrl(f'ws://127.0.0.1:{self.port}'))

    def clear_session(self):
        was_available = self.ready or bool(self.scenes)
        self.ready = False; self.watchdog.stop(); self.heartbeat.stop(); self.request_watch.stop(); self.pending.clear()
        self.program = {}; self.scenes = []; self.collection = ''; self.collection_revision += 1
        self.collection_changing = False; self.scene_list_dirty = False
        if self.capture_queue is not None:
            self.capture_queue = None; self.capture_status_changed.emit('A conexão caiu durante o ajuste da captura. Conecte e tente novamente.')
        if was_available: self.availability_changed.emit(False)
        self.scenes_changed.emit()

    def stop_with_error(self, text):
        self.enabled = False; self.retry.stop(); self.clear_session()
        self.socket.blockSignals(True); self.socket.abort(); self.socket.blockSignals(False)
        self.set_status(text)

    def disconnect_obs(self):
        self.enabled = False; self.retry.stop(); self.clear_session()
        self.socket.blockSignals(True); self.socket.abort(); self.socket.blockSignals(False)
        self.password = ''; self.set_status('Sincronização desligada')

    def disconnected(self):
        code = self.socket.closeCode().value
        if code == 4009:
            self.stop_with_error('Senha recusada pelo OBS. Copie a senha em Ferramentas → Configurações do servidor WebSocket.'); return
        if code == 4011:
            self.stop_with_error('O OBS encerrou esta conexão. Clique em Conectar para autorizar uma nova tentativa.'); return
        if 4002 <= code <= 4012:
            self.stop_with_error('Servidor incompatível. Use o WebSocket 5 do OBS 28 ou posterior e confira a porta.'); return
        self.clear_session(); self.network_error()

    def network_error(self, error=None):
        # O fechamento remoto entrega o código de autenticação em disconnected.
        if error == QAbstractSocket.SocketError.RemoteHostClosedError: return
        if self.enabled and not self.retry.isActive():
            self.clear_session()
            self.socket.blockSignals(True); self.socket.abort(); self.socket.blockSignals(False)
            delay = min(30000, 1000 * 2 ** min(5, self.failures))
            self.failures += 1
            self.set_status(f'OBS indisponível na porta {self.port}. Ative o servidor WebSocket no OBS e confira a porta. Nova tentativa em {delay // 1000} s.')
            self.retry.start(delay)

    def timeout(self):
        if self.enabled: self.network_error()

    def ping(self):
        if self.ready:
            self.socket.ping(b'2DCam'); self.watchdog.start(8000)

    def send(self, op, data):
        self.socket.sendTextMessage(json.dumps(dict(op=op, d=data), ensure_ascii=False))

    def request(self, kind, request_data=None, context=None):
        if not self.ready or len(self.pending) >= 8: return
        if any(item[0] == kind for item in self.pending.values()): return
        self.sequence += 1; identity = str(self.sequence)
        self.pending[identity] = (kind, self.collection_revision, self.program_revision, time.monotonic(), context, request_data)
        self.request_watch.start()
        data = dict(requestType=kind, requestId=identity)
        if request_data is not None: data['requestData'] = request_data
        self.send(6, data)

    def repair_capture(self):
        if not self.ready:
            self.capture_status_changed.emit('Conecte ao OBS primeiro.'); return
        if self.capture_queue is not None: return
        self.capture_queue = []; self.capture_fixed = 0
        self.capture_status_changed.emit('Verificando as fontes de captura do 2DCam…')
        self.request('GetInputList', context='capture:list')

    def next_capture(self):
        if self.capture_queue:
            self.request('GetInputSettings', dict(inputName=self.capture_queue.pop(0)), context='capture:read')
        else:
            count = self.capture_fixed; self.capture_queue = None
            self.capture_status_changed.emit(f'Captura Windows 10/1903+ aplicada em {count} fonte(s) do 2DCam.' if count else
                'Nenhuma fonte do 2DCam encontrada. Abra a janela do avatar e selecione-a em Captura de janela no OBS.')

    def capture_response(self, kind, response, context, request_data):
        if self.capture_queue is None: return
        if context == 'capture:list':
            self.capture_queue = [item['inputName'] for item in response.get('inputs', [])[:1024]
                if isinstance(item, dict) and item.get('inputKind') == 'window_capture'
                and isinstance(item.get('inputName'), str)]
            self.next_capture()
        elif context == 'capture:read':
            value = response.get('inputSettings', {}).get('window', '')
            parts = value.split(':') if isinstance(value, str) else []
            if len(parts) == 3 and parts[0].casefold() == '2dcam - avatar' and parts[2].casefold() in ('2dcamstudio.exe','python.exe','pythonw.exe'):
                self.request('SetInputSettings', dict(inputName=request_data['inputName'],
                    inputSettings=dict(method=2), overlay=True), context='capture:write')
            else: self.next_capture()
        elif context == 'capture:write':
            self.capture_fixed += 1; self.next_capture()

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
                        self.stop_with_error('Informe a senha exibida pelo OBS.'); return
                    identify['authentication'] = authentication(self.password, challenge['salt'], challenge['challenge'])
                self.send(1, identify)
            elif op == 2:
                self.retry.stop(); self.watchdog.stop(); self.heartbeat.start(); self.ready = True; self.failures = 0
                self.collection_changing = False; self.set_status('OBS conectado'); self.availability_changed.emit(True)
                self.request('GetSceneCollectionList')
            elif op == 7 and self.ready:
                pending = self.pending.pop(data.get('requestId'), None)
                if not pending or pending[1] != self.collection_revision: return
                kind, _, revision, _, context, request_data = pending
                if data.get('requestType') != kind: return
                if not data.get('requestStatus', {}).get('result'):
                    if context and context.startswith('capture:'):
                        self.capture_queue = None; self.capture_status_changed.emit('O OBS não permitiu ajustar a captura. Confira se a fonte ainda existe e tente novamente.'); return
                    if kind == 'GetSceneCollectionList': self.refresh(); return
                    self.set_status('O OBS não retornou as cenas. Confira a conexão.'); return
                response = data.get('responseData', {})
                if context and context.startswith('capture:'):
                    self.capture_response(kind, response, context, request_data)
                elif kind == 'GetSceneCollectionList':
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
                    if self.capture_queue is not None:
                        self.capture_queue = None; self.capture_status_changed.emit('A coleção de cenas mudou. Execute o ajuste de captura novamente.')
                    self.scene_list_dirty = False
                    self.scenes = []; self.program = {}; self.scenes_changed.emit()
                elif event == 'CurrentSceneCollectionChanged':
                    self.collection_changing = False; self.request('GetSceneCollectionList')
                elif event in ('SceneCreated', 'SceneRemoved', 'SceneNameChanged'): self.refresh()
        except (ValueError, KeyError, TypeError, AttributeError):
            self.stop_with_error('Resposta do OBS incompatível. Use OBS 28 ou posterior.')

    def target(self, links, names):
        if not self.ready or not self.program: return None
        key = self.program['key']; name = self.program['name']
        target = links[key] if key in links else name if name in names else None
        return target if target in names else None

    def close(self):
        self.disconnect_obs()
