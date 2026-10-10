"""Frames Pillow compartilhados pelo preview e pela captura OBS."""
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageSequence


@dataclass
class FrameSequence:
    frames: list
    durations: list[float]
    signature: tuple = ()

    def index(self, seconds: float, fps: int) -> int:
        if not self.frames:
            return 0
        if self.durations:
            phase = seconds % sum(self.durations)
            for index, duration in enumerate(self.durations):
                phase -= duration
                if phase < 0:
                    return index
            return len(self.frames) - 1
        return int(seconds * fps) % len(self.frames)


class AssetStore:
    def __init__(self):
        self.cache = OrderedDict()
        self.max_bytes = 64 * 1024 * 1024
        self.max_side = 1280
        self.revision = 0
        self.failed = OrderedDict()

    def load(self, paths: list[str]) -> FrameSequence:
        signature = tuple((str(Path(p).resolve()), Path(p).stat().st_mtime_ns, Path(p).stat().st_size) for p in paths if Path(p).is_file())
        if signature in self.failed:
            raise ValueError(self.failed[signature])
        try:
            return self._decode(signature)
        except (OSError,ValueError) as error:
            self.failed[signature]=str(error)
            while len(self.failed)>16: self.failed.popitem(last=False)
            raise

    def _decode(self, signature):
        if signature in self.cache:
            self.cache.move_to_end(signature)
            return self.cache[signature][0]
        frames, durations = [], []
        used = 0
        gif_only = len(signature) == 1 and Path(signature[0][0]).suffix.lower() == '.gif'
        for path, _, _ in signature:
            with Image.open(path) as image:
                for frame in ImageSequence.Iterator(image):
                    rgba = frame.convert('RGBA')
                    rgba.thumbnail((self.max_side, self.max_side), Image.Resampling.LANCZOS)
                    used += rgba.width * rgba.height * 4
                    if used > self.max_bytes or len(frames) >= 256:
                        raise ValueError('Animacao muito pesada: reduza dimensoes ou numero de frames (maximo 256).')
                    frames.append(rgba)
                    durations.append(max(.02, frame.info.get('duration', 100) / 1000))
        sequence = FrameSequence(frames, durations if gif_only else [], signature)
        while self.cache and sum(entry[1] for entry in self.cache.values()) + used > self.max_bytes:
            self.cache.popitem(last=False)
        self.cache[signature] = (sequence, used)
        return sequence

    @property
    def used_bytes(self):
        return sum(entry[1] for entry in self.cache.values())

    def configure(self, max_bytes, max_side):
        self.max_bytes = max_bytes; self.max_side = max_side; self.clear()

    def clear(self):
        self.cache.clear(); self.failed.clear(); self.revision += 1
