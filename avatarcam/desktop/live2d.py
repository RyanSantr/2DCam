"""Importação local de modelos Cubism; o Core licenciado é fornecido separadamente."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from avatarcam.core.settings import APP_DIR


def core_path():
    # Somente para desenvolvimento/licença aprovada. Nenhum download automático.
    return Path(os.environ.get('AVATARCAM_CUBISM_CORE', str(Path(__file__).resolve().parents[1] / 'web3d/live2dcubismcore.min.js')))


def runtime_available():
    return core_path().is_file() and (Path(__file__).resolve().parents[1] / 'web3d/live2d.js').is_file()


def local_resource(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '?' in name or '#' in name:
        raise ValueError('O modelo Live2D deve usar arquivos locais relativos.')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts: raise ValueError('Recurso Live2D fora da pasta do modelo.')
    target = (root / Path(*path.parts)).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file(): raise ValueError('Recurso Live2D ausente ou fora da pasta: ' + name)
    return target


def inspect_live2d(path):
    path = Path(path)
    if not path.name.endswith('.model3.json') or path.stat().st_size > 2_000_000:
        raise ValueError('Selecione o arquivo .model3.json do personagem.')
    data = json.loads(path.read_text(encoding='utf-8-sig')); refs = data.get('FileReferences')
    if not isinstance(refs, dict) or not isinstance(refs.get('Moc'), str) or not isinstance(refs.get('Textures'), list) or not refs['Textures']:
        raise ValueError('Modelo Live2D incompleto: faltam malha ou texturas.')
    names = [refs['Moc'], *refs['Textures']]
    for key in ('Physics', 'Pose', 'UserData', 'DisplayInfo'):
        if refs.get(key): names.append(refs[key])
    for item in refs.get('Expressions', []): names.append(item['File'])
    for motions in refs.get('Motions', {}).values():
        for item in motions:
            names.append(item['File'])
            if item.get('Sound'): names.append(item['Sound'])
    if len(names) > 512: raise ValueError('Modelo com recursos demais.')
    files = {name: local_resource(path.parent, name) for name in names}
    if sum(file.stat().st_size for file in files.values()) + path.stat().st_size > 128 * 1048576:
        raise ValueError('Modelo Live2D maior que 128 MB.')
    with files[refs['Moc']].open('rb') as stream:
        if stream.read(4) != b'MOC3': raise ValueError('Arquivo MOC3 inválido.')
    return data, files


def import_live2d(source):
    source = Path(source); _, files = inspect_live2d(source)
    digest = hashlib.sha256()
    for name, file in sorted({source.name: source, **files}.items()):
        digest.update(name.encode())
        with file.open('rb') as stream:
            while block := stream.read(65536): digest.update(block)
    base = APP_DIR / 'models-live2d'; base.mkdir(parents=True, exist_ok=True)
    target = base / digest.hexdigest()[:24]
    if not target.exists():
        temp = Path(tempfile.mkdtemp(dir=base))
        try:
            for name, file in {source.name: source, **files}.items():
                output = temp / name; output.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(file, output)
            inspect_live2d(temp / source.name); temp.rename(target)
        finally:
            if temp.exists(): shutil.rmtree(temp)
    return str(target / source.name)
