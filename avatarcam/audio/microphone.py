from __future__ import annotations

import math
import queue
import struct
from typing import Optional


class MicrophoneInput:
    """Captura audio do microfone e entrega volume RMS normalizado."""

    def __init__(self, samplerate: int = 44100, blocksize: int = 512) -> None:
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.device_index: int | None = None
        self._stream = None
        self._levels: queue.Queue[float] = queue.Queue(maxsize=3)
        self._sounddevice = None

    @property
    def is_running(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self.is_running:
            return

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "A biblioteca sounddevice nao esta instalada. Rode: pip install -r requirements.txt"
            ) from exc

        self._sounddevice = sd
        stream = sd.RawInputStream(
            device=self.device_index,
            channels=1,
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="float32",
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

    def stop(self) -> None:
        if self._stream is None:
            return

        try:
            self._stream.stop()
        finally:
            self._stream.close()
        self._stream = None
        self._clear_queue()

    def read_level(self) -> float:
        latest: Optional[float] = None
        while True:
            try:
                latest = self._levels.get_nowait()
            except queue.Empty:
                break
        return latest if latest is not None else 0.0

    def _callback(self, indata, frames, time, status) -> None:
        if status:
            # Evita interromper a UI por mensagens ocasionais do driver de audio.
            pass

        total = 0.0
        sample_count = max(1, len(indata) // 4)

        for index in range(sample_count):
            value = struct.unpack_from("f", indata, index * 4)[0]
            total += value * value

        rms = math.sqrt(total / sample_count)
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
