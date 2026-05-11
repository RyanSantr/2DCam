from __future__ import annotations

import tkinter as tk

from avatarcam.ui.avatar_canvas import AvatarCanvas


class ObsOutputWindow(tk.Toplevel):
    """Janela limpa para captura no OBS via Window Capture."""

    def __init__(
        self,
        master: tk.Misc,
        idle_images: list[str],
        speaking_images: list[str],
        low_images: list[str],
        mid_images: list[str],
        high_images: list[str],
        blink_images: list[str],
        pet_images: list[str],
        pet_speaking_images: list[str],
        pet_loud_images: list[str],
        background: str,
        always_on_top: bool,
        animation_fps: int,
        resolution: str,
        borderless: bool,
    ) -> None:
        super().__init__(master)
        self.title("OBS Avatar Output")
        self.geometry(resolution)
        self.minsize(640, 360)
        self.configure(bg="#00ff00")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self.canvas = AvatarCanvas(self)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.set_image_sets(idle_images, speaking_images, low_images, mid_images, high_images, blink_images)
        self.canvas.set_pet_images(pet_images, pet_speaking_images, pet_loud_images)
        self.canvas.set_animation_fps(animation_fps)
        self.canvas.set_background(background)
        self.set_always_on_top(always_on_top)
        self.set_borderless(borderless)

        self.bind("<F10>", lambda _event: master.show_controls())

    def set_image_sets(
        self,
        idle_images: list[str],
        speaking_images: list[str],
        low_images: list[str],
        mid_images: list[str],
        high_images: list[str],
        blink_images: list[str] | None = None,
    ) -> None:
        self.canvas.set_image_sets(idle_images, speaking_images, low_images, mid_images, high_images, blink_images)

    def set_pet_images(
        self,
        pet_images: list[str],
        pet_speaking_images: list[str] | None = None,
        pet_loud_images: list[str] | None = None,
    ) -> None:
        self.canvas.set_pet_images(pet_images, pet_speaking_images, pet_loud_images)

    def set_animation_fps(self, fps: int) -> None:
        self.canvas.set_animation_fps(fps)

    def set_transform(self, scale: float, offset_x: float, offset_y: float, rotation: float = 0.0) -> None:
        self.canvas.set_transform(scale, offset_x, offset_y, rotation)

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
        self.canvas.set_visual_options(
            idle_motion,
            avatar_shadow,
            pet_enabled,
            pet_size,
            pet_offset_x,
            pet_offset_y,
            pet_reaction,
            pet_reaction_strength,
            pet_layer,
            pet_opacity,
            pet_mirror,
        )

    def set_background(self, background: str) -> None:
        self.canvas.set_background(background)

    def set_always_on_top(self, enabled: bool) -> None:
        self.attributes("-topmost", bool(enabled))
        if not enabled:
            self.lower()

    def set_borderless(self, enabled: bool) -> None:
        self.overrideredirect(bool(enabled))

    def set_resolution(self, resolution: str) -> None:
        self.geometry(resolution)

    def send_to_back(self) -> None:
        self.attributes("-topmost", False)
        self.lower()

    def update_state(self, speaking: bool, level: float) -> None:
        self.canvas.update_state(speaking, level)
