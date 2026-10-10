"""Atalhos de live opcionais; callbacks de teclado entram pela fila do Qt."""
from PySide6.QtCore import QObject, Signal
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


class LiveShortcuts(QObject):
    triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = None
        self.enabled = False

    def set_enabled(self, enabled):
        self.close()
        if not enabled:
            return True
        self.manager = HotkeyManager()
        for chord, action, _ in SHORTCUTS:
            if not self.manager.register(chord.lower(), lambda value=action: self.triggered.emit(value), on_release=True):
                self.close()
                return False
        self.enabled = True
        return True

    def close(self):
        if self.manager:
            self.manager.close()
            self.manager = None
        self.enabled = False
