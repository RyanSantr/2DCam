"""Perfis completos; valida tudo antes de substituir o avatar atual."""
from copy import deepcopy
from pathlib import Path
from avatarcam.core.settings import Settings
from avatarcam.desktop.preferences import sanitize_preferences, ROLES

IMAGE_FIELDS = dict(idle='idle_images', talk='speaking_images', blink='blink_images',
                    pet='pet_images', pet_talk='pet_speaking_images')
SETTING_FIELDS = ('avatar_scale', 'avatar_offset_x', 'avatar_offset_y', 'avatar_rotation', 'camera3d',
                  'sensitivity', 'smoothing', 'noise_floor', 'speech_mode', 'mouth_hold_ticks', 'animation_fps',
                  'auto_rotate3d', 'pet_enabled', 'pet_size', 'pet_offset_x', 'pet_offset_y')
PREFERENCE_FIELDS = ('mode', 'avatar2d_name', 'expressions2d', 'performance', 'face_smoothing',
                     'face_strength', 'output_size', 'output_background', 'hide_controls', 'output_on_top', 'expression_profiles', 'face_neutral')


def save_profile(controller, name):
    name = name.strip()
    if not name or len(name) > 80:
        raise ValueError('Use um nome de perfil com até 80 caracteres.')
    entry = {key: deepcopy(getattr(controller.settings, key)) for key in SETTING_FIELDS}
    entry['avatar3d_path'] = controller.model_path
    for role, field in IMAGE_FIELDS.items():
        entry[field] = list(controller.sets[role])
    entry['studio'] = {key: deepcopy(controller.preferences.get(key)) for key in PREFERENCE_FIELDS}
    entry['studio']['mode'] = controller.mode
    entry['studio'] = {key: value for key, value in sanitize_preferences(entry['studio']).items() if key in PREFERENCE_FIELDS}
    if controller.settings.profiles is None:
        controller.settings.profiles = {}
    controller.settings.profiles[name] = entry
    controller.settings.active_profile = name
    controller.defer_save()


def load_profile(controller, name):
    entry = (controller.settings.profiles or {}).get(name)
    if not isinstance(entry, dict):
        raise ValueError('Perfil não encontrado.')
    # Settings valida posições e valores; nenhum dado atual muda se houver erro.
    checked = Settings.from_dict(deepcopy(entry))
    modern = isinstance(entry.get('studio'), dict)
    metadata = sanitize_preferences(entry['studio'] if modern else {'mode': controller.preferences.get('profile_modes', {}).get(name, '2D')})
    mode = metadata['mode']
    if mode == 'Live2D':
        from avatarcam.desktop.live2d import runtime_available
        if not runtime_available(): raise ValueError('O componente Live2D não está disponível nesta distribuição.')
    model = checked.avatar3d_path or controller.model_path
    if mode != '2D' and not Path(model).is_file():
        raise ValueError('O modelo deste perfil não foi encontrado. Importe o avatar novamente.')
    sets = {role: list(getattr(checked, field) or []) if field in entry else list(controller.sets.get(role, [])) for role, field in IMAGE_FIELDS.items()}
    if mode == '2D' and (not sets['idle'] or not all(Path(path).is_file() for path in sets['idle'])):
        raise ValueError('As imagens deste perfil não foram encontradas. Importe o avatar novamente.')
    controller.model_path = model
    controller.sets = sets
    for key in SETTING_FIELDS:
        if key in entry:
            setattr(controller.settings, key, getattr(checked, key))
    controller.microphone.speech_mode = controller.settings.speech_mode
    # Perfis antigos nao tinham vinculos; limpar evita misturar dois personagens.
    controller.preferences['expressions2d'] = metadata['expressions2d']
    if modern:
        for key in PREFERENCE_FIELDS:
            if key in entry['studio']:
                controller.preferences[key] = metadata[key]
        controller.set_performance(metadata['performance'])
        if hasattr(controller, 'smoother'): controller.smoother.neutral = deepcopy(controller.preferences['face_neutral'])
    controller.settings.active_profile = name
    controller.camera_revision += 1
    controller.manual_expression = None
    controller.store.clear()
    controller.switch_mode(mode)
    controller.remember_avatar()
    controller.defer_save()
    controller.changed.emit()


def delete_profile(controller, name):
    profiles = controller.settings.profiles or {}
    if name not in profiles:
        return False
    del profiles[name]
    controller.preferences.get('profile_modes', {}).pop(name, None)
    if controller.settings.active_profile == name:
        controller.settings.active_profile = 'Default'
    controller.defer_save()
    return True
