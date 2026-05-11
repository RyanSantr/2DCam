from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class SetupWizard(tk.Toplevel):
    """Janela curta de primeiros passos para preparar uma live sem procurar menus."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        choose_idle: Callable[[], None],
        choose_talk: Callable[[], None],
        toggle_microphone: Callable[[], None],
        calibrate: Callable[[], None],
        open_obs: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("Setup guiado")
        self.geometry("460x430")
        self.minsize(420, 390)
        self.transient(master)
        self.configure(bg=getattr(master, "colors", {}).get("bg", "#111827"))

        self.columnconfigure(0, weight=1)
        frame = ttk.Frame(self, padding=18)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        ttk.Label(frame, text="Setup rapido", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(
            frame,
            text="Prepare o avatar, o microfone e a janela do OBS em poucos cliques.",
            style="Body.TLabel",
            wraplength=390,
        ).grid(row=1, column=0, sticky="w", pady=(0, 14))

        steps = ttk.LabelFrame(frame, text="Passos recomendados", padding=12)
        steps.grid(row=2, column=0, sticky="ew")
        steps.columnconfigure(0, weight=1)

        self._add_action(steps, 0, "1. Escolher imagens idle", choose_idle)
        self._add_action(steps, 1, "2. Escolher imagens falando", choose_talk)
        self._add_action(steps, 2, "3. Ativar microfone", toggle_microphone)
        self._add_action(steps, 3, "4. Calibrar ruido ambiente", calibrate)
        self._add_action(steps, 4, "5. Abrir janela OBS", open_obs)

        ttk.Label(
            frame,
            text="Dica: depois salve um perfil para guardar esse conjunto de imagens e ajustes.",
            style="Body.TLabel",
            wraplength=390,
        ).grid(row=3, column=0, sticky="w", pady=(14, 10))
        ttk.Button(frame, text="Fechar", command=self.destroy).grid(row=4, column=0, sticky="ew")

    def _add_action(self, parent: ttk.Frame, row: int, text: str, command: Callable[[], None]) -> None:
        button = ttk.Button(parent, text=text, command=command)
        button.grid(row=row, column=0, sticky="ew", pady=4)
