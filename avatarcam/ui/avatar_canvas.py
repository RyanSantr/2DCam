from __future__ import annotations

import math
import tkinter as tk
from typing import Any

from avatarcam.ui.theme import BACKGROUNDS


class AvatarCanvas(tk.Canvas):
    """Avatar 2D desenhado em Canvas, pronto para trocar por sprites no futuro."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, highlightthickness=0, **kwargs)
        self.avatar = {}
        self.speaking = False
        self.level = 0.0
        self.frame = 0
        self.background = "studio"
        self.bind("<Configure>", lambda _event: self.draw())

    def set_avatar(self, avatar: dict) -> None:
        self.avatar = avatar
        self.draw()

    def set_background(self, background: str) -> None:
        self.background = background
        self.draw()

    def update_state(self, speaking: bool, level: float) -> None:
        self.speaking = speaking
        self.level = level
        self.frame += 1
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        cx = w / 2
        scale = min(w / 430, h / 520)
        idle_bob = math.sin(self.frame / 18) * 5 * scale
        talk_bounce = min(1.0, self.level * 3) * 9 * scale if self.speaking else 0
        cy = h * 0.55 + idle_bob - talk_bounce

        self._draw_background(w, h)
        self._draw_avatar(cx, cy, scale)

    def _draw_background(self, w: int, h: int) -> None:
        top, bottom = BACKGROUNDS.get(self.background, BACKGROUNDS["studio"])
        self.create_rectangle(0, 0, w, h, fill=top, outline="")
        if self.background.startswith("chroma_") or self.background == "obs_black":
            return

        self.create_oval(-w * 0.15, h * 0.15, w * 0.55, h * 0.85, fill=bottom, outline="")
        self.create_oval(w * 0.45, -h * 0.1, w * 1.18, h * 0.65, fill=bottom, outline="")

        if self.background == "grid":
            for x in range(0, w, 42):
                self.create_line(x, 0, x, h, fill="#2b3a50", width=1)
            for y in range(0, h, 42):
                self.create_line(0, y, w, y, fill="#2b3a50", width=1)

    def _draw_avatar(self, cx: float, cy: float, scale: float) -> None:
        skin = self.avatar.get("skin", "#f7c7a5")
        hair = self.avatar.get("hair", "#35253e")
        shirt = self.avatar.get("shirt", "#2f7dd1")
        accent = self.avatar.get("accent", "#53e0c2")
        eye = self.avatar.get("eye", "#171923")

        def p(value: float) -> float:
            return value * scale

        # Corpo e pescoco.
        self.create_oval(cx - p(118), cy + p(86), cx + p(118), cy + p(250), fill=shirt, outline="")
        self.create_rectangle(cx - p(34), cy + p(54), cx + p(34), cy + p(124), fill=skin, outline="")
        self.create_oval(cx - p(38), cy + p(92), cx + p(38), cy + p(142), fill=skin, outline="")

        # Cabeca, cabelo e orelhas.
        self.create_oval(cx - p(110), cy - p(138), cx + p(110), cy + p(92), fill=skin, outline="")
        self.create_oval(cx - p(124), cy - p(22), cx - p(94), cy + p(34), fill=skin, outline="")
        self.create_oval(cx + p(94), cy - p(22), cx + p(124), cy + p(34), fill=skin, outline="")
        self.create_arc(cx - p(116), cy - p(150), cx + p(116), cy + p(18), start=0, extent=180, fill=hair, outline=hair)
        self.create_polygon(
            cx - p(105), cy - p(48),
            cx - p(58), cy - p(132),
            cx - p(8), cy - p(48),
            cx + p(42), cy - p(132),
            cx + p(102), cy - p(42),
            fill=hair,
            outline="",
        )

        # Olhos e sobrancelhas.
        blink = abs(math.sin(self.frame / 70)) > 0.985
        eye_h = p(3 if blink else 22)
        self.create_oval(cx - p(58), cy - p(32), cx - p(24), cy - p(32) + eye_h, fill=eye, outline="")
        self.create_oval(cx + p(24), cy - p(32), cx + p(58), cy - p(32) + eye_h, fill=eye, outline="")
        self.create_line(cx - p(66), cy - p(52), cx - p(22), cy - p(58), fill=hair, width=max(2, int(p(4))))
        self.create_line(cx + p(22), cy - p(58), cx + p(66), cy - p(52), fill=hair, width=max(2, int(p(4))))

        # Boca muda de forma conforme fala e volume.
        if self.speaking:
            mouth_h = p(12 + min(1.0, self.level * 3.8) * 42)
            self.create_oval(cx - p(34), cy + p(26), cx + p(34), cy + p(26) + mouth_h, fill="#5b1b26", outline="")
            self.create_arc(cx - p(26), cy + p(34), cx + p(26), cy + p(60) + mouth_h, start=180, extent=180, fill="#ff8aa2", outline="")
        else:
            self.create_arc(cx - p(34), cy + p(20), cx + p(34), cy + p(58), start=200, extent=140, style=tk.ARC, outline="#8f4d48", width=max(2, int(p(4))))

        # Acessorio simples para dar identidade ao avatar.
        self.create_oval(cx + p(72), cy - p(112), cx + p(118), cy - p(66), fill=accent, outline="")
        self.create_text(cx + p(95), cy - p(90), text="*", fill="#ffffff", font=("Segoe UI", max(10, int(p(18))), "bold"))
