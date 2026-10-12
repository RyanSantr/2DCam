"""Importacao em etapas, sem substituir a biblioteca anterior."""
from pathlib import Path, PurePosixPath
import json
import os
import shutil
import tempfile
import zipfile
from PIL import Image
from avatarcam.core.settings import APP_DIR, Settings
from avatarcam.core.avatar_config import portable_setup
from avatarcam.core.image_sequence import IMAGE_EXTS, natural_paths

AVATAR_DIR = APP_DIR / 'avatars'
MAX_IMAGE_SIDE = 1600
MAX_PACK_BYTES = 256 * 1024 * 1024
EXPRESSION_KEYS = ('happy', 'angry', 'sad', 'relaxed', 'surprised', 'neutral')
FOLDERS = {
    'idle': ('idle',), 'talk': ('talk', 'fala'),
    'talk_low': ('talk_low', 'fala_baixa'), 'talk_mid': ('talk_mid', 'fala_media'),
    'talk_high': ('talk_high', 'fala_alta'), 'blink': ('blink', 'piscar'),
    'pet': ('pet',), 'pet_talk': ('pet_talk', 'pet_fala'), 'pet_loud': ('pet_loud', 'pet_alto'),
}


def safe_name(name: str) -> str:
    cleaned = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in name.strip())[:80]
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1, 10)), *('LPT'+str(i) for i in range(1, 10))}
    if cleaned.upper() in reserved:
        cleaned = 'avatar_' + cleaned
    return cleaned or 'avatar'


def images_from_folder(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return natural_paths(str(p) for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def copy_optimized_image(src: Path, dest: Path) -> None:
    with Image.open(src) as image:
        image.verify()
    with Image.open(src) as image:
        if image.width * image.height > 32_000_000:
            raise ValueError(f'Imagem muito grande: {src.name}')
        if image.format in ('GIF', 'WEBP') or getattr(image, 'is_animated', False):
            shutil.copy2(src, dest)
        else:
            image = image.convert('RGBA')
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
            image.save(dest, format='PNG', optimize=True)


def _commit(stage: Path, name: str, settings: dict | None = None, studio: dict | None = None) -> dict:
    target = AVATAR_DIR / safe_name(name)
    number = 2
    while target.exists():
        target = AVATAR_DIR / f'{safe_name(name)}_{number}'
        number += 1
    stage.rename(target)
    models = list((target / 'model').glob('*')) if (target / 'model').is_dir() else []
    return {'name': target.name, 'settings': settings or {}, 'studio': studio or {}, 'model_path': str(models[0]) if models else '',
            'sets': {key: images_from_folder(target / key) for key in FOLDERS},
            'expressions': {key: images_from_folder(target / 'expressions' / key) for key in EXPRESSION_KEYS if images_from_folder(target / 'expressions' / key)}}


def import_avatar_folder(source: str, name: str) -> dict:
    source_path = Path(source)
    if not source_path.is_dir():
        raise ValueError('Pasta de avatar nao encontrada.')
    sources = {key: next((source_path / alias for alias in aliases if (source_path / alias).is_dir()), None) for key, aliases in FOLDERS.items()}
    if not any(images_from_folder(sources[key]) for key in ('idle', 'talk') if sources[key]):
        if images_from_folder(source_path): sources['idle'] = source_path
        else: raise ValueError('Escolha uma pasta com PNG, GIF ou WebP, ou subpastas idle / talk / blink.')
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.import-', dir=AVATAR_DIR))
    try:
        total = 0
        for key, folder in sources.items():
            destination = stage / key
            destination.mkdir()
            if folder:
                paths = images_from_folder(folder)
                if len(paths) > 256: raise ValueError('Use até 256 arquivos por pose.')
                for path in paths:
                    src = Path(path)
                    total += src.stat().st_size
                    if total > MAX_PACK_BYTES:
                        raise ValueError('Avatar excede 256 MB.')
                    copy_optimized_image(src, destination / (src.stem + src.suffix.lower()))
        (stage / 'manifest.json').write_text(json.dumps({'version': 2, 'name': name}), encoding='utf-8')
        return _commit(stage, name)['sets']
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def export_avatar_pack(destination: str, name: str, image_sets: dict, settings: dict, model_path: str = '', expression_sets: dict | None = None, studio: dict | None = None) -> None:
    Settings.from_dict(settings)
    setup = portable_setup(studio) if studio is not None else None
    expression_sets = {} if expression_sets is None else expression_sets
    if not isinstance(expression_sets, dict) or any(key not in EXPRESSION_KEYS or not isinstance(paths, list) or len(paths)>512 or not all(isinstance(path,str) for path in paths) for key,paths in expression_sets.items()):
        raise ValueError('Vínculos de expressão inválidos.')
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=dest.parent, suffix='.avatarpack.tmp')
    os.close(fd)
    try:
        sets = {}
        total_bytes = 0
        total_files = 1
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            model_entry = ''
            if model_path:
                from avatarcam.core.model3d import inspect_model
                model = Path(model_path)
                inspect_model(model)
                model_entry = 'model/' + model.name
                total_bytes += model.stat().st_size
                total_files += 1
                archive.write(model, model_entry)
            groups = {key:paths for key,paths in image_sets.items() if key in FOLDERS}
            groups.update({'expressions/'+key:paths for key,paths in expression_sets.items()})
            for key, paths in groups.items():
                sets[key] = []
                for index, path in enumerate(paths):
                    src = Path(path)
                    if not src.is_file():
                        raise ValueError(f'Asset ausente: {src.name}')
                    total_bytes += src.stat().st_size
                    total_files += 1
                    if total_bytes > MAX_PACK_BYTES or total_files > 2048:
                        raise ValueError('Pacote excede 256 MB ou 2048 arquivos.')
                    filename = f'{index:04d}_{src.name}'
                    archive.write(src, f'{key}/{filename}')
                    sets[key].append(filename)
            manifest = dict(version=4 if setup is not None else 3, name=name, sets=sets, settings=settings, model=model_entry)
            if setup is not None: manifest['studio'] = setup
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, allow_nan=False))
        os.replace(temporary, dest)
    finally:
        Path(temporary).unlink(missing_ok=True)


def import_avatar_pack(pack_path: str) -> dict:
    with zipfile.ZipFile(pack_path, 'r') as archive:
        infos = archive.infolist()
        if len(infos) > 2048 or sum(i.file_size for i in infos) > MAX_PACK_BYTES:
            raise ValueError('Avatarpack excede o limite de arquivos ou 256 MB.')
        manifests = [i for i in infos if i.filename == 'manifest.json']
        if len(manifests) != 1 or manifests[0].file_size > 1_000_000:
            raise ValueError('Manifesto ausente, duplicado ou muito grande.')
        seen = set()
        for item in infos:
            parts = PurePosixPath(item.filename).parts
            if '\\' in item.filename or not parts or item.filename.startswith('/') or item.filename.rstrip('/') != '/'.join(parts) or any(p in ('.', '..') or ':' in p for p in parts):
                raise ValueError('Avatarpack contem caminho invalido.')
            folded = item.filename.casefold()
            if folded in seen:
                raise ValueError('Avatarpack contem nomes duplicados.')
            seen.add(folded)
            if item.is_dir():
                if not ((len(parts)==1 and parts[0] in (*FOLDERS, 'model', 'expressions')) or (len(parts)==2 and parts[0]=='expressions' and parts[1] in EXPRESSION_KEYS)):
                    raise ValueError('Pasta inesperada no avatarpack.')
            elif item.filename != 'manifest.json' and not ((len(parts)==2 and ((parts[0] in FOLDERS and Path(parts[1]).suffix.lower() in IMAGE_EXTS) or (parts[0]=='model' and Path(parts[1]).suffix.lower() in ('.glb','.vrm')))) or (len(parts)==3 and parts[0]=='expressions' and parts[1] in EXPRESSION_KEYS and Path(parts[2]).suffix.lower() in IMAGE_EXTS)):
                raise ValueError('Arquivo inesperado no avatarpack.')
        manifest = json.loads(archive.read('manifest.json').decode('utf-8'))
        if not isinstance(manifest, dict) or not isinstance(manifest.get('name', 'Avatar'), str):
            raise ValueError('Manifesto invalido.')
        setup = portable_setup(manifest['studio']) if 'studio' in manifest else {}
        model_entries = [i.filename for i in infos if i.filename.startswith('model/') and not i.is_dir()]
        if len(model_entries) > 1 or (model_entries and manifest.get('model') != model_entries[0]):
            raise ValueError('Manifesto do modelo 3D invalido.')
        settings = manifest.get('settings', {})
        checked = Settings.from_dict(settings)
        normalized = {key: getattr(checked, key) for key in settings if hasattr(checked, key)}
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.import-', dir=AVATAR_DIR))
        try:
            for key in FOLDERS:
                (stage / key).mkdir()
            if model_entries:
                (stage / 'model').mkdir()
            for key in EXPRESSION_KEYS:
                if any(item.filename.startswith('expressions/'+key+'/') and not item.is_dir() for item in infos):
                    (stage / 'expressions' / key).mkdir(parents=True)
            for item in infos:
                if item.is_dir() or item.filename == 'manifest.json':
                    continue
                if item.filename in model_entries:
                    from avatarcam.core.model3d import inspect_model
                    model = stage / item.filename
                    with archive.open(item) as source, model.open('wb') as destination:
                        shutil.copyfileobj(source,destination,65536)
                    inspect_model(model)
                    continue
                raw = stage / (PurePosixPath(item.filename).name + '.raw')
                with archive.open(item) as source, raw.open('wb') as destination:
                    shutil.copyfileobj(source,destination,65536)
                try:
                    copy_optimized_image(raw, stage / item.filename)
                finally:
                    raw.unlink(missing_ok=True)
            if not images_from_folder(stage / 'idle') and not images_from_folder(stage / 'talk') and not model_entries:
                raise ValueError('Avatarpack sem imagens de idle ou fala.')
            (stage / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            return _commit(stage, manifest.get('name', Path(pack_path).stem), normalized, setup)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
