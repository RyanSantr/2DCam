from __future__ import annotations


class HotkeyManager:
    """Registra hotkeys globais quando permitido pelo Windows."""

    def __init__(self) -> None:
        self._keyboard = None
        self._handles = []
        self._key_handles = []
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
            if hotkey.lower() in ('up', 'down', 'left', 'right'):
                # OBS aceita setas mesmo com W/A/S/D pressionados no jogo.
                # O matcher de combinações exige todas as outras teclas soltas.
                def trigger(_event):
                    if not any(self._keyboard.is_pressed(key) for key in ('ctrl','alt','shift','windows')):
                        callback()
                register = self._keyboard.on_release_key if on_release else self._keyboard.on_press_key
                self._key_handles.append(register(hotkey.lower(), trigger, suppress=False))
                return True
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
        for handle in self._key_handles:
            try:
                self._keyboard.unhook_key(handle)
            except Exception:
                pass
        self._key_handles.clear()
        for handle in self._handles:
            try:
                self._keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._handles.clear()

    def close(self) -> None:
        self.clear()
