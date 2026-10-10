from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from avatarcam.core.avatar_pack import import_avatar_folder, import_avatar_pack, export_avatar_pack


class AssetControls:
    def _choose_idle_images(self) -> None:
        paths = self._pick_images("Escolha imagens idle")
        if not paths:
            return
        self.idle_images = paths
        self._save_image_sets()

    def _choose_speaking_images(self) -> None:
        paths = self._pick_images("Escolha imagens falando")
        if not paths:
            return
        self.speaking_images = paths
        self._save_image_sets()

    def _choose_level_images(self) -> None:
        low = self._pick_images("Escolha fala baixa")
        if low:
            self.speaking_low_images = low
        mid = self._pick_images("Escolha fala media")
        if mid:
            self.speaking_mid_images = mid
        high = self._pick_images("Escolha fala alta")
        if high:
            self.speaking_high_images = high
        self._save_image_sets()

    def _choose_blink_images(self) -> None:
        paths = self._pick_images("Escolha imagens de piscar")
        if not paths:
            return
        self.blink_images = paths
        self._save_image_sets()

    def _import_avatar_folder(self) -> None:
        folder = filedialog.askdirectory(title="Escolha a pasta do avatar")
        if not folder:
            return

        name = simpledialog.askstring("Nome do avatar", "Nome para salvar na biblioteca:", initialvalue=Path(folder).name)
        if not name:
            return
        self._run_job('Importando e otimizando avatar...', lambda: import_avatar_folder(folder, name), self._use_imported_sets)

    def _use_imported_sets(self, imported):
        self.idle_images = imported['idle']
        self.speaking_images = imported['talk']
        self.speaking_low_images = imported['talk_low']
        self.speaking_mid_images = imported['talk_mid']
        self.speaking_high_images = imported['talk_high']
        self.blink_images = imported.get('blink', [])
        self.pet_images = imported.get('pet', [])
        self.pet_speaking_images = imported.get('pet_talk', [])
        self.pet_loud_images = imported.get('pet_loud', [])
        self._save_image_sets()
        self._set_status('Avatar importado. Entradas anteriores foram preservadas.', 4000)

    def _export_pack(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Exportar avatarpack",
            defaultextension=".avatarpack",
            filetypes=(("Avatar pack", "*.avatarpack"), ("Zip", "*.zip")),
        )
        if not path:
            return
        export_avatar_pack(
            path,
            self._clean_profile_name(self.profile_var.get()) or "Avatar",
            self._current_image_sets(),
            {
                "sensitivity": float(self.sensitivity_var.get()),
                "smoothing": float(self.smoothing_var.get()),
                "animation_fps": int(float(self.animation_fps_var.get())),
                "avatar_scale": float(self.avatar_scale_var.get()),
                "avatar_offset_x": float(self.avatar_x_var.get()),
                "avatar_offset_y": float(self.avatar_y_var.get()),
                "avatar_rotation": float(self.avatar_rotation_var.get()),
                "idle_motion": self.idle_motion_var.get(),
                "avatar_shadow": self.avatar_shadow_var.get(),
                "pet_enabled": self.pet_enabled_var.get(),
                "pet_size": float(self.pet_size_var.get()),
                "pet_offset_x": float(self.pet_x_var.get()),
                "pet_offset_y": float(self.pet_y_var.get()),
                "pet_reaction": self.pet_reaction_var.get(),
                "pet_reaction_strength": float(self.pet_strength_var.get()),
                "pet_layer": self.pet_layer_var.get(),
                "pet_opacity": float(self.pet_opacity_var.get()),
                "pet_mirror": self.pet_mirror_var.get(),
                'camera3d': self.settings.camera3d,
                'expression3d': self.settings.expression3d,
                'speech_mode': self.settings.speech_mode,
                "mouth_hold_ticks": int(float(self.mouth_hold_var.get())),
            },
            model_path=self.settings.avatar3d_path,
        )
        self._set_status("Avatarpack exportado")

    def _import_pack(self) -> None:
        path = filedialog.askopenfilename(
            title="Importar avatarpack",
            filetypes=(("Avatar pack", "*.avatarpack *.zip"), ("Todos os arquivos", "*.*")),
        )
        if not path:
            return
        self._run_job('Validando e importando avatarpack...', lambda: import_avatar_pack(path), self._use_imported_pack)

    def _use_imported_pack(self, pack):
        sets = pack['sets']
        self.idle_images = sets["idle"]
        self.speaking_images = sets["talk"]
        self.speaking_low_images = sets["talk_low"]
        self.speaking_mid_images = sets["talk_mid"]
        self.speaking_high_images = sets["talk_high"]
        self.blink_images = sets.get("blink", [])
        self.pet_images = sets.get("pet", [])
        self.pet_speaking_images = sets.get("pet_talk", [])
        self.pet_loud_images = sets.get("pet_loud", [])
        settings = pack.get("settings", {})
        self.sensitivity_var.set(float(settings.get("sensitivity", self.sensitivity_var.get())))
        self.smoothing_var.set(float(settings.get("smoothing", self.smoothing_var.get())))
        self.animation_fps_var.set(int(settings.get("animation_fps", self.animation_fps_var.get())))
        self.avatar_scale_var.set(float(settings.get("avatar_scale", self.avatar_scale_var.get())))
        self.avatar_x_var.set(float(settings.get("avatar_offset_x", self.avatar_x_var.get())))
        self.avatar_y_var.set(float(settings.get("avatar_offset_y", self.avatar_y_var.get())))
        self.avatar_rotation_var.set(float(settings.get("avatar_rotation", self.avatar_rotation_var.get())))
        self.idle_motion_var.set(bool(settings.get("idle_motion", self.idle_motion_var.get())))
        self.avatar_shadow_var.set(bool(settings.get("avatar_shadow", self.avatar_shadow_var.get())))
        self.pet_enabled_var.set(bool(settings.get("pet_enabled", self.pet_enabled_var.get())))
        self.pet_size_var.set(float(settings.get("pet_size", self.pet_size_var.get())))
        self.pet_x_var.set(float(settings.get("pet_offset_x", self.pet_x_var.get())))
        self.pet_y_var.set(float(settings.get("pet_offset_y", self.pet_y_var.get())))
        self.pet_reaction_var.set(settings.get("pet_reaction", self.pet_reaction_var.get()))
        self.pet_strength_var.set(float(settings.get("pet_reaction_strength", self.pet_strength_var.get())))
        self.pet_layer_var.set(settings.get("pet_layer", self.pet_layer_var.get()))
        self.pet_opacity_var.set(float(settings.get("pet_opacity", self.pet_opacity_var.get())))
        self.pet_mirror_var.set(bool(settings.get("pet_mirror", self.pet_mirror_var.get())))
        self.mouth_hold_var.set(int(settings.get("mouth_hold_ticks", self.mouth_hold_var.get())))
        self.settings.avatar3d_path = pack.get('model_path', '')
        self.settings.camera3d = settings.get('camera3d')
        self._camera_revision += 1
        self.expression3d_var.set(settings.get('expression3d', 'neutral'))
        self.speech_mode_var.set(settings.get('speech_mode', self.settings.speech_mode))
        self.model_label.configure(text=self._model_description())
        self._save_studio(True)
        self.profile_var.set(pack.get("name", "Imported"))
        self._save_settings()
        self._save_image_sets()
        self._save_profile()
        self._set_status("Avatarpack importado")

    def _current_image_sets(self) -> dict:
        return {
            "idle": self.idle_images,
            "talk": self.speaking_images,
            "talk_low": self.speaking_low_images,
            "talk_mid": self.speaking_mid_images,
            "talk_high": self.speaking_high_images,
            "blink": self.blink_images,
            "pet": self.pet_images,
            "pet_talk": self.pet_speaking_images,
            "pet_loud": self.pet_loud_images,
        }

    def _images_from_folder(self, folder: Path) -> list[str]:
        if not folder.is_dir():
            return []
        allowed = {".png", ".gif"}
        return [str(path) for path in sorted(folder.iterdir()) if path.suffix.lower() in allowed and path.is_file()]

    def _clear_images(self) -> None:
        self.idle_images = []
        self.speaking_images = []
        self.speaking_low_images = []
        self.speaking_mid_images = []
        self.speaking_high_images = []
        self.blink_images = []
        self._save_image_sets()

    def _choose_pet_images(self) -> None:
        paths = self._pick_images("Escolha GIF ou PNG do pet")
        if not paths:
            return
        self.pet_images = paths
        self.pet_enabled_var.set(True)
        self._save_settings()
        self._save_image_sets()

    def _choose_pet_state_images(self) -> None:
        speaking = self._pick_images("Escolha pet falando")
        if speaking:
            self.pet_speaking_images = speaking
        loud = self._pick_images("Escolha pet volume alto")
        if loud:
            self.pet_loud_images = loud
        self.pet_enabled_var.set(True)
        self._save_settings()
        self._save_image_sets()

    def _clear_pet_images(self) -> None:
        self.pet_images = []
        self.pet_speaking_images = []
        self.pet_loud_images = []
        self._save_image_sets()

    def _all_asset_paths(self) -> list[str]:
        return [
            *self.idle_images,
            *self.speaking_images,
            *self.speaking_low_images,
            *self.speaking_mid_images,
            *self.speaking_high_images,
            *self.blink_images,
            *self.pet_images,
            *self.pet_speaking_images,
            *self.pet_loud_images,
        ]

    def _validate_assets(self) -> None:
        paths = self._all_asset_paths()
        if not paths:
            messagebox.showinfo("Validar assets", "Nenhum asset carregado ainda.")
            return

        missing = [path for path in paths if not Path(path).is_file()]
        heavy: list[str] = []
        oversized: list[str] = []
        for path in paths:
            file_path = Path(path)
            if not file_path.is_file():
                continue
            try:
                if file_path.stat().st_size > 8 * 1024 * 1024:
                    heavy.append(file_path.name)
            except OSError:
                continue
            if file_path.suffix.lower() != ".png":
                continue
            try:
                from PIL import Image

                with Image.open(file_path) as image:
                    if max(image.size) > 2000:
                        oversized.append(f"{file_path.name} ({image.size[0]}x{image.size[1]})")
            except Exception:
                continue

        if not self.idle_images:
            missing.append("Estado idle sem imagem")
        if not (self.speaking_images or self.speaking_low_images or self.speaking_mid_images or self.speaking_high_images):
            missing.append("Estado de fala sem imagem")

        issues = []
        if missing:
            issues.append("Problemas:\n" + "\n".join(f"- {Path(item).name}" for item in missing[:8]))
        if heavy:
            issues.append("Arquivos pesados:\n" + "\n".join(f"- {item}" for item in heavy[:8]))
        if oversized:
            issues.append("PNG muito grande:\n" + "\n".join(f"- {item}" for item in oversized[:8]))

        if issues:
            messagebox.showwarning("Validar assets", "\n\n".join(issues))
            self._set_status("Assets precisam de atencao", 2600)
            return

        messagebox.showinfo("Validar assets", "Assets prontos para live. Nenhum problema encontrado.")
        self._set_status("Assets validados", 2200)

    def _pick_images(self, title: str) -> list[str]:
        return list(
            filedialog.askopenfilenames(
                title=title,
                filetypes=(
                    ("Imagens PNG/GIF", "*.png *.gif"),
                    ("PNG", "*.png"),
                    ("GIF", "*.gif"),
                    ("Todos os arquivos", "*.*"),
                ),
            )
        )

    def _save_image_sets(self) -> None:
        self.settings.idle_images = self.idle_images
        self.settings.speaking_images = self.speaking_images
        self.settings.speaking_low_images = self.speaking_low_images
        self.settings.speaking_mid_images = self.speaking_mid_images
        self.settings.speaking_high_images = self.speaking_high_images
        self.settings.blink_images = self.blink_images
        self.settings.pet_images = self.pet_images
        self.settings.pet_speaking_images = self.pet_speaking_images
        self.settings.pet_loud_images = self.pet_loud_images
        self.avatar_canvas.set_image_sets(
            self.idle_images,
            self.speaking_images,
            self.speaking_low_images,
            self.speaking_mid_images,
            self.speaking_high_images,
            self.blink_images,
        )
        self.avatar_canvas.set_pet_images(self.pet_images, self.pet_speaking_images, self.pet_loud_images)
        self.avatar_canvas.set_transform(
            self.settings.avatar_scale,
            self.settings.avatar_offset_x,
            self.settings.avatar_offset_y,
            self.settings.avatar_rotation,
        )
        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_image_sets(
                self.idle_images,
                self.speaking_images,
                self.speaking_low_images,
                self.speaking_mid_images,
                self.speaking_high_images,
                self.blink_images,
            )
            self.obs_window.set_pet_images(self.pet_images, self.pet_speaking_images, self.pet_loud_images)
        self.avatar_label.configure(text="Assets carregados" if self.settings.streamer_safe else self._image_summary())
        self.settings.save()

    def _image_summary(self) -> str:
        level_count = len(self.speaking_low_images) + len(self.speaking_mid_images) + len(self.speaking_high_images)
        pet_count = len(self.pet_images) + len(self.pet_speaking_images) + len(self.pet_loud_images)
        return f"Idle: {len(self.idle_images)} | Fala: {len(self.speaking_images)} | Niveis: {level_count} | Piscar: {len(self.blink_images)} | Pet: {pet_count}"

