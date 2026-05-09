from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from typing import Any

from avatarcam.ui.theme import BACKGROUNDS


class AvatarCanvas(tk.Canvas):
    """Avatar 2D desenhado em Canvas, pronto para trocar por sprites no futuro."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, highlightthickness=0, **kwargs)
        self.avatar = {}
        self.idle_paths: list[str] = []
        self.speaking_paths: dict[str, list[str]] = {"low": [], "mid": [], "high": []}
        self.idle_frames: list[tk.PhotoImage] = []
        self.speaking_frames: dict[str, list[tk.PhotoImage]] = {"low": [], "mid": [], "high": []}
        self._fit_cache: dict[tuple[str, int, int, int], tk.PhotoImage] = {}
        self.animation_fps = 12
        self.speaking = False
        self.level = 0.0
        self.frame = 0
        self.background = "studio"
        self.bind("<Configure>", self._handle_resize)

    def set_avatar(self, avatar: dict) -> None:
        self.avatar = avatar
        self.draw()

    def set_image_sets(
        self,
        idle_paths: list[str],
        speaking_paths: list[str],
        low_paths: list[str] | None = None,
        mid_paths: list[str] | None = None,
        high_paths: list[str] | None = None,
    ) -> None:
        self.idle_paths = idle_paths
        self.speaking_paths = {
            "low": low_paths or speaking_paths,
            "mid": mid_paths or speaking_paths,
            "high": high_paths or speaking_paths,
        }
        self.idle_frames = self._load_images(idle_paths)
        self.speaking_frames = {
            name: self._load_images(paths)
            for name, paths in self.speaking_paths.items()
        }
        self._fit_cache.clear()
        self.draw()

    def set_animation_fps(self, fps: int) -> None:
        self.animation_fps = max(1, min(30, fps))

    def set_background(self, background: str) -> None:
        self.background = background
        self.draw()

    def update_state(self, speaking: bool, level: float) -> None:
        self.speaking = speaking
        self.level = level
        self.frame += 1
        self.draw()

    def _handle_resize(self, _event: tk.Event) -> None:
        self._fit_cache.clear()
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
        if self._draw_custom_image(cx, cy):
            return

        self._draw_empty_state(cx, cy, scale)

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

    def _load_images(self, paths: list[str]) -> list[tk.PhotoImage]:
        frames: list[tk.PhotoImage] = []
        for path in paths:
            try:
                if Path(path).is_file():
                    frames.append(tk.PhotoImage(file=path))
            except tk.TclError:
                continue
        return frames

    def _draw_custom_image(self, cx: float, cy: float) -> bool:
        frames = self._current_frames()
        if not frames:
            return False

        step = max(1, int(60 / self.animation_fps))
        image = frames[(self.frame // step) % len(frames)]
        image = self._fit_image(image)
        self.create_image(cx, cy, image=image, anchor=tk.CENTER)
        self._last_drawn_image = image
        return True

    def _current_frames(self) -> list[tk.PhotoImage]:
        if not self.speaking:
            return self.idle_frames

        if self.level >= 0.45:
            return self.speaking_frames["high"] or self.speaking_frames["mid"] or self.speaking_frames["low"] or self.idle_frames
        if self.level >= 0.22:
            return self.speaking_frames["mid"] or self.speaking_frames["low"] or self.idle_frames
        return self.speaking_frames["low"] or self.idle_frames

    def _fit_image(self, image: tk.PhotoImage) -> tk.PhotoImage:
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        max_w = max(1, int(w * 0.86))
        max_h = max(1, int(h * 0.86))
        iw = max(1, image.width())
        ih = max(1, image.height())

        if iw <= max_w and ih <= max_h:
            return image

        factor = max(1, math.ceil(max(iw / max_w, ih / max_h)))
        key = (str(image), factor, max_w, max_h)
        if key not in self._fit_cache:
            self._fit_cache[key] = image.subsample(factor, factor)
        return self._fit_cache[key]

    def _draw_empty_state(self, cx: float, cy: float, scale: float) -> None:
        def p(value: float) -> float:
            return value * scale

        self.create_oval(cx - p(92), cy - p(92), cx + p(92), cy + p(92), fill="#243047", outline="#60708f", width=max(2, int(p(3))))
        self.create_line(cx - p(38), cy - p(16), cx + p(38), cy - p(16), fill="#9fb0cf", width=max(2, int(p(5))))
        self.create_line(cx, cy - p(54), cx, cy + p(22), fill="#9fb0cf", width=max(2, int(p(5))))
        self.create_text(
            cx,
            cy + p(135),
            text="Selecione imagens de idle e fala",
            fill="#ffffff",
            font=("Segoe UI", max(10, int(p(13))), "bold"),
        )
