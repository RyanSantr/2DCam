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
    choices = {'mode': ('3D', '2D', 'Live2D'), 'performance': ('balanced', 'economy', 'quality', 'auto'),
               'output_background': ('green', 'blue', 'dark'), 'output_size': tuple(OUTPUT_SIZES)}
    for key, allowed in choices.items():
        if not isinstance(result.get(key), str) or result[key] not in allowed:
            result[key] = allowed[0]
    if not isinstance(result.get('avatar2d_name'), str):
        result['avatar2d_name'] = 'Avatar 2D'
    result['hide_controls'] = result.get('hide_controls') is True
    result['output_on_top'] = result.get('output_on_top') is True
    result['global_shortcuts'] = result.get('global_shortcuts') is True
    from avatarcam.core.avatar_config import motion_config
    result.update(motion_config(result))
    from avatarcam.desktop.shortcuts import validate_bindings
    try: result['shortcut_bindings'] = validate_bindings(result.get('shortcut_bindings', {}))
    except ValueError: result['shortcut_bindings'] = validate_bindings({})
    for key in ('camera_identity', 'microphone_identity'):
        value = result.get(key, '')
        result[key] = value if isinstance(value, str) and len(value) <= 4096 else ''
    result['expressions2d'] = expressions(result.get('expressions2d'))
    from avatarcam.desktop.creative import expression_config, neutral_pose
    result['face_neutral'] = neutral_pose(result.get('face_neutral'))
    profiles = result.get('expression_profiles', {})
    result['expression_profiles'] = {key: expression_config(item) for key, item in list(profiles.items())[:48] if isinstance(key, str) and len(key) == 24} if isinstance(profiles, dict) else {}
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
        if entry.get('mode') in ('3D', 'Live2D'):
            path = entry.get('path')
            if isinstance(path, str) and 0 < len(path) <= 4096:
                valid.append(dict(mode=entry['mode'], name=entry['name'], path=path))
        elif entry.get('mode') == '2D':
            sets = entry.get('sets')
            if isinstance(sets, dict) and image_paths(sets.get('idle')) and sets['idle']:
                valid.append(dict(mode='2D', name=entry['name'],
                                  sets={key: list(sets.get(key, [])) if image_paths(sets.get(key, [])) else [] for key in ROLES},
                                  expressions=expressions(entry.get('expressions'))))
        if len(valid) == 12:
            break
    result['recent_avatars'] = valid
    from avatarcam.desktop.library import update_library
    library = []
    raw = result.get('avatar_library', valid)
    # Reutiliza a validação de poses/expressões sem recursão de preferências.
    for entry in (raw[:48] if isinstance(raw, list) else []):
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str): continue
        if entry.get('mode') in ('3D', 'Live2D') and isinstance(entry.get('path'), str) and 0 < len(entry['path']) <= 4096:
            item = dict(mode=entry['mode'], name=entry['name'][:64], path=entry['path'])
        elif entry.get('mode') == '2D' and isinstance(entry.get('sets'), dict) and image_paths(entry['sets'].get('idle')) and entry['sets']['idle']:
            item = dict(mode='2D', name=entry['name'][:64], sets={key: list(entry['sets'].get(key, [])) if image_paths(entry['sets'].get(key, [])) else [] for key in ROLES}, expressions=expressions(entry.get('expressions')))
        else: continue
        item['favorite'] = entry.get('favorite') is True
        item['renamed'] = entry.get('renamed') is True
        if isinstance(entry.get('tuning'), dict):
            from avatarcam.core.settings import Settings
            fields = ('avatar_scale','avatar_offset_x','avatar_offset_y','avatar_rotation','animation_fps','camera3d',
                      'auto_rotate3d','pet_enabled','pet_size','pet_offset_x','pet_offset_y','sensitivity','smoothing','noise_floor')
            checked = Settings.from_dict(entry['tuning'])
            item['tuning'] = {key: getattr(checked, key) for key in fields if key in entry['tuning']}
            item['tuning']['face_neutral'] = neutral_pose(entry['tuning'].get('face_neutral'))
            item['tuning'].update(motion_config(entry['tuning']))
            for key, low, high, default in (('face_smoothing', .1, .9, .55), ('face_strength', .2, 2., 1.)):
                value = entry['tuning'].get(key, default)
                item['tuning'][key] = max(low,min(high,value)) if isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value) else default
        library.append(item)
    # Mantém a ordem e elimina entradas repetidas ao migrar os recentes.
    merged = []
    for item in reversed(library):
        merged = update_library(merged, item)
        stored = next(entry for entry in merged if entry.get('path') == item.get('path') and entry.get('sets') == item.get('sets'))
        stored.update(favorite=item['favorite'], renamed=item['renamed'], name=item['name'])
    result['avatar_library'] = merged
    return result
