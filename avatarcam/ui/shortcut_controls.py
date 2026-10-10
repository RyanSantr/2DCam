from tkinter import messagebox
from avatarcam.ui.shortcut_defaults import DEFAULT_HOTKEYS, HOTKEY_ACTION_LABELS


class ShortcutControls:
    def _bind_hotkeys(self) -> None:
        for sequence in self.local_hotkey_sequences:
            self.unbind_all(sequence)
        self.local_hotkey_sequences.clear()
        self.hotkeys.clear()
        used = set()
        for action, hotkey in self._hotkey_config().items():
            normalized = self._normalize_hotkey(hotkey)
            if not normalized or normalized in used:
                continue
            used.add(normalized)
            registered = self.hotkeys.register(normalized, lambda selected=action: self.enqueue_ui(lambda: self._run_hotkey_action(selected)))
            # O fallback local so existe quando o registro global falha.
            if not registered:
                sequence = self._tk_sequence_for_hotkey(normalized)
                if sequence:
                    self.bind_all(sequence, lambda e, selected=action: self._run_hotkey_action(selected))
                    self.local_hotkey_sequences.append(sequence)
        self._refresh_hotkey_label()

    def _hotkey_config(self) -> dict[str, str]:
        configured = self.settings.hotkeys or {}
        return {
            action: self._normalize_hotkey(str(configured.get(action, default)))
            for action, default in DEFAULT_HOTKEYS.items()
        }

    def _normalize_hotkey(self, value: str) -> str:
        return value.strip().lower().replace(" ", "").replace("control+", "ctrl+")

    def _tk_sequence_for_hotkey(self, hotkey: str) -> str | None:
        parts = [part for part in hotkey.split("+") if part]
        if not parts:
            return None
        key = parts[-1]
        modifiers = []
        for part in parts[:-1]:
            if part == "ctrl":
                modifiers.append("Control")
            elif part == "alt":
                modifiers.append("Alt")
            elif part == "shift":
                modifiers.append("Shift")
            else:
                return None
        if key.startswith("f") and key[1:].isdigit():
            key_name = key.upper()
        elif len(key) == 1:
            key_name = f"Key-{key}"
        else:
            key_name = key
        return "<" + "-".join([*modifiers, key_name]) + ">"

    def _run_hotkey_action(self, action: str) -> None:
        if action == "toggle_mic":
            self._toggle_microphone()
        elif action == "test_speech":
            self._trigger_test()
        elif action == "show_controls":
            self.show_controls()
        elif action == "toggle_obs":
            self._toggle_obs_window()
        elif action == "toggle_pet":
            self._toggle_pet()
        elif action == "live_mode":
            self._enable_live_mode()
        elif action.startswith("scene_"):
            try:
                self._load_scene_by_index(int(action.rsplit("_", 1)[1]))
            except ValueError:
                return

    def _save_hotkeys(self) -> None:
        configured = {action: self._normalize_hotkey(variable.get()) for action, variable in self.hotkey_vars.items()}
        values = [value for value in configured.values() if value]
        if len(values) != len(set(values)):
            messagebox.showerror('Atalhos', 'Duas acoes usam o mesmo atalho. Escolha uma combinacao diferente para cada acao.')
            return
        self.settings.hotkeys = configured
        self._bind_hotkeys()
        self._save_settings_file()
        self._set_status("Atalhos salvos", 2200)

    def _reset_hotkeys(self) -> None:
        for action, default in DEFAULT_HOTKEYS.items():
            self.hotkey_vars[action].set(default)
        self._save_hotkeys()

    def _refresh_hotkey_label(self) -> None:
        if not hasattr(self, "hotkey_label"):
            return
        enabled = sum(1 for value in self._hotkey_config().values() if value)
        scope = "globais ativos" if self.hotkeys.available else "fallback com janela focada"
        self.hotkey_label.configure(text=f"Atalhos: {enabled} configurados | {scope}")

