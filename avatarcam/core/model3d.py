"""Importacao local de GLB e VRM com recursos incorporados."""
from pathlib import Path
import hashlib
import json
import os
import struct
import tempfile
from avatarcam.core.settings import APP_DIR
from avatarcam.core.avatar_pack import safe_name

MAX_MODEL_BYTES = 128 * 1024 * 1024


def inspect_model(path: Path) -> dict:
    if path.suffix.lower() not in ('.vrm', '.glb'):
        raise ValueError('Selecione um arquivo .vrm ou .glb.')
    size = path.stat().st_size
    if size < 24 or size > MAX_MODEL_BYTES:
        raise ValueError('Modelo vazio ou maior que 128 MB.')
    with path.open('rb') as stream:
        magic, version, length = struct.unpack('<4sII', stream.read(12))
        if magic != b'glTF' or version != 2 or length != size:
            raise ValueError('Arquivo GLB/VRM invalido ou incompleto.')
        chunk_size, chunk_type = struct.unpack('<II', stream.read(8))
        if chunk_type != 0x4E4F534A or chunk_size > min(8_000_000, size - 20):
            raise ValueError('Metadados do modelo invalidos.')
        data = json.loads(stream.read(chunk_size).decode('utf-8').rstrip('\x00 '))
        offset = 20 + chunk_size
        while offset < size:
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError('Modelo truncado.')
            length, kind = struct.unpack('<II', header)
            offset += 8 + length
            if offset > size:
                raise ValueError('Modelo truncado.')
            stream.seek(length, 1)
        if offset != size:
            raise ValueError('Tamanho do modelo invalido.')
    if not isinstance(data, dict) or data.get('asset', {}).get('version') != '2.0':
        raise ValueError('Formato glTF 2.0 esperado.')
    for group in ('buffers', 'images'):
        for item in data.get(group, []):
            uri = item.get('uri', '')
            if uri and not uri.startswith('data:'):
                raise ValueError('Exporte o GLB com texturas e recursos incorporados (sem arquivos externos).')
    unsupported = {'KHR_draco_mesh_compression', 'EXT_meshopt_compression', 'KHR_texture_basisu'}
    if unsupported.intersection(data.get('extensionsRequired', [])):
        raise ValueError('Exporte sem compressao Draco, Meshopt ou KTX2 para usar o visualizador local.')
    extensions = data.get('extensions', {})
    is_vrm = 'VRM' in extensions or 'VRMC_vrm' in extensions
    if path.suffix.lower() == '.vrm' and not is_vrm:
        raise ValueError('O arquivo nao contem um avatar VRM.')
    return {'kind': 'VRM' if is_vrm else 'GLB', 'size_mb': round(size / 1024**2, 1)}


def import_model(source: str) -> str:
    src = Path(source)
    inspect_model(src)
    folder = APP_DIR / 'models3d'
    folder.mkdir(parents=True, exist_ok=True)
    with src.open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()[:12]
    target = folder / f'{safe_name(src.stem)}_{digest}{src.suffix.lower()}'
    if target.exists():
        return str(target)
    fd, temporary = tempfile.mkstemp(dir=folder, suffix=src.suffix.lower())
    try:
        with os.fdopen(fd, 'wb') as output, src.open('rb') as input_file:
            while block := input_file.read(65536):
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        inspect_model(Path(temporary))
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(target)
