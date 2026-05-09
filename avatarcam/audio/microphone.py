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
        self._stream = sd.RawInputStream(
            channels=1,
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is None:
            return

        self._stream.stop()
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
        self._levels.put_nowait(level)

    def _clear_queue(self) -> None:
        while not self._levels.empty():
            try:
                self._levels.get_nowait()
            except queue.Empty:
                break
