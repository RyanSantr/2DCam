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

    def register(self, hotkey: str, callback, on_release: bool = False) -> bool:
        if not self._keyboard or not hotkey.strip():
            return False
        try:
            handle = self._keyboard.add_hotkey(hotkey, callback, trigger_on_release=on_release)
            self._handles.append(handle)
            return True
        except Exception as exc:
            import logging
            logging.getLogger('avatarcam').warning('Atalho global %s indisponivel: %s', hotkey, exc)
            return False

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
