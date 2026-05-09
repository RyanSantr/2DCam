from dataclasses import asdict, dataclass
from pathlib import Path
import json


APP_DIR = Path.home() / ".avatarcam_2d"
SETTINGS_FILE = APP_DIR / "settings.json"


@dataclass
class Settings:
    sensitivity: float = 0.10
    smoothing: float = 0.38
    dark_mode: bool = True
    background: str = "studio"
    avatar_index: int = 0
    obs_background: str = "chroma_green"
    obs_always_on_top: bool = False
    idle_images: list[str] | None = None
    speaking_images: list[str] | None = None
    speaking_low_images: list[str] | None = None
    speaking_mid_images: list[str] | None = None
    speaking_high_images: list[str] | None = None
    animation_fps: int = 12
    auto_hide_controls: bool = False
    active_profile: str = "Default"
    profiles: dict | None = None
    obs_resolution: str = "1280x720"
    obs_borderless: bool = False

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            defaults = asdict(cls())
            valid_data = {key: value for key, value in data.items() if key in defaults}
            return cls(**{**defaults, **valid_data})
        except Exception:
            return cls()

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
