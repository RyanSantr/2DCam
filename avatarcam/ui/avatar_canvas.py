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
        self.pet_paths: list[str] = []
        self.pet_frames: list[tk.PhotoImage] = []
        self._fit_cache: dict[tuple[str, int, int, int], tk.PhotoImage] = {}
        self.animation_fps = 12
        self.avatar_scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.idle_motion = True
        self.avatar_shadow = True
        self.pet_enabled = False
        self.pet_size = 0.85
        self.speaking = False
        self.level = 0.0
        self.frame = 0
        self._last_signature: tuple | None = None
        self.background = "studio"
        self.bind("<Configure>", self._handle_resize)

    def set_avatar(self, avatar: dict) -> None:
        self.avatar = avatar
        self.draw()

    def set_pet_images(self, pet_paths: list[str]) -> None:
        self.pet_paths = pet_paths
        self.pet_frames = self._load_images(pet_paths)
        self._fit_cache.clear()
        self._last_signature = None
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
        self._last_signature = None
        self.draw()

    def set_animation_fps(self, fps: int) -> None:
        self.animation_fps = max(1, min(30, fps))

    def set_transform(self, scale: float, offset_x: float, offset_y: float) -> None:
        self.avatar_scale = max(0.2, min(3.0, scale))
        self.offset_x = max(-0.8, min(0.8, offset_x))
        self.offset_y = max(-0.8, min(0.8, offset_y))
        self._fit_cache.clear()
        self._last_signature = None
        self.draw()

    def set_visual_options(
        self,
        idle_motion: bool,
        avatar_shadow: bool,
        pet_enabled: bool | None = None,
        pet_size: float | None = None,
    ) -> None:
        self.idle_motion = idle_motion
        self.avatar_shadow = avatar_shadow
        if pet_enabled is not None:
            self.pet_enabled = pet_enabled
        if pet_size is not None:
            self.pet_size = max(0.45, min(1.6, pet_size))
        self._last_signature = None
        self.draw()

    def set_background(self, background: str) -> None:
        self.background = background
        self._last_signature = None
        self.draw()

    def update_state(self, speaking: bool, level: float) -> None:
        self.speaking = speaking
        self.level = level
        self.frame += 1
        if not self._should_redraw():
            return
        self.draw()

    def _handle_resize(self, _event: tk.Event) -> None:
        self._fit_cache.clear()
        self._last_signature = None
        self.draw()

    def _should_redraw(self) -> bool:
        frames = self._current_frames()
        animated = self.idle_motion or self.pet_enabled or len(frames) > 1
        level_bucket = int(self.level * 10) if self.speaking else 0
        frame_bucket = (self.frame // max(1, int(30 / self.animation_fps))) if animated else 0
        signature = (
            self.speaking,
            level_bucket,
            frame_bucket,
            len(frames),
            self.background,
            self.pet_enabled,
            round(self.pet_size, 2),
            len(self.pet_frames),
        )
        if signature == self._last_signature:
            return False
        self._last_signature = signature
        return True

    def draw(self) -> None:
        self.delete("all")
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        cx = w / 2 + (w * self.offset_x * 0.5)
        scale = min(w / 430, h / 520) * self.avatar_scale
        idle_bob = math.sin(self.frame / 18) * 5 * scale if self.idle_motion else 0
        talk_bounce = min(1.0, self.level * 3) * 9 * scale if self.speaking and self.idle_motion else 0
        cy = h * 0.55 + (h * self.offset_y * 0.5) + idle_bob - talk_bounce

        self._draw_background(w, h)
        if self._draw_custom_image(cx, cy):
            self._draw_pet(w, h, scale)
            return

        self._draw_empty_state(cx, cy, scale)
        self._draw_pet(w, h, scale)

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
                    frames.extend(self._load_file_frames(path))
            except tk.TclError:
                continue
        return frames

    def _load_file_frames(self, path: str) -> list[tk.PhotoImage]:
        if Path(path).suffix.lower() != ".gif":
            return [tk.PhotoImage(file=path)]

        frames: list[tk.PhotoImage] = []
        for index in range(80):
            try:
                frames.append(tk.PhotoImage(file=path, format=f"gif -index {index}"))
            except tk.TclError:
                break
        return frames or [tk.PhotoImage(file=path)]

    def _draw_custom_image(self, cx: float, cy: float) -> bool:
        frames = self._current_frames()
        if not frames:
            return False

        step = max(1, int(30 / self.animation_fps))
        image = frames[(self.frame // step) % len(frames)]
        image = self._fit_image(image)
        if self.avatar_shadow:
            self.create_oval(
                cx - image.width() * 0.36,
                cy + image.height() * 0.36,
                cx + image.width() * 0.36,
                cy + image.height() * 0.47,
                fill="#000000",
                outline="",
            )
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
        max_w = max(1, int(w * 0.86 * self.avatar_scale))
        max_h = max(1, int(h * 0.86 * self.avatar_scale))
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

    def _draw_pet(self, w: int, h: int, avatar_scale: float) -> None:
        if not self.pet_enabled:
            return

        base = max(0.55, min(1.35, avatar_scale)) * self.pet_size
        size = max(34, min(w, h) * 0.13 * base)
        margin = max(12, size * 0.28)
        t = self.frame
        mood_cycle = (t // 180) % 4
        reacting = self.speaking and self.level > 0.08

        x = w - margin - size * 0.7
        y = h - margin - size * 0.55
        if mood_cycle == 1:
            y += math.sin(t / 5) * size * 0.10
        elif mood_cycle == 2 and not reacting:
            y += size * 0.10
        elif mood_cycle == 3:
            x += math.sin(t / 18) * size * 0.10

        if reacting:
            y -= min(1.0, self.level * 2.8) * size * 0.22

        if self.pet_frames:
            self._draw_pet_image(x, y, size, reacting)
            return

        blink = (t % 140) > 132
        sleepy = mood_cycle == 2 and not reacting
        happy = reacting or mood_cycle == 1
        tail_angle = math.sin(t / (4 if reacting else 9)) * size * 0.22

        shadow_y = y + size * 0.48
        self.create_oval(
            x - size * 0.7,
            shadow_y - size * 0.09,
            x + size * 0.72,
            shadow_y + size * 0.08,
            fill="#000000",
            outline="",
            stipple="gray50",
        )

        body = "#7dd3fc" if reacting else "#8bd7a8"
        belly = "#f6f7db"
        accent = "#283246"
        ear = "#5dbb86"
        if sleepy:
            body = "#9aa8c7"
            ear = "#7987a7"

        self.create_line(
            x + size * 0.50,
            y + size * 0.04,
            x + size * 0.78,
            y - size * 0.16 + tail_angle,
            x + size * 0.60,
            y - size * 0.30 + tail_angle,
            fill=accent,
            width=max(2, int(size * 0.08)),
            smooth=True,
        )
        self.create_oval(x - size * 0.58, y - size * 0.28, x + size * 0.58, y + size * 0.50, fill=body, outline=accent, width=max(1, int(size * 0.025)))
        self.create_oval(x - size * 0.33, y - size * 0.05, x + size * 0.33, y + size * 0.45, fill=belly, outline="")
        self.create_polygon(
            x - size * 0.42,
            y - size * 0.20,
            x - size * 0.26,
            y - size * 0.70,
            x - size * 0.08,
            y - size * 0.18,
            fill=ear,
            outline=accent,
        )
        self.create_polygon(
            x + size * 0.42,
            y - size * 0.20,
            x + size * 0.26,
            y - size * 0.70,
            x + size * 0.08,
            y - size * 0.18,
            fill=ear,
            outline=accent,
        )
        self.create_oval(x - size * 0.42, y - size * 0.58, x + size * 0.42, y + size * 0.08, fill=body, outline=accent, width=max(1, int(size * 0.025)))

        if blink or sleepy:
            self.create_line(x - size * 0.20, y - size * 0.25, x - size * 0.08, y - size * 0.25, fill=accent, width=max(1, int(size * 0.03)))
            self.create_line(x + size * 0.08, y - size * 0.25, x + size * 0.20, y - size * 0.25, fill=accent, width=max(1, int(size * 0.03)))
        else:
            self.create_oval(x - size * 0.22, y - size * 0.31, x - size * 0.08, y - size * 0.16, fill=accent, outline="")
            self.create_oval(x + size * 0.08, y - size * 0.31, x + size * 0.22, y - size * 0.16, fill=accent, outline="")

        self.create_oval(x - size * 0.05, y - size * 0.13, x + size * 0.05, y - size * 0.04, fill=accent, outline="")
        if happy:
            self.create_arc(x - size * 0.17, y - size * 0.09, x + size * 0.17, y + size * 0.15, start=205, extent=130, outline=accent, width=max(1, int(size * 0.025)), style=tk.ARC)
        else:
            self.create_line(x - size * 0.10, y + size * 0.07, x + size * 0.10, y + size * 0.07, fill=accent, width=max(1, int(size * 0.025)))

    def _draw_pet_image(self, x: float, y: float, size: float, reacting: bool) -> None:
        step = max(1, int(30 / max(1, self.animation_fps)))
        image = self.pet_frames[(self.frame // step) % len(self.pet_frames)]
        image = self._fit_pet_image(image, size)
        if self.avatar_shadow:
            self.create_oval(
                x - image.width() * 0.36,
                y + image.height() * 0.34,
                x + image.width() * 0.36,
                y + image.height() * 0.46,
                fill="#000000",
                outline="",
            )
        angle_offset = math.sin(self.frame / (5 if reacting else 12)) * size * 0.04
        self.create_image(x + angle_offset, y, image=image, anchor=tk.CENTER)
        self._last_drawn_pet_image = image

    def _fit_pet_image(self, image: tk.PhotoImage, size: float) -> tk.PhotoImage:
        max_w = max(1, int(size * 1.5))
        max_h = max(1, int(size * 1.5))
        iw = max(1, image.width())
        ih = max(1, image.height())
        if iw <= max_w and ih <= max_h:
            return image

        factor = max(1, math.ceil(max(iw / max_w, ih / max_h)))
        key = (str(image), factor, max_w, max_h)
        if key not in self._fit_cache:
            self._fit_cache[key] = image.subsample(factor, factor)
        return self._fit_cache[key]
