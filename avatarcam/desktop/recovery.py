"""Recuperação optativa após queda, sem ligar dispositivos automaticamente."""
import json
from copy import deepcopy
from pathlib import Path
from avatarcam.core.persistence import atomic_write_text
from avatarcam.core.settings import Settings
from avatarcam.desktop.preferences import sanitize_preferences

SETTINGS = ('avatar_scale', 'avatar_offset_x', 'avatar_offset_y', 'avatar_rotation', 'camera3d',
            'sensitivity', 'smoothing', 'noise_floor', 'speech_mode', 'mouth_hold_ticks', 'animation_fps',
            'auto_rotate3d', 'pet_enabled', 'pet_size', 'pet_offset_x', 'pet_offset_y')
PREFERENCES = ('expressions2d', 'avatar2d_name', 'face_smoothing', 'face_strength', 'expression_profiles', 'face_neutral', 'idle_motion', 'idle_strength')


def capture_state(controller):
    return dict(mode=controller.mode, model_path=controller.model_path, sets={k: list(v) for k, v in controller.sets.items() if not k.startswith('_')},
                settings={k: deepcopy(getattr(controller.settings, k)) for k in SETTINGS},
                preferences={k: deepcopy(controller.preferences.get(k)) for k in PREFERENCES})


def apply_state(controller, state):
    if not isinstance(state, dict) or state.get('mode') not in ('2D', '3D', 'Live2D'): raise ValueError('Sessão inválida.')
    if not isinstance(state.get('model_path'), str) or len(state['model_path']) > 4096: raise ValueError('Caminho de modelo inválido na sessão.')
    sets = state.get('sets', {})
    if not isinstance(sets, dict): raise ValueError('Imagens inválidas.')
    checked = Settings.from_dict(state.get('settings', {}))
    prefs = sanitize_preferences(state.get('preferences', {}))
    if state['mode'] == '2D':
        paths = sets.get('idle')
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and Path(p).is_file() for p in paths):
            raise ValueError('As imagens da sessão não estão disponíveis.')
    elif not isinstance(state.get('model_path'), str) or not Path(state['model_path']).is_file():
        raise ValueError('O modelo da sessão não está disponível.')
    if state['mode'] == 'Live2D':
        from avatarcam.desktop.live2d import runtime_available
        if not runtime_available(): raise ValueError('O componente Live2D não está disponível nesta distribuição.')
    for key in ('idle', 'talk', 'blink', 'pet', 'pet_talk'):
        paths = sets.get(key, [])
        if not isinstance(paths, list) or len(paths) > 512 or not all(isinstance(p, str) for p in paths): raise ValueError('Poses inválidas.')
    if state['model_path'] != controller.model_path: controller.renderer_report = {}
    controller.model_path = state['model_path']; controller.sets = deepcopy(sets)
    for key in SETTINGS: setattr(controller.settings, key, deepcopy(getattr(checked, key)))
    for key in PREFERENCES: controller.preferences[key] = prefs[key]
    controller.smoother.neutral = deepcopy(prefs['face_neutral'])
    controller.camera_revision += 1; controller.manual_expression = None; controller.store.clear()
    controller.microphone.speech_mode = controller.settings.speech_mode
    controller.switch_mode(state['mode']); controller.remember_avatar(); controller.defer_save()


class SessionRecovery:
    def __init__(self, folder):
        self.path = Path(folder) / 'session-recovery.json'; self.previous = None
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('unclean') is True and isinstance(data.get('state'), dict): self.previous = data['state']
        except (OSError, ValueError, AttributeError): pass

    def checkpoint(self, state, unclean=True):
        atomic_write_text(self.path, json.dumps(dict(unclean=unclean, state=state), ensure_ascii=False))

    def finish(self, state): self.checkpoint(state, False)
