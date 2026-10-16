"""Atalhos de live opcionais; callbacks de teclado entram pela fila do Qt."""
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence
from avatarcam.core.hotkeys import HotkeyManager

SHORTCUTS = (
    ('F8', 'controls', 'Mostrar / ocultar controles'),
    ('F9', 'pause', 'Pausar / retomar'),
    ('F10', 'microphone', 'Microfone'),
    ('Ctrl+Alt+1', 'expression:auto', 'Expressão automática'),
    ('Ctrl+Alt+2', 'expression:neutral', 'Neutro'),
    ('Ctrl+Alt+3', 'expression:happy', 'Feliz'),
    ('Ctrl+Alt+4', 'expression:angry', 'Bravo'),
    ('Ctrl+Alt+5', 'expression:sad', 'Triste'),
    ('Ctrl+Alt+6', 'expression:surprised', 'Surpreso'),
    ('Ctrl+Alt+7', 'gesture:wave', 'Acenar'),
    ('Ctrl+Alt+8', 'gesture:yes', 'Concordar'),
    ('Ctrl+Alt+9', 'gesture:no', 'Negar'),
    ('Ctrl+Alt+0', 'gesture:celebrate', 'Comemorar'),
)

DEFAULT_BINDINGS = {action: chord for chord, action, _ in SHORTCUTS}
RESERVED = ('Ctrl+O', 'Ctrl+M', 'Ctrl+T', 'Ctrl+P', 'Ctrl+Shift+O', 'Space', 'Ctrl+Z', 'Ctrl+Shift+Z')
SCENE_PREFIX = 'scene:'
MAX_SCENES = 64
SCENE_ARROWS = ('Up', 'Down', 'Left', 'Right')


def scene_action(name):
    return SCENE_PREFIX + name


def is_scene_action(action):
    return isinstance(action, str) and action.startswith(SCENE_PREFIX) and 0 < len(action[len(SCENE_PREFIX):]) <= 80


def validate_bindings(value):
    if not isinstance(value, dict): raise ValueError('Configuração de atalhos inválida.')
    result = {}; used = set(RESERVED)
    actions = [(default, action) for default, action, _ in SHORTCUTS]
    scenes = [action for action in value if is_scene_action(action)]
    if len(scenes) > MAX_SCENES: raise ValueError('Use até 64 atalhos de cenas.')
    actions.extend(('', action) for action in scenes)
    for default, action in actions:
        chord = value.get(action, default)
        if not isinstance(chord, str) or len(chord) > 64: raise ValueError('Atalho inválido.')
        if not chord: result[action] = ''; continue
        sequence = QKeySequence.fromString(chord, QKeySequence.SequenceFormat.PortableText)
        normalized = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        if sequence.count() != 1 or not normalized or sequence[0].key().value == 0x1ffffff:
            raise ValueError('Use uma única combinação por ação.')
        if normalized in used: raise ValueError('Há uma combinação repetida ou reservada pelo app: ' + normalized)
        arrow = is_scene_action(action) and normalized in SCENE_ARROWS
        if '+' not in normalized and not arrow and not (normalized.startswith('F') and normalized[1:].isdigit() and 1 <= int(normalized[1:]) <= 24):
            raise ValueError('Use Ctrl/Alt/Shift ou F1…F24. Para cenas, também pode usar as setas.')
        used.add(normalized); result[action] = normalized
    return result


def with_scene_defaults(bindings, names):
    """Atribui as combinações livres; vazio é uma escolha explícita do usuário."""
    result = validate_bindings(bindings or {})
    names = [name for name in list(names)[:MAX_SCENES] if isinstance(name, str) and 0 < len(name) <= 80]
    live = {scene_action(name) for name in names}
    result = {action: chord for action, chord in result.items() if not is_scene_action(action) or action in live}
    available = [f'Ctrl+Shift+{number}' for number in range(1, 10) if f'Ctrl+Shift+{number}' not in result.values()]
    for name in names:
        action = scene_action(name)
        if is_scene_action(action) and action not in result:
            result[action] = available.pop(0) if available else ''
    return result


def shortcut_rows(bindings=None, scenes=()):
    bindings = validate_bindings(bindings or {})
    rows = [(bindings[action], action, label) for _, action, label in SHORTCUTS if bindings[action]]
    rows.extend((bindings[scene_action(name)], scene_action(name), 'Cena: ' + name)
                for name in list(scenes)[:MAX_SCENES] if bindings.get(scene_action(name)))
    return rows


class LiveShortcuts(QObject):
    triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = None
        self.enabled = False

    def set_enabled(self, enabled, bindings=None, scenes=()):
        self.close()
        if not enabled:
            return True
        self.manager = HotkeyManager()
        for chord, action, _ in shortcut_rows(bindings, scenes):
            chord = chord.lower().replace('meta+', 'windows+')
            if not self.manager.register(chord, lambda value=action: self.triggered.emit(value), on_release=True):
                self.close()
                return False
        self.enabled = True
        return True

    def close(self):
        if self.manager:
            self.manager.close()
            self.manager = None
        self.enabled = False
