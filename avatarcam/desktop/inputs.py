"""Recupera apenas entradas explicitamente ligadas, com espera progressiva."""
import time
from concurrent.futures import ThreadPoolExecutor
from avatarcam.tracking.devices import camera_devices, resolve_camera


class InputRecovery:
    def __init__(self, controller):
        self.c = controller
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='AvatarDevices')
        self.wanted = {'audio': False, 'camera': False}
        self.generation = {'audio': 0, 'camera': 0}
        self.pending = {}
        self.next_attempt = {'audio': 0., 'camera': 0.}
        self.failures = {'audio': 0, 'camera': 0}
        self.status = {'audio': '', 'camera': ''}
        self.audio_catalog = []; self.camera_catalog = []; self.catalog_revision = 0
        self.scan = None; self.closed = False
        self.camera_attempted = False

    def request_scan(self):
        if not self.closed and self.scan is None:
            def worker():
                try: audio = self.c.microphone.input_catalog()
                except Exception: audio = [{'name': 'Padrão do sistema', 'index': None, 'id': ''}]
                return audio, camera_devices()
            self.scan = self.pool.submit(worker)

    def request(self, kind, enabled):
        self.wanted[kind] = bool(enabled)
        self.generation[kind] += 1
        self.next_attempt[kind] = 0.; self.failures[kind] = 0
        self.status[kind] = 'Conectando…' if enabled else ''
        if kind == 'camera': self.camera_attempted = False
        if not enabled:
            if kind == 'camera': self.c.tracker.stop()
            elif kind not in self.pending:
                self.pool.submit(self._stop_audio)

    def _stop_audio(self):
        try: self.c.microphone.stop()
        except Exception: pass

    def _start(self, kind):
        c = self.c
        if kind == 'camera':
            identity = c.preferences.get('camera_identity', '')
            index = int(c.preferences.get('camera_device', 0))
            return self.pool.submit(lambda: resolve_camera(camera_devices(), identity, index))
        identity = c.preferences.get('microphone_identity', '')
        index = c.settings.microphone_device
        generation = self.generation['audio']
        def audio():
            self._stop_audio()
            catalog = c.microphone.input_catalog(refresh=True)
            if identity:
                matches = [item for item in catalog if item['id'] == identity]
                if len(matches) != 1: raise RuntimeError('Aguardando o microfone selecionado ser reconectado.')
                chosen = matches[0]['index']
            else: chosen = index
            if generation != self.generation['audio'] or not self.wanted['audio']:
                raise RuntimeError('Conexão cancelada.')
            c.microphone.device_index = chosen
            c.microphone.start()
            if generation != self.generation['audio'] or not self.wanted['audio']:
                self._stop_audio(); raise RuntimeError('Conexão cancelada.')
            return chosen, catalog
        return self.pool.submit(audio)

    def _failed(self, kind, error, now):
        self.failures[kind] += 1
        delay = min(30, 2 ** min(5, self.failures[kind]))
        self.next_attempt[kind] = now + delay
        self.status[kind] = f'{error} Nova tentativa em {delay}s.'
        if self.failures[kind] == 1: self.c.notice.emit(self.status[kind])

    def poll(self, now=None):
        if self.closed: return
        now = time.monotonic() if now is None else now
        if self.scan is not None and self.scan.done():
            try: self.audio_catalog, self.camera_catalog = self.scan.result(); self.catalog_revision += 1
            except Exception: pass
            self.scan = None
        for kind in ('audio', 'camera'):
            job = self.pending.get(kind)
            if job and job[0].done():
                future, generation = self.pending.pop(kind)
                stale = generation != self.generation[kind] or not self.wanted[kind]
                try:
                    value = future.result()
                    if stale:
                        if kind == 'audio': self.pool.submit(self._stop_audio)
                        continue
                    if kind == 'camera':
                        if not self.c.tracker.start(value): raise RuntimeError('Aguardando liberação da câmera.')
                        self.camera_attempted = True
                    else:
                        self.c.settings.microphone_device, self.audio_catalog = value
                        self.catalog_revision += 1
                    self.status[kind] = ''; self.next_attempt[kind] = now + 2
                except Exception as error:
                    if not stale: self._failed(kind, error, now)
            if not self.wanted[kind] or kind in self.pending or self.c.paused:
                continue
            active = self.c.microphone.is_running if kind == 'audio' else self.c.tracker.running
            if kind == 'camera' and not active and self.camera_attempted:
                error = self.c.tracker.latest()[3] or 'Câmera desconectada.'
                self._failed(kind, error, now); self.camera_attempted = False
            if kind == 'audio' and active and now - self.c.microphone.last_audio_time > 3:
                active = False
                self.next_attempt[kind] = min(self.next_attempt[kind], now)
            if active:
                if kind == 'audio' or self.c.tracker.timestamp:
                    self.failures[kind] = 0; self.status[kind] = ''
            elif now >= self.next_attempt[kind]:
                self.status[kind] = 'Reconectando…' if self.failures[kind] else 'Conectando…'
                self.pending[kind] = (self._start(kind), self.generation[kind])

    def close(self):
        if self.closed: return
        self.closed = True; self.wanted = {'audio': False, 'camera': False}
        self.pool.shutdown(wait=True, cancel_futures=True)
        self._stop_audio(); self.c.tracker.stop()
