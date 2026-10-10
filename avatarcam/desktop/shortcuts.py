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
)

DEFAULT_BINDINGS = {action: chord for chord, action, _ in SHORTCUTS}
RESERVED = ('Ctrl+O', 'Ctrl+M', 'Ctrl+T', 'Ctrl+P', 'Ctrl+Shift+O', 'Space')


def validate_bindings(value):
    if not isinstance(value, dict): raise ValueError('Configuração de atalhos inválida.')
    result = {}; used = set(RESERVED)
    for default, action, _ in SHORTCUTS:
        chord = value.get(action, default)
        if not isinstance(chord, str) or len(chord) > 64: raise ValueError('Atalho inválido.')
        if not chord: result[action] = ''; continue
        sequence = QKeySequence.fromString(chord, QKeySequence.SequenceFormat.PortableText)
        normalized = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        if sequence.count() != 1 or not normalized or sequence[0].key().value == 0x1ffffff:
            raise ValueError('Use uma única combinação por ação.')
        if normalized in used: raise ValueError('Há uma combinação repetida ou reservada pelo app: ' + normalized)
        if '+' not in normalized and not (normalized.startswith('F') and normalized[1:].isdigit() and 1 <= int(normalized[1:]) <= 24):
            raise ValueError('Use Ctrl/Alt/Shift ou uma tecla F1…F24 para não interferir na digitação.')
        used.add(normalized); result[action] = normalized
    return result


def shortcut_rows(bindings=None):
    bindings = validate_bindings(bindings or {})
    return [(bindings[action], action, label) for _, action, label in SHORTCUTS if bindings[action]]


class LiveShortcuts(QObject):
    triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = None
        self.enabled = False

    def set_enabled(self, enabled, bindings=None):
        self.close()
        if not enabled:
            return True
        self.manager = HotkeyManager()
        for chord, action, _ in shortcut_rows(bindings):
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
