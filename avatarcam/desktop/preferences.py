"""Valida dados da interface antes de usa-los em widgets e bibliotecas."""
from copy import deepcopy
import math
from avatarcam.desktop.output import OUTPUT_SIZES

ROLES = ('idle', 'talk', 'blink', 'pet', 'pet_talk')
EXPRESSIONS = ('happy', 'angry', 'sad', 'relaxed', 'surprised', 'neutral')


def image_paths(value):
    return isinstance(value, list) and len(value) <= 512 and all(isinstance(p, str) and 0 < len(p) <= 4096 for p in value)


def expressions(value):
    if not isinstance(value, dict):
        return {}
    return {key: list(paths) for key, paths in value.items() if key in EXPRESSIONS and image_paths(paths)}


def sanitize_preferences(value):
    result = deepcopy(value) if isinstance(value, dict) else {}
    choices = {'mode': ('3D', '2D'), 'performance': ('balanced', 'economy', 'quality'),
               'output_background': ('green', 'blue', 'dark'), 'output_size': tuple(OUTPUT_SIZES)}
    for key, allowed in choices.items():
        if not isinstance(result.get(key), str) or result[key] not in allowed:
            result[key] = allowed[0]
    if not isinstance(result.get('avatar2d_name'), str):
        result['avatar2d_name'] = 'Avatar 2D'
    result['hide_controls'] = result.get('hide_controls') is True
    result['output_on_top'] = result.get('output_on_top') is True
    result['global_shortcuts'] = result.get('global_shortcuts') is True
    result['expressions2d'] = expressions(result.get('expressions2d'))
    modes = result.get('profile_modes', {})
    result['profile_modes'] = {key: mode for key, mode in modes.items() if isinstance(key, str) and mode in ('2D', '3D')} if isinstance(modes, dict) else {}
    for key, default, low, high in (('face_smoothing', .55, .1, .9), ('face_strength', 1., .2, 2.), ('camera_device', 0, 0, 20)):
        number = result.get(key, default)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            number = default
        result[key] = max(low, min(high, number))
    recent = result.get('recent_avatars', [])
    valid = []
    for entry in recent if isinstance(recent, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str):
            continue
        if entry.get('mode') == '3D':
            path = entry.get('path')
            if isinstance(path, str) and 0 < len(path) <= 4096:
                valid.append(dict(mode='3D', name=entry['name'], path=path))
        elif entry.get('mode') == '2D':
            sets = entry.get('sets')
            if isinstance(sets, dict) and image_paths(sets.get('idle')) and sets['idle']:
                valid.append(dict(mode='2D', name=entry['name'],
                                  sets={key: list(sets.get(key, [])) if image_paths(sets.get(key, [])) else [] for key in ROLES},
                                  expressions=expressions(entry.get('expressions'))))
        if len(valid) == 12:
            break
    result['recent_avatars'] = valid
    return result
