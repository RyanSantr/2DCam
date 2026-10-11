"""Ajustes portáteis do personagem, sem dispositivos ou caminhos pessoais."""
import math


def expression_config(value):
    if not isinstance(value, dict): return {}
    result = {}
    for action in ('neutral', 'happy', 'angry', 'sad', 'relaxed', 'surprised', 'mouth', 'blink'):
        entry = value.get(action)
        if not isinstance(entry, dict): continue
        target = entry.get('target', action)
        intensity = entry.get('intensity', 1.)
        if not isinstance(target, str) or len(target) > 100: continue
        if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not math.isfinite(intensity): intensity = 1.
        result[action] = dict(target=target, intensity=max(0., min(1., intensity)))
    return result


def motion_config(value):
    value = value if isinstance(value, dict) else {}
    strength = value.get('idle_strength', .5)
    if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(strength): strength = .5
    return dict(idle_motion=value.get('idle_motion', True) is True,
                idle_strength=max(.1, min(1.5, strength)))


def portable_setup(value):
    if not isinstance(value, dict): raise ValueError('Ajustes do personagem inválidos.')
    return dict(expression_mapping=expression_config(value.get('expression_mapping')),
                **motion_config(value))
