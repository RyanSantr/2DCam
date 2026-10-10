from dataclasses import dataclass
import time
import math


@dataclass
class SpeechState:
    level: float
    speaking: bool


class SpeechDetector:
    """Suavizacao e fechamento da boca independentes do FPS."""
    def __init__(self, sensitivity: float, smoothing: float, mouth_hold_ticks: int = 7, clock=time.monotonic):
        self.sensitivity = sensitivity
        self.smoothing = smoothing
        self.mouth_hold_ticks = mouth_hold_ticks
        self.clock = clock
        self.reset()

    def reset(self) -> None:
        self.smoothed_level = 0.0
        self.speaking = False
        self.last_time = self.clock()
        self.last_voice = float('-inf')

    def update(self, raw_level: float, voice_allowed: bool = True) -> SpeechState:
        now = self.clock()
        dt = max(.001, min(1, now - self.last_time))
        self.last_time = now
        raw_level = max(0, min(1, raw_level)) if math.isfinite(raw_level) else 0
        keep = min(self.smoothing, .24) if raw_level > self.smoothed_level else self.smoothing
        keep = max(.01, min(.99, keep)) ** (dt / .033)
        self.smoothed_level = self.smoothed_level * keep + raw_level * (1 - keep)
        threshold = max(.02, self.sensitivity * .58) if self.speaking else self.sensitivity
        if voice_allowed and self.smoothed_level >= threshold:
            self.last_voice = now
            self.speaking = True
        elif now - self.last_voice >= self.mouth_hold_ticks * .033:
            self.speaking = False
        return SpeechState(self.smoothed_level, self.speaking)
