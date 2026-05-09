from dataclasses import asdict, dataclass
from pathlib import Path
import json


APP_DIR = Path.home() / ".avatarcam_2d"
SETTINGS_FILE = APP_DIR / "settings.json"


@dataclass
class Settings:
    sensitivity: float = 0.16
    smoothing: float = 0.72
    dark_mode: bool = True
    background: str = "studio"
    avatar_index: int = 0

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
