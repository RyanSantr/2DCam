from __future__ import annotations


class HotkeyManager:
    """Registra hotkeys globais quando permitido pelo Windows."""

    def __init__(self) -> None:
        self._keyboard = None
        self._handles = []
        try:
            import keyboard

            self._keyboard = keyboard
        except Exception:
            self._keyboard = None

    @property
    def available(self) -> bool:
        return self._keyboard is not None

    def register(self, hotkey: str, callback) -> None:
        if not self._keyboard or not hotkey.strip():
            return
        try:
            handle = self._keyboard.add_hotkey(hotkey, callback)
            self._handles.append(handle)
        except Exception:
            pass

    def clear(self) -> None:
        if not self._keyboard:
            return
        for handle in self._handles:
            try:
                self._keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._handles.clear()

    def close(self) -> None:
        self.clear()
