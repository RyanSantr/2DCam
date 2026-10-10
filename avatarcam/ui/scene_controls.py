from tkinter import messagebox, simpledialog


class SceneControls:
    def _scene_names(self) -> tuple[str, ...]:
        scenes = self.settings.scenes or {}
        defaults = [f"Cena {index}" for index in range(1, 5)]
        names = sorted(set(scenes.keys()) | set(defaults) | {self.settings.active_scene})
        return tuple(name for name in names if name)

    def _current_scene_data(self) -> dict:
        return {
            "avatar_scale": float(self.avatar_scale_var.get()),
            "avatar_offset_x": float(self.avatar_x_var.get()),
            "avatar_offset_y": float(self.avatar_y_var.get()),
            "avatar_rotation": float(self.avatar_rotation_var.get()),
            "animation_fps": int(float(self.animation_fps_var.get())),
            "idle_motion": self.idle_motion_var.get(),
            "avatar_shadow": self.avatar_shadow_var.get(),
            "obs_background": self.obs_background_var.get(),
            "obs_resolution": self.obs_resolution_var.get(),
            "obs_borderless": self.obs_borderless_var.get(),
            "obs_always_on_top": self.obs_top_var.get(),
            "pet_enabled": self.pet_enabled_var.get(),
            "pet_size": float(self.pet_size_var.get()),
            "pet_offset_x": float(self.pet_x_var.get()),
            "pet_offset_y": float(self.pet_y_var.get()),
            "pet_reaction": self.pet_reaction_var.get(),
            "pet_reaction_strength": float(self.pet_strength_var.get()),
            "pet_layer": self.pet_layer_var.get(),
            "pet_opacity": float(self.pet_opacity_var.get()),
            "pet_mirror": self.pet_mirror_var.get(),
        }

    def _refresh_scene_select(self) -> None:
        if hasattr(self, "scene_select"):
            self.scene_select.configure(values=self._scene_names())

    def _save_scene(self, name: str) -> None:
        name = (name or "").strip() or "Cena 1"
        scenes = self.settings.scenes or {}
        scenes[name] = self._current_scene_data()
        self.settings.scenes = scenes
        self.settings.active_scene = name
        self.scene_var.set(name)
        self._refresh_scene_select()
        self._save_settings_file()
        self._set_status(f"Cena salva: {name}", 2400)

    def _new_scene(self) -> None:
        name = simpledialog.askstring("Nova cena", "Nome da cena:", initialvalue=f"Cena {len(self._scene_names()) + 1}")
        if not name or not name.strip():
            return
        self.scene_var.set(name.strip())
        self._save_scene(name.strip())

    def _delete_scene(self) -> None:
        name = self.scene_var.get().strip()
        scenes = self.settings.scenes or {}
        if name not in scenes:
            messagebox.showinfo("Excluir cena", "Essa cena ainda nao foi salva.")
            return
        if not messagebox.askyesno("Excluir cena", f"Excluir a cena {name}?"):
            return
        scenes.pop(name, None)
        self.settings.scenes = scenes
        fallback_names = sorted(set(scenes.keys()) | {f"Cena {index}" for index in range(1, 5)})
        fallback = next(iter(fallback_names), "Cena 1")
        self.settings.active_scene = fallback
        self.scene_var.set(fallback)
        self._refresh_scene_select()
        self._save_settings_file()
        self._set_status(f"Cena excluida: {name}", 2400)

    def _load_scene_by_index(self, index: int) -> None:
        names = self._scene_names()
        if 0 <= index - 1 < len(names):
            self._apply_scene(names[index - 1])

    def _apply_scene(self, name: str) -> None:
        name = (name or "").strip()
        scene = (self.settings.scenes or {}).get(name)
        if not scene:
            self.scene_var.set(name or self.settings.active_scene)
            self._set_status("Cena ainda nao salva", 2200)
            return

        self.scene_var.set(name)
        self.avatar_scale_var.set(float(scene.get("avatar_scale", self.avatar_scale_var.get())))
        self.avatar_x_var.set(float(scene.get("avatar_offset_x", self.avatar_x_var.get())))
        self.avatar_y_var.set(float(scene.get("avatar_offset_y", self.avatar_y_var.get())))
        self.avatar_rotation_var.set(float(scene.get("avatar_rotation", self.avatar_rotation_var.get())))
        self.animation_fps_var.set(int(scene.get("animation_fps", self.animation_fps_var.get())))
        self.idle_motion_var.set(bool(scene.get("idle_motion", self.idle_motion_var.get())))
        self.avatar_shadow_var.set(bool(scene.get("avatar_shadow", self.avatar_shadow_var.get())))
        self.obs_background_var.set(scene.get("obs_background", self.obs_background_var.get()))
        self.obs_resolution_var.set(scene.get("obs_resolution", self.obs_resolution_var.get()))
        self.obs_borderless_var.set(bool(scene.get("obs_borderless", self.obs_borderless_var.get())))
        self.obs_top_var.set(bool(scene.get("obs_always_on_top", self.obs_top_var.get())))
        self.pet_enabled_var.set(bool(scene.get("pet_enabled", self.pet_enabled_var.get())))
        self.pet_size_var.set(float(scene.get("pet_size", self.pet_size_var.get())))
        self.pet_x_var.set(float(scene.get("pet_offset_x", self.pet_x_var.get())))
        self.pet_y_var.set(float(scene.get("pet_offset_y", self.pet_y_var.get())))
        self.pet_reaction_var.set(scene.get("pet_reaction", self.pet_reaction_var.get()))
        self.pet_strength_var.set(float(scene.get("pet_reaction_strength", self.pet_strength_var.get())))
        self.pet_layer_var.set(scene.get("pet_layer", self.pet_layer_var.get()))
        self.pet_opacity_var.set(float(scene.get("pet_opacity", self.pet_opacity_var.get())))
        self.pet_mirror_var.set(bool(scene.get("pet_mirror", self.pet_mirror_var.get())))
        self.settings.active_scene = name
        self._save_settings()
        self._save_obs_settings()
        self._set_status(f"Cena aplicada: {name}", 2200)

