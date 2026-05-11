from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from typing import Any

from avatarcam.ui.theme import BACKGROUNDS


MAX_GIF_FRAMES = 48
MAX_FIT_CACHE = 96


class AvatarCanvas(tk.Canvas):
    """Avatar 2D desenhado em Canvas, pronto para trocar por sprites no futuro."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, highlightthickness=0, **kwargs)
        self.avatar = {}
        self.idle_paths: list[str] = []
        self.speaking_paths: dict[str, list[str]] = {"low": [], "mid": [], "high": []}
        self.idle_frames: list[tk.PhotoImage] = []
        self.speaking_frames: dict[str, list[tk.PhotoImage]] = {"low": [], "mid": [], "high": []}
        self.idle_pil_frames: list[Any] = []
        self.speaking_pil_frames: dict[str, list[Any]] = {"low": [], "mid": [], "high": []}
        self.pet_paths: list[str] = []
        self.pet_speaking_paths: list[str] = []
        self.pet_loud_paths: list[str] = []
        self.pet_frames: list[tk.PhotoImage] = []
        self.pet_speaking_frames: list[tk.PhotoImage] = []
        self.pet_loud_frames: list[tk.PhotoImage] = []
        self.pet_pil_frames: list[Any] = []
        self.pet_speaking_pil_frames: list[Any] = []
        self.pet_loud_pil_frames: list[Any] = []
        self.blink_paths: list[str] = []
        self.blink_frames: list[tk.PhotoImage] = []
        self.blink_pil_frames: list[Any] = []
        self._fit_cache: dict[tuple[Any, ...], tk.PhotoImage] = {}
        self._pet_fit_cache: dict[tuple[int, int, float, bool], tk.PhotoImage] = {}
        self.animation_fps = 12
        self.avatar_scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.avatar_rotation = 0.0
        self.idle_motion = True
        self.avatar_shadow = True
        self.pet_enabled = False
        self.pet_size = 0.85
        self.pet_offset_x = 0.72
        self.pet_offset_y = 0.62
        self.pet_reaction = "bounce"
        self.pet_reaction_strength = 0.55
        self.pet_layer = "front"
        self.pet_opacity = 1.0
        self.pet_mirror = False
        self.speaking = False
        self.level = 0.0
        self.frame = 0
        self._last_signature: tuple | None = None
        self.background = "studio"
        self.bind("<Configure>", self._handle_resize)

    def set_avatar(self, avatar: dict) -> None:
        self.avatar = avatar
        self.draw()

    def set_pet_images(
        self,
        pet_paths: list[str],
        speaking_paths: list[str] | None = None,
        loud_paths: list[str] | None = None,
    ) -> None:
        next_pet = list(pet_paths)
        next_speaking = list(speaking_paths or [])
        next_loud = list(loud_paths or [])
        if (
            self.pet_paths == next_pet
            and self.pet_speaking_paths == next_speaking
            and self.pet_loud_paths == next_loud
        ):
            return

        self.pet_paths = next_pet
        self.pet_speaking_paths = next_speaking
        self.pet_loud_paths = next_loud
        self.pet_frames = self._load_images(pet_paths)
        self.pet_speaking_frames = self._load_images(self.pet_speaking_paths)
        self.pet_loud_frames = self._load_images(self.pet_loud_paths)
        self.pet_pil_frames = self._load_pil_frames(pet_paths)
        self.pet_speaking_pil_frames = self._load_pil_frames(self.pet_speaking_paths)
        self.pet_loud_pil_frames = self._load_pil_frames(self.pet_loud_paths)
        self._fit_cache.clear()
        self._pet_fit_cache.clear()
        self._last_signature = None
        self.draw()

    def set_image_sets(
        self,
        idle_paths: list[str],
        speaking_paths: list[str],
        low_paths: list[str] | None = None,
        mid_paths: list[str] | None = None,
        high_paths: list[str] | None = None,
        blink_paths: list[str] | None = None,
    ) -> None:
        next_idle = list(idle_paths)
        next_speaking = {
            "low": list(low_paths or speaking_paths),
            "mid": list(mid_paths or speaking_paths),
            "high": list(high_paths or speaking_paths),
        }
        next_blink = list(blink_paths or [])
        if self.idle_paths == next_idle and self.speaking_paths == next_speaking and self.blink_paths == next_blink:
            return

        self.idle_paths = next_idle
        self.speaking_paths = next_speaking
        self.idle_frames = self._load_images(self.idle_paths)
        self.speaking_frames = {
            name: self._load_images(paths)
            for name, paths in self.speaking_paths.items()
        }
        self.idle_pil_frames = self._load_pil_frames(self.idle_paths)
        self.speaking_pil_frames = {
            name: self._load_pil_frames(paths)
            for name, paths in self.speaking_paths.items()
        }
        self.blink_paths = next_blink
        self.blink_frames = self._load_images(self.blink_paths)
        self.blink_pil_frames = self._load_pil_frames(self.blink_paths)
        self._fit_cache.clear()
        self._last_signature = None
        self.draw()

    def set_animation_fps(self, fps: int) -> None:
        next_fps = max(1, min(30, fps))
        if self.animation_fps == next_fps:
            return
        self.animation_fps = next_fps
        self._last_signature = None

    def set_transform(self, scale: float, offset_x: float, offset_y: float, rotation: float = 0.0) -> None:
        next_scale = max(0.2, min(3.0, scale))
        next_x = max(-0.8, min(0.8, offset_x))
        next_y = max(-0.8, min(0.8, offset_y))
        next_rotation = max(-45.0, min(45.0, rotation))
        if (
            self.avatar_scale == next_scale
            and self.offset_x == next_x
            and self.offset_y == next_y
            and self.avatar_rotation == next_rotation
        ):
            return
        self.avatar_scale = next_scale
        self.offset_x = next_x
        self.offset_y = next_y
        self.avatar_rotation = next_rotation
        self._fit_cache.clear()
        self._last_signature = None
        self.draw()

    def set_visual_options(
        self,
        idle_motion: bool,
        avatar_shadow: bool,
        pet_enabled: bool | None = None,
        pet_size: float | None = None,
        pet_offset_x: float | None = None,
        pet_offset_y: float | None = None,
        pet_reaction: str | None = None,
        pet_reaction_strength: float | None = None,
        pet_layer: str | None = None,
        pet_opacity: float | None = None,
        pet_mirror: bool | None = None,
    ) -> None:
        old_pet_size = self.pet_size
        old_pet_opacity = self.pet_opacity
        old_pet_mirror = self.pet_mirror
        old_values = (
            self.idle_motion,
            self.avatar_shadow,
            self.pet_enabled,
            self.pet_size,
            self.pet_offset_x,
            self.pet_offset_y,
            self.pet_reaction,
            self.pet_reaction_strength,
            self.pet_layer,
            self.pet_opacity,
            self.pet_mirror,
        )
        self.idle_motion = idle_motion
        self.avatar_shadow = avatar_shadow
        if pet_enabled is not None:
            self.pet_enabled = pet_enabled
        if pet_size is not None:
            self.pet_size = max(0.45, min(1.6, pet_size))
        if pet_offset_x is not None:
            self.pet_offset_x = max(-0.9, min(0.9, pet_offset_x))
        if pet_offset_y is not None:
            self.pet_offset_y = max(-0.9, min(0.9, pet_offset_y))
        if pet_reaction is not None:
            self.pet_reaction = pet_reaction
        if pet_reaction_strength is not None:
            self.pet_reaction_strength = max(0.0, min(1.0, pet_reaction_strength))
        if pet_layer is not None:
            self.pet_layer = pet_layer
        if pet_opacity is not None:
            self.pet_opacity = max(0.05, min(1.0, pet_opacity))
        if pet_mirror is not None:
            self.pet_mirror = pet_mirror

        new_values = (
            self.idle_motion,
            self.avatar_shadow,
            self.pet_enabled,
            self.pet_size,
            self.pet_offset_x,
            self.pet_offset_y,
            self.pet_reaction,
            self.pet_reaction_strength,
            self.pet_layer,
            self.pet_opacity,
            self.pet_mirror,
        )
        if old_values == new_values:
            return
        if old_pet_size != self.pet_size or old_pet_opacity != self.pet_opacity or old_pet_mirror != self.pet_mirror:
            self._pet_fit_cache.clear()
        self._last_signature = None
        self.draw()

    def set_background(self, background: str) -> None:
        if self.background == background:
            return
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
            len(self.blink_frames),
            self.background,
            round(self.avatar_scale, 2),
            round(self.offset_x, 2),
            round(self.offset_y, 2),
            round(self.avatar_rotation, 1),
            self.pet_enabled,
            round(self.pet_size, 2),
            round(self.pet_offset_x, 2),
            round(self.pet_offset_y, 2),
            self.pet_reaction,
            round(self.pet_reaction_strength, 2),
            self.pet_layer,
            round(self.pet_opacity, 2),
            self.pet_mirror,
            len(self.pet_frames),
            len(self.pet_speaking_frames),
            len(self.pet_loud_frames),
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
        if self.pet_layer == "back":
            self._draw_pet(w, h, scale)
        if self._draw_custom_image(cx, cy):
            if self.pet_layer != "back":
                self._draw_pet(w, h, scale)
            return

        self._draw_empty_state(cx, cy, scale)
        if self.pet_layer != "back":
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
        for index in range(MAX_GIF_FRAMES):
            try:
                frames.append(tk.PhotoImage(file=path, format=f"gif -index {index}"))
            except tk.TclError:
                break
        return frames or [tk.PhotoImage(file=path)]

    def _load_pil_frames(self, paths: list[str]) -> list[Any]:
        try:
            from PIL import Image, ImageSequence
        except Exception:
            return []
        frames: list[Any] = []
        for path in paths:
            file_path = Path(path)
            if not file_path.is_file():
                continue
            try:
                with Image.open(file_path) as image:
                    if file_path.suffix.lower() == ".gif":
                        for frame in ImageSequence.Iterator(image):
                            frames.append(frame.convert("RGBA").copy())
                            if len(frames) >= MAX_GIF_FRAMES:
                                break
                    else:
                        frames.append(image.convert("RGBA").copy())
            except Exception:
                continue
        return frames

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

    def _current_frames(self) -> list[Any]:
        if not self.speaking:
            if (self.blink_pil_frames or self.blink_frames) and self.frame % 190 > 178:
                return self.blink_pil_frames or self.blink_frames
            return self.idle_pil_frames or self.idle_frames

        if self.level >= 0.45:
            return (
                self.speaking_pil_frames["high"]
                or self.speaking_pil_frames["mid"]
                or self.speaking_pil_frames["low"]
                or self.speaking_frames["high"]
                or self.speaking_frames["mid"]
                or self.speaking_frames["low"]
                or self.idle_pil_frames
                or self.idle_frames
            )
        if self.level >= 0.22:
            return (
                self.speaking_pil_frames["mid"]
                or self.speaking_pil_frames["low"]
                or self.speaking_frames["mid"]
                or self.speaking_frames["low"]
                or self.idle_pil_frames
                or self.idle_frames
            )
        return self.speaking_pil_frames["low"] or self.speaking_frames["low"] or self.idle_pil_frames or self.idle_frames

    def _fit_image(self, image: Any) -> tk.PhotoImage:
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        max_w = max(1, int(w * 0.86 * self.avatar_scale))
        max_h = max(1, int(h * 0.86 * self.avatar_scale))
        if not isinstance(image, tk.PhotoImage):
            try:
                from PIL import Image, ImageTk

                key = (id(image), max_w, max_h, round(self.avatar_rotation, 1))
                if key not in self._fit_cache:
                    if len(self._fit_cache) > MAX_FIT_CACHE:
                        self._fit_cache.clear()
                    pil_image = image.copy()
                    pil_image.thumbnail((max_w, max_h))
                    if abs(self.avatar_rotation) > 0.05:
                        resampling = getattr(Image, "Resampling", Image).BICUBIC
                        pil_image = pil_image.rotate(-self.avatar_rotation, expand=True, resample=resampling)
                    self._fit_cache[key] = ImageTk.PhotoImage(pil_image)
                return self._fit_cache[key]
            except Exception:
                pass

        iw = max(1, image.width())
        ih = max(1, image.height())

        if iw <= max_w and ih <= max_h:
            return image

        factor = max(1, math.ceil(max(iw / max_w, ih / max_h)))
        key = (str(image), factor, max_w, max_h)
        if key not in self._fit_cache:
            if len(self._fit_cache) > MAX_FIT_CACHE:
                self._fit_cache.clear()
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
        frames = self._current_pet_frames()
        if not self.pet_enabled or not frames:
            return

        base = max(0.55, min(1.35, avatar_scale)) * self.pet_size
        size = max(34, min(w, h) * 0.13 * base)
        x = w * (0.5 + self.pet_offset_x * 0.5)
        y = h * (0.5 + self.pet_offset_y * 0.5)
        reacting = self.speaking and self.level > 0.08
        self._draw_pet_image(x, y, size, reacting, frames)

    def _current_pet_frames(self) -> list[Any]:
        if self.level >= 0.45 and (self.pet_loud_pil_frames or self.pet_loud_frames):
            return self.pet_loud_pil_frames or self.pet_loud_frames
        if self.speaking and (self.pet_speaking_pil_frames or self.pet_speaking_frames):
            return self.pet_speaking_pil_frames or self.pet_speaking_frames
        return self.pet_pil_frames or self.pet_frames

    def _draw_pet_image(self, x: float, y: float, size: float, reacting: bool, frames: list[Any]) -> None:
        speed_bonus = 1
        if reacting and self.pet_reaction in ("speed", "bounce_speed", "shake_speed"):
            speed_bonus = 2
        step = max(1, int(30 / max(1, self.animation_fps * speed_bonus)))
        source = frames[(self.frame // step) % len(frames)]
        image = self._fit_pet_image(source, size)
        if self.avatar_shadow:
            self.create_oval(
                x - image.width() * 0.36,
                y + image.height() * 0.34,
                x + image.width() * 0.36,
                y + image.height() * 0.46,
                fill="#000000",
                outline="",
            )
        if reacting:
            intensity = min(1.0, self.level * 2.8) * self.pet_reaction_strength
            if self.pet_reaction in ("bounce", "bounce_speed"):
                y -= intensity * size * 0.42
            elif self.pet_reaction in ("shake", "shake_speed"):
                x += math.sin(self.frame * 1.7) * size * 0.16 * intensity
                y += math.cos(self.frame * 1.1) * size * 0.08 * intensity
            elif self.pet_reaction == "float":
                y += math.sin(self.frame / 5) * size * 0.16 * intensity
        self.create_image(x, y, image=image, anchor=tk.CENTER)
        self._last_drawn_pet_image = image

    def _fit_pet_image(self, image: Any, size: float) -> tk.PhotoImage:
        max_w = max(1, int(size * 1.5))
        max_h = max(1, int(size * 1.5))
        if not isinstance(image, tk.PhotoImage):
            try:
                from PIL import ImageOps, ImageTk

                pil_image = image.copy()
                pil_image.thumbnail((max_w, max_h))
                if self.pet_mirror:
                    pil_image = ImageOps.mirror(pil_image)
                if self.pet_opacity < 0.99:
                    alpha = pil_image.getchannel("A").point(lambda value: int(value * self.pet_opacity))
                    pil_image.putalpha(alpha)
                key = (id(image), max_w, round(self.pet_opacity, 2), self.pet_mirror)
                if key not in self._pet_fit_cache:
                    if len(self._pet_fit_cache) > MAX_FIT_CACHE:
                        self._pet_fit_cache.clear()
                    self._pet_fit_cache[key] = ImageTk.PhotoImage(pil_image)
                return self._pet_fit_cache[key]
            except Exception:
                pass

        iw = max(1, image.width())
        ih = max(1, image.height())
        if iw <= max_w and ih <= max_h:
            return image

        factor = max(1, math.ceil(max(iw / max_w, ih / max_h)))
        key = (str(image), factor, max_w, max_h)
        if key not in self._fit_cache:
            if len(self._fit_cache) > MAX_FIT_CACHE:
                self._fit_cache.clear()
            self._fit_cache[key] = image.subsample(factor, factor)
        return self._fit_cache[key]
