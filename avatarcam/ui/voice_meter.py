from __future__ import annotations

import tkinter as tk
from typing import Any


class VoiceMeter(tk.Canvas):
    """Medidor visual com volume, linha de sensibilidade e estado de fala."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, height=42, highlightthickness=0, **kwargs)
        self.level = 0.0
        self.sensitivity = 0.1
        self.speaking = False
        self.colors = {
            "track": "#202c42",
            "fill": "#2dd4bf",
            "hot": "#fb7185",
            "threshold": "#ffffff",
            "text": "#eef4ff",
            "muted": "#9aa7bd",
        }
        self._last_signature: tuple | None = None
        self.bind("<Configure>", lambda _event: self._draw(force=True))

    def set_theme(self, colors: dict[str, str]) -> None:
        self.colors = {
            "track": colors.get("panel_2", "#202c42"),
            "fill": colors.get("meter", "#2dd4bf"),
            "hot": colors.get("danger", "#fb7185"),
            "threshold": colors.get("text", "#ffffff"),
            "text": colors.get("text", "#eef4ff"),
            "muted": colors.get("muted", "#9aa7bd"),
        }
        self.configure(bg=colors.get("panel", colors.get("bg", "#111827")))
        self._draw(force=True)

    def set_level(self, level: float, sensitivity: float, speaking: bool) -> None:
        self.level = max(0.0, min(1.0, level))
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        self.speaking = speaking
        self._draw()

    def _draw(self, force: bool = False) -> None:
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        level_bucket = int(self.level * 100)
        sensitivity_bucket = int(self.sensitivity * 100)
        signature = (width, height, level_bucket, sensitivity_bucket, self.speaking)
        if not force and signature == self._last_signature:
            return
        self._last_signature = signature

        self.delete("all")
        pad = 8
        bar_h = 14
        y = 11
        right = width - pad
        track_w = max(1, right - pad)
        radius = 7
        self._rounded_rect(pad, y, right, y + bar_h, radius, self.colors["track"])

        fill_w = max(0, track_w * self.level)
        if fill_w > 0:
            color = self.colors["hot"] if self.speaking else self.colors["fill"]
            self._rounded_rect(pad, y, pad + fill_w, y + bar_h, radius, color)

        tx = pad + track_w * self.sensitivity
        self.create_line(tx, y - 4, tx, y + bar_h + 4, fill=self.colors["threshold"], width=2)
        label = "voz" if self.speaking else "ruido"
        self.create_text(pad, height - 8, text=f"{label}: {level_bucket}%", fill=self.colors["text"], anchor="w", font=("Segoe UI", 9, "bold"))
        self.create_text(right, height - 8, text=f"sens. {sensitivity_bucket}%", fill=self.colors["muted"], anchor="e", font=("Segoe UI", 9))

    def _rounded_rect(self, x1: float, y1: float, x2: float, y2: float, radius: float, fill: str) -> None:
        if x2 - x1 <= radius * 2:
            self.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
            return
        self.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        self.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="")
        self.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=fill, outline="")
        self.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=fill, outline="")
        self.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=fill, outline="")
        self.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=fill, outline="")
