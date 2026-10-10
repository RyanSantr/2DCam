from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import logging
import math
from avatarcam.core.persistence import atomic_write_text


APP_DIR = Path(os.environ.get('AVATARCAM_DATA_DIR', str(Path.home() / '.avatarcam_2d')))
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_DIR = APP_DIR / "logs"


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
    blink_images: list[str] | None = None
    animation_fps: int = 8
    auto_hide_controls: bool = False
    active_profile: str = "Default"
    profiles: dict | None = None
    obs_resolution: str = "1280x720"
    obs_borderless: bool = False
    avatar_scale: float = 1.0
    avatar_offset_x: float = 0.0
    avatar_offset_y: float = 0.0
    avatar_rotation: float = 0.0
    performance_mode: bool = False
    expressions: dict | None = None
    active_expression: str = "Default"
    hotkeys: dict | None = None
    scenes: dict | None = None
    active_scene: str = "Cena 1"
    idle_motion: bool = False
    avatar_shadow: bool = True
    streamer_safe: bool = False
    microphone_device: int | None = None
    performance_preset: str = "balanced"
    pet_enabled: bool = False
    pet_size: float = 0.85
    pet_images: list[str] | None = None
    pet_speaking_images: list[str] | None = None
    pet_loud_images: list[str] | None = None
    pet_offset_x: float = 0.72
    pet_offset_y: float = 0.62
    pet_reaction: str = "bounce"
    pet_reaction_strength: float = 0.55
    pet_layer: str = "front"
    pet_opacity: float = 1.0
    pet_mirror: bool = False
    mouth_hold_ticks: int = 5
    auto_start_minimized: bool = False
    advanced_mode: bool = False
    speech_mode: str = 'volume'
    noise_floor: float = 0.01
    avatar3d_path: str = ''
    expression3d: str = 'neutral'
    fps3d: int = 30
    auto_rotate3d: bool = False
    camera3d: dict | None = None
    viewer_port: int = 8765
    viewer_token: str = ''

    @classmethod
    def from_dict(cls, data: dict) -> 'Settings':
        if not isinstance(data, dict):
            raise ValueError('Configuracoes devem ser um objeto JSON.')
        defaults = asdict(cls())
        valid = {}
        for key, value in data.items():
            if key not in defaults:
                continue
            default = defaults[key]
            if key.endswith('_images'):
                if value is None:
                    valid[key] = None
                elif isinstance(value, list) and len(value) <= 512 and all(isinstance(p, str) for p in value):
                    valid[key] = value
                else:
                    raise ValueError(f'Lista de imagens invalida: {key}')
            elif key in ('profiles', 'scenes', 'expressions', 'hotkeys', 'camera3d'):
                if value is not None and not isinstance(value, dict):
                    raise ValueError(f'Configuracao invalida: {key}')
                valid[key] = value
            elif isinstance(default, bool):
                if not isinstance(value, bool):
                    raise ValueError(f'Valor liga/desliga invalido: {key}')
                valid[key] = value
            elif isinstance(default, (int, float)) or key == 'microphone_device':
                if value is None and key == 'microphone_device':
                    valid[key] = None
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f'Numero invalido: {key}')
                valid[key] = int(value) if isinstance(default, int) or key == 'microphone_device' else float(value)
            elif isinstance(default, str):
                if not isinstance(value, str) or len(value) > 4096:
                    raise ValueError(f'Texto invalido: {key}')
                valid[key] = value
        limits = {
            'sensitivity': (.04, .7), 'smoothing': (.1, .95), 'animation_fps': (1, 30),
            'avatar_scale': (.25, 2.5), 'avatar_offset_x': (-.8, .8), 'avatar_offset_y': (-.8, .8),
            'avatar_rotation': (-35, 35), 'pet_size': (.45, 1.6), 'pet_offset_x': (-.9, .9),
            'pet_offset_y': (-.9, .9), 'pet_reaction_strength': (0, 1), 'pet_opacity': (.1, 1),
            'mouth_hold_ticks': (1, 18), 'noise_floor': (0, .7), 'fps3d': (15, 60),
            'viewer_port': (1024, 65535), 'avatar_index': (0, 100), 'microphone_device': (0, 10000),
        }
        for key, (low, high) in limits.items():
            if key in valid and valid[key] is not None:
                valid[key] = max(low, min(high, valid[key]))
        choices = {
            'background': ('studio', 'aurora', 'grid', 'clean'),
            'obs_background': ('chroma_green', 'chroma_magenta', 'chroma_blue', 'obs_black'),
            'performance_preset': ('quality', 'balanced', 'performance', 'ultra'),
            'pet_layer': ('front', 'back'), 'speech_mode': ('volume', 'vad'),
            'expression3d': ('neutral', 'happy', 'angry', 'sad', 'relaxed', 'surprised'),
            'obs_resolution': ('1280x720', '1920x1080', '1080x1920', '960x540', '640x360'),
            'pet_reaction': ('none', 'bounce', 'shake', 'float', 'speed', 'bounce_speed', 'shake_speed'),
        }
        for key, allowed in choices.items():
            if key in valid and valid[key] not in allowed:
                raise ValueError(f'Opcao invalida: {key}')
        for collection in ('profiles', 'scenes', 'expressions'):
            entries = valid.get(collection)
            if entries:
                for name, entry in entries.items():
                    if not isinstance(name, str) or not isinstance(entry, dict):
                        raise ValueError(f'{collection}: item invalido')
                    # Valida os valores conhecidos, sem recursao de colecoes.
                    sanitized = cls.from_dict({k: v for k, v in entry.items() if k not in ('profiles', 'scenes', 'expressions')})
                    for key in list(entry):
                        if key in defaults and key not in ('profiles', 'scenes', 'expressions'):
                            entry[key] = getattr(sanitized, key)
                        elif key in ('idle', 'talk', 'talk_low', 'talk_mid', 'talk_high', 'blink', 'pet', 'pet_talk', 'pet_loud'):
                            if not isinstance(entry[key], list) or len(entry[key]) > 512 or not all(isinstance(p, str) for p in entry[key]):
                                raise ValueError('Lista de expressao invalida')
        if valid.get('hotkeys') and not all(isinstance(v, str) for v in valid['hotkeys'].values()):
            raise ValueError('Atalhos invalidos')
        camera = valid.get('camera3d')
        if camera:
            for key in ('position', 'target'):
                vector = camera.get(key)
                if not isinstance(vector, list) or len(vector) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 100 for v in vector):
                    raise ValueError('Enquadramento 3D invalido')
        return cls(**{**defaults, **valid})

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError, TypeError) as exc:
            logging.getLogger('avatarcam').warning('Configuracao nao carregada; arquivo original preservado: %s', exc)
            return cls()

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        content = json.dumps(asdict(self), indent=2, ensure_ascii=False, allow_nan=False)
        if SETTINGS_FILE.is_file():
            try:
                if SETTINGS_FILE.read_text(encoding="utf-8") == content:
                    return
            except OSError:
                pass
        if SETTINGS_FILE.exists():
            try:
                cls_data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
                self.from_dict(cls_data)
            except (ValueError, TypeError):
                atomic_write_text(SETTINGS_FILE.with_suffix('.invalid.json'), SETTINGS_FILE.read_text(encoding='utf-8'))
        atomic_write_text(SETTINGS_FILE, content)
