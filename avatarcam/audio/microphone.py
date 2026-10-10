from __future__ import annotations

import math
import queue
import time
import numpy as np
from typing import Optional


class MicrophoneInput:
    """Captura audio do microfone e entrega volume RMS normalizado."""

    def __init__(self, samplerate: int = 48000, blocksize: int = 960) -> None:
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.device_index: int | None = None
        self._stream = None
        self._levels: queue.Queue[float] = queue.Queue(maxsize=3)
        self._sounddevice = None
        self.last_audio_time = 0.0
        self.last_voice_time = 0.0
        self.audio_warnings = 0
        self.speech_mode = 'volume'
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(2)
        except ImportError:
            self._vad = None

    @property
    def vad_available(self) -> bool:
        return self._vad is not None

    @property
    def voice_allowed(self) -> bool:
        return self.speech_mode != 'vad' or (self._vad is not None and time.monotonic() - self.last_voice_time < .12)

    @property
    def is_running(self) -> bool:
        try: return self._stream is not None and bool(self._stream.active)
        except Exception: return False

    def start(self) -> None:
        if self.is_running:
            return
        if self._stream is not None:
            self.stop()

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "A biblioteca sounddevice nao esta instalada. Rode: pip install -r requirements.txt"
            ) from exc

        self._sounddevice = sd
        if self._stream is not None:
            self.stop()
        if self.speech_mode == 'vad' and not self.vad_available:
            raise RuntimeError('Filtro de voz indisponivel. Instale webrtcvad-wheels ou use o modo volume.')
        # Negocia uma taxa suportada pelo dispositivo e pelo detector de voz.
        for rate in (48000, 32000, 16000, 8000):
            try:
                sd.check_input_settings(device=self.device_index, channels=1, dtype='int16', samplerate=rate)
                self.samplerate, self.blocksize = rate, rate // 50
                break
            except Exception:
                continue
        self.last_audio_time = time.monotonic()
        self.last_voice_time = 0.0
        stream = sd.RawInputStream(
            device=self.device_index,
            channels=1,
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="int16",
            callback=self._callback,
        )
        try:
            stream.start()
        except Exception:
            stream.close()
            self._stream = None
            raise
        self._stream = stream

    def set_device(self, device_index: int | None) -> None:
        restart = self.is_running
        if restart:
            self.stop()
        self.device_index = device_index
        if restart:
            self.start()

    @staticmethod
    def list_input_devices() -> list[tuple[str, int | None]]:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
        except Exception:
            return [("Padrao do sistema", None)]

        result: list[tuple[str, int | None]] = [("Padrao do sistema", None)]
        for index, device in enumerate(devices):
            if int(device.get("max_input_channels", 0)) > 0:
                name = str(device.get("name", f"Dispositivo {index}"))
                result.append((f"{index}: {name}", index))
        return result

    @staticmethod
    def input_catalog(refresh=False):
        import sounddevice as sd
        if refresh:
            # PortAudio da versão fixada só atualiza hotplug ao reinicializar.
            # Chamado apenas pelo worker, com o stream deste app fechado.
            if sd._initialized: sd._terminate()
            sd._initialize()
        hosts = sd.query_hostapis()
        result = [{'name': 'Padrão do sistema', 'index': None, 'id': ''}]
        for index, device in enumerate(sd.query_devices()):
            if device['max_input_channels'] > 0:
                host = hosts[device['hostapi']]['name']
                name = device['name']
                result.append({'name': f'{name} · {host}', 'index': index, 'id': host + ':' + name})
        return result

    def stop(self) -> None:
        if self._stream is None:
            return

        stream, self._stream = self._stream, None
        try:
            stream.stop()
        finally:
            try:
                stream.close()
            finally:
                self._clear_queue()

    def read_level(self) -> float:
        latest: Optional[float] = None
        while True:
            try:
                latest = self._levels.get_nowait()
            except queue.Empty:
                break
        return latest if latest is not None else 0.0

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            self.audio_warnings += 1
        self.last_audio_time = time.monotonic()
        samples = np.frombuffer(indata, dtype=np.int16).astype(np.float32) / 32768
        rms = math.sqrt(float(np.mean(samples * samples))) if samples.size else 0.0
        if self._vad is not None and self.speech_mode == 'vad':
            try:
                if self._vad.is_speech(bytes(indata), self.samplerate):
                    self.last_voice_time = self.last_audio_time
            except (ValueError, RuntimeError):
                self.audio_warnings += 1
        level = min(1.0, rms * 8.0)

        if self._levels.full():
            try:
                self._levels.get_nowait()
            except queue.Empty:
                pass
        try:
            self._levels.put_nowait(level)
        except queue.Full:
            pass

    def _clear_queue(self) -> None:
        while not self._levels.empty():
            try:
                self._levels.get_nowait()
            except queue.Empty:
                break
