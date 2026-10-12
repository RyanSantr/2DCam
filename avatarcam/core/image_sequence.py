"""Formatos 2D e ordem dos arquivos antes de copiar para a biblioteca."""
from pathlib import Path
import re

IMAGE_EXTS = {'.png', '.gif', '.webp'}
IMAGE_FILTER = 'Imagens e animações (*.png *.gif *.webp)'


def natural_paths(paths):
    def key(path):
        name = Path(path).name.casefold()
        parts = tuple((1, int(part)) if part.isdecimal() else (0, part)
                      for part in re.split(r'(\d+)', name))
        return parts, str(Path(path)).casefold()
    # Não ordene os nomes internos da biblioteca: eles são hashes, não números de quadros.
    return sorted(dict.fromkeys(str(Path(path)) for path in paths), key=key)


def image_paths(paths):
    files = []
    for path in paths:
        item = Path(path)
        candidates = item.iterdir() if item.is_dir() else [item]
        files.extend(str(file) for file in candidates if file.is_file() and file.suffix.lower() in IMAGE_EXTS)
    return natural_paths(files)
