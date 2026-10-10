from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from avatarcam.core.persistence import atomic_write_text
from avatarcam.core.settings import Settings
import json

from avatarcam.core.settings import APP_DIR, SETTINGS_FILE


BACKUP_DIR = APP_DIR / "backups"
MAX_BACKUPS = 12


def create_settings_backup(reason: str = "manual") -> Path | None:
    """Cria um backup leve do settings.json antes de mudancas importantes."""
    if not SETTINGS_FILE.is_file():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_reason = "".join(char for char in reason.lower().replace(" ", "_") if char.isalnum() or char == "_")
    backup_path = BACKUP_DIR / f"settings_{stamp}_{safe_reason or 'backup'}.json"
    shutil.copy2(SETTINGS_FILE, backup_path)
    prune_settings_backups()
    return backup_path


def list_settings_backups() -> list[Path]:
    if not BACKUP_DIR.is_dir():
        return []
    return sorted(BACKUP_DIR.glob("settings_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)


def restore_settings_backup(backup_path: Path | None = None) -> Path:
    backups = list_settings_backups()
    source = backup_path or (backups[0] if backups else None)
    if source is None or not source.is_file():
        raise FileNotFoundError("Nenhum backup de configuracao encontrado.")

    APP_DIR.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding='utf-8')
    Settings.from_dict(json.loads(content))
    create_settings_backup('antes_restaurar')
    atomic_write_text(SETTINGS_FILE, content)
    return source


def prune_settings_backups(limit: int = MAX_BACKUPS) -> None:
    for old_backup in list_settings_backups()[limit:]:
        try:
            old_backup.unlink()
        except OSError:
            continue
