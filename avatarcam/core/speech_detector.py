from dataclasses import dataclass


@dataclass
class SpeechState:
    level: float
    speaking: bool


class SpeechDetector:
    """Converte volume bruto em estado estavel de fala."""

    def __init__(self, sensitivity: float, smoothing: float, mouth_hold_ticks: int = 7) -> None:
        self.sensitivity = sensitivity
        self.smoothing = smoothing
        self.mouth_hold_ticks = mouth_hold_ticks
        self.smoothed_level = 0.0
        self.speaking = False
        self.voice_frames = 0
        self.silence_frames = 0

    def reset(self) -> None:
        self.smoothed_level = 0.0
        self.speaking = False
        self.voice_frames = 0
        self.silence_frames = 0

    def update(self, raw_level: float) -> SpeechState:
        raw_level = max(0.0, min(1.0, raw_level))
        keep = self.smoothing
        self.smoothed_level = (self.smoothed_level * keep) + (raw_level * (1.0 - keep))

        on_threshold = self.sensitivity
        off_threshold = max(0.02, self.sensitivity * 0.58)

        if self.smoothed_level >= on_threshold:
            self.voice_frames += 1
            self.silence_frames = 0
        elif self.smoothed_level <= off_threshold:
            self.silence_frames += 1
            self.voice_frames = 0

        if not self.speaking and self.voice_frames >= 1:
            self.speaking = True
        elif self.speaking and self.silence_frames >= self.mouth_hold_ticks:
            self.speaking = False

        return SpeechState(level=self.smoothed_level, speaking=self.speaking)
