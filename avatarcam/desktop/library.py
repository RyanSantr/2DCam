"""Identidades estáveis e biblioteca limitada, independente da lista de recentes."""
from copy import deepcopy
import hashlib
import os
import unicodedata


def avatar_id(entry):
    path = entry.get('path') if entry.get('mode') in ('3D', 'Live2D') else next(iter(entry.get('sets', {}).get('idle', [])), '')
    return hashlib.sha256((entry.get('mode', '') + ':' + os.path.normcase(os.path.abspath(path))).encode()).hexdigest()[:24]


def clean_name(value):
    return ' '.join(str(value).split())[:64]


def matches_search(entry, query):
    def normalized(text):
        return ''.join(c for c in unicodedata.normalize('NFD', str(text).casefold())
                       if not unicodedata.combining(c))
    return normalized(query.strip()) in normalized(entry.get('name', ''))


def update_library(entries, entry):
    identity = avatar_id(entry)
    old = next((item for item in entries if avatar_id(item) == identity), {})
    result = deepcopy(entry)
    result['favorite'] = old.get('favorite') is True
    if old.get('renamed'):
        result['name'] = old['name']; result['renamed'] = True
    others = [deepcopy(item) for item in entries if avatar_id(item) != identity]
    # Favoritos não somem quando muitos avatares são importados.
    ordered = [result] + others
    favorites = [item for item in ordered if item.get('favorite')]
    ordinary = [item for item in ordered if not item.get('favorite')]
    return (favorites + ordinary)[:48]
