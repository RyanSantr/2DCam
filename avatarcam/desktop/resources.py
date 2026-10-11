"""Mantem exemplos fora da pasta temporaria do executavel unico."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile

BUNDLED = Path(__file__).resolve().parents[1] / 'assets'


def preserve_assets(source, destination):
    source, destination = Path(source), Path(destination)
    files = [source / name for name in ('AvatarHumanoide.vrm', 'StudioBot.glb', 'studio.ico')]
    files += sorted((source / 'StudioBot2D').rglob('*.png'))
    for original in files:
        relative = original.relative_to(source)
        target = destination / relative
        content = original.read_bytes()
        if target.is_file() and hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(content).digest():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix='.asset-', dir=target.parent)
        try:
            with os.fdopen(handle, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return destination


def asset_directory():
    if not getattr(sys, 'frozen', False):
        return BUNDLED
    from avatarcam.core.settings import APP_DIR
    return preserve_assets(BUNDLED, APP_DIR / 'builtin-avatars')


def restore_builtin_paths(value, assets):
    """Recupera somente referencias de exemplos que perderam a pasta antiga."""
    if isinstance(value, dict):
        return {key: restore_builtin_paths(item, assets) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_builtin_paths(item, assets) for item in value]
    if isinstance(value, str) and '/avatarcam/assets/' in value.replace('\\', '/'):
        relative = value.replace('\\', '/').split('/avatarcam/assets/', 1)[1]
        allowed = relative in ('AvatarHumanoide.vrm', 'StudioBot.glb') or relative in {
            'StudioBot2D/' + role + '/001.png' for role in ('idle', 'talk', 'blink', 'pet')}
        if allowed and not Path(value).is_file() and (Path(assets) / relative).is_file():
            return str(Path(assets) / relative)
    return value
