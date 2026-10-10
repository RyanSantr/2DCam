"""Servidor apenas em loopback para o visualizador WebGL e o OBS."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import SimpleQueue
from threading import Thread, Lock
from urllib.parse import urlsplit, unquote
import json
import secrets
import mimetypes
import time


class ViewerServer:
    def __init__(self, token: str | None = None):
        self.token = token or secrets.token_urlsafe(24)
        self.commands = SimpleQueue()
        self.lock = Lock()
        self.snapshot = {'level': 0, 'speaking': False, 'model': '', 'fps': 30, 'expression': 'neutral'}
        self.model_path = None
        self.server = None
        self.thread = None
        self.asset_dir = Path(__file__).resolve().parent.parent / 'web3d'

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}/{self.token}/'

    def publish(self, state: dict, model_path: str = ''):
        with self.lock:
            self.snapshot = dict(state, timestamp=time.time())
            self.model_path = Path(model_path) if model_path and Path(model_path).is_file() and Path(model_path).suffix.lower() in ('.vrm', '.glb') else None
            if self.model_path:
                info = self.model_path.stat()
                self.snapshot['model'] = f'model/{info.st_mtime_ns}-{info.st_size}/{self.model_path.name}'
            else:
                self.snapshot['model'] = ''

    def start(self, port=8765):
        if self.server:
            return self.url
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _route(self):
                expected = f'127.0.0.1:{self.server.server_port}'
                if self.headers.get('Host') != expected:
                    return None
                path = unquote(urlsplit(self.path).path)
                prefix = '/' + owner.token + '/'
                return path[len(prefix):] if path.startswith(prefix) else None

            def _send(self, body, mime='application/json', status=200):
                self.send_response(status)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; base-uri 'none'")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except ConnectionError:
                    pass

            def do_GET(self):
                route = self._route()
                if route is None:
                    self._send(b'{}', status=403)
                    return
                if route == 'api/state':
                    with owner.lock:
                        snapshot = dict(owner.snapshot)
                    self._send(json.dumps(snapshot, allow_nan=False).encode())
                elif route.startswith('model/'):
                    with owner.lock:
                        path = owner.model_path
                        expected_model = owner.snapshot['model']
                    if not path or route != expected_model:
                        self._send(b'{}', status=404)
                        return
                    try:
                        with path.open('rb') as stream:
                            self.send_response(200)
                            self.send_header('Content-Type', 'model/gltf-binary')
                            self.send_header('Content-Length', str(path.stat().st_size))
                            self.send_header('Cache-Control', 'no-store')
                            self.end_headers()
                            while block := stream.read(65536):
                                self.wfile.write(block)
                    except (OSError, ConnectionError):
                        return
                elif route in ('', 'index.html', 'viewer.js', 'style.css'):
                    path = owner.asset_dir / (route or 'index.html')
                    if path.is_file():
                        self._send(path.read_bytes(), mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
                    else:
                        self._send(b'{}', status=404)
                else:
                    self._send(b'{}', status=404)

            def do_POST(self):
                route = self._route()
                origin = self.headers.get('Origin')
                expected = f'http://127.0.0.1:{self.server.server_port}'
                if route != 'api/command' or origin not in (None, expected):
                    self._send(b'{}', status=403)
                    return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 16384:
                        raise ValueError()
                    command = json.loads(self.rfile.read(size))
                    if not isinstance(command, dict) or command.get('action') not in ('camera', 'expression', 'test', 'microphone', 'reset_camera'):
                        raise ValueError()
                    if command['action'] == 'camera':
                        from avatarcam.core.settings import Settings
                        Settings.from_dict({'camera3d': command.get('value')})
                    if command['action'] == 'expression':
                        from avatarcam.core.settings import Settings
                        Settings.from_dict({'expression3d': command.get('value')})
                    owner.commands.put(command)
                    self._send(b'{"ok":true}')
                except (ValueError, TypeError, KeyError):
                    self._send(b'{"error":"Comando invalido"}', status=400)

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.server.daemon_threads = True
        self.thread = Thread(target=self.server.serve_forever, daemon=True, name='AvatarCam3D')
        self.thread.start()
        return self.url

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None
