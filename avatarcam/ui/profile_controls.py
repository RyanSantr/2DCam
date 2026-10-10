from tkinter import messagebox, simpledialog
from avatarcam.core.profile_backup import create_settings_backup, restore_settings_backup
from avatarcam.core.settings import Settings


class ProfileControls:
    def _profile_names(self) -> tuple[str, ...]:
        profiles = self.settings.profiles or {}
        names = sorted(set(profiles.keys()) | {self.settings.active_profile, "Default"})
        return tuple(names)

    def _clean_profile_name(self, name: str | None) -> str:
        cleaned = (name or "").strip()
        return cleaned or "Default"

    def _profile_list(self, profile: dict, key: str) -> list[str]:
        value = profile.get(key, [])
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    def _refresh_profile_select(self) -> None:
        names = self._profile_names()
        self.profile_select.configure(values=names)
        if self.profile_var.get() not in names:
            self.profile_var.set(self.settings.active_profile)

    def _expression_names(self) -> tuple[str, ...]:
        expressions = self.settings.expressions or {}
        names = sorted(set(expressions.keys()) | {self.settings.active_expression, "Default"})
        return tuple(names)

    def _current_profile_data(self) -> dict:
        return {
            "idle_images": list(self.idle_images),
            "speaking_images": list(self.speaking_images),
            "speaking_low_images": list(self.speaking_low_images),
            "speaking_mid_images": list(self.speaking_mid_images),
            "speaking_high_images": list(self.speaking_high_images),
            "blink_images": list(self.blink_images),
            "pet_images": list(self.pet_images),
            "pet_speaking_images": list(self.pet_speaking_images),
            "pet_loud_images": list(self.pet_loud_images),
            "sensitivity": float(self.sensitivity_var.get()),
            "smoothing": float(self.smoothing_var.get()),
            "animation_fps": int(float(self.animation_fps_var.get())),
            "avatar_scale": float(self.avatar_scale_var.get()),
            "avatar_offset_x": float(self.avatar_x_var.get()),
            "avatar_offset_y": float(self.avatar_y_var.get()),
            "avatar_rotation": float(self.avatar_rotation_var.get()),
            "pet_enabled": self.pet_enabled_var.get(),
            "pet_size": float(self.pet_size_var.get()),
            "pet_offset_x": float(self.pet_x_var.get()),
            "pet_offset_y": float(self.pet_y_var.get()),
            "pet_reaction": self.pet_reaction_var.get(),
            "pet_reaction_strength": float(self.pet_strength_var.get()),
            "pet_layer": self.pet_layer_var.get(),
            "pet_opacity": float(self.pet_opacity_var.get()),
            "pet_mirror": self.pet_mirror_var.get(),
            "mouth_hold_ticks": int(float(self.mouth_hold_var.get())),
            "obs_background": self.obs_background_var.get(),
            "obs_resolution": self.obs_resolution_var.get(),
            'avatar3d_path': self.settings.avatar3d_path,
            'camera3d': self.settings.camera3d,
            'expression3d': self.settings.expression3d,
            'speech_mode': self.settings.speech_mode,
            "expressions": self.settings.expressions or {},
        }

    def _save_profile(self) -> None:
        name = self._clean_profile_name(self.profile_var.get())
        self.profile_var.set(name)
        create_settings_backup("antes_salvar_perfil")
        profiles = self.settings.profiles or {}
        profiles[name] = self._current_profile_data()
        self.settings.profiles = profiles
        self.settings.active_profile = name
        self._refresh_profile_select()
        self.settings.save()
        self._set_status(f"Perfil salvo: {name}", 2600)

    def _save_expression(self) -> None:
        name = self.expression_var.get() or "Default"
        expressions = self.settings.expressions or {}
        expressions[name] = self._current_image_sets()
        self.settings.expressions = expressions
        self.settings.active_expression = name
        self.expression_select.configure(values=self._expression_names())
        self.settings.save()
        self._set_status(f"Expressao salva: {name}", 2200)

    def _new_expression(self) -> None:
        name = simpledialog.askstring("Nova expressao", "Nome da expressao:")
        if not name:
            return
        self.expression_var.set(name)
        self._save_expression()

    def _load_expression_by_index(self, index: int) -> None:
        names = self._expression_names()
        if 0 <= index - 1 < len(names):
            self._load_expression(names[index - 1])

    def _load_expression(self, name: str) -> None:
        expression = (self.settings.expressions or {}).get(name)
        if not expression:
            return
        self.idle_images = list(expression.get("idle") or [])
        self.speaking_images = list(expression.get("talk") or [])
        self.speaking_low_images = list(expression.get("talk_low") or [])
        self.speaking_mid_images = list(expression.get("talk_mid") or [])
        self.speaking_high_images = list(expression.get("talk_high") or [])
        self.blink_images = self._profile_list(expression, "blink")
        self.pet_images = self._profile_list(expression, "pet")
        self.pet_speaking_images = self._profile_list(expression, "pet_talk")
        self.pet_loud_images = self._profile_list(expression, "pet_loud")
        self.settings.active_expression = name
        self.expression_var.set(name)
        self._save_image_sets()
        self._set_status(f"Expressao: {name}", 2200)

    def _new_profile(self) -> None:
        raw_name = simpledialog.askstring("Novo perfil", "Nome do perfil:")
        if not raw_name or not raw_name.strip():
            return
        name = self._clean_profile_name(raw_name)
        self.profile_var.set(name)
        self._save_profile()

    def _duplicate_profile(self) -> None:
        current = self._clean_profile_name(self.profile_var.get())
        raw_name = simpledialog.askstring("Duplicar perfil", "Nome do novo perfil:", initialvalue=f"{current} copia")
        if not raw_name or not raw_name.strip():
            return
        new_name = self._clean_profile_name(raw_name)
        create_settings_backup("antes_duplicar_perfil")
        profiles = self.settings.profiles or {}
        profiles[new_name] = self._current_profile_data()
        self.settings.profiles = profiles
        self.settings.active_profile = new_name
        self.profile_var.set(new_name)
        self._refresh_profile_select()
        self.settings.save()
        self._set_status(f"Perfil duplicado: {new_name}", 2600)

    def _rename_profile(self) -> None:
        old_name = self._clean_profile_name(self.profile_var.get())
        profiles = self.settings.profiles or {}
        if old_name not in profiles:
            messagebox.showinfo("Renomear perfil", "Salve o perfil atual antes de renomear.")
            return

        raw_name = simpledialog.askstring("Renomear perfil", "Novo nome do perfil:", initialvalue=old_name)
        if not raw_name or not raw_name.strip():
            return
        new_name = self._clean_profile_name(raw_name)
        if new_name == old_name:
            return
        if new_name in profiles and not messagebox.askyesno("Renomear perfil", f"Ja existe um perfil chamado {new_name}. Substituir?"):
            return

        create_settings_backup("antes_renomear_perfil")
        profiles[new_name] = profiles.pop(old_name)
        self.settings.profiles = profiles
        self.settings.active_profile = new_name
        self.profile_var.set(new_name)
        self._refresh_profile_select()
        self.settings.save()
        self._set_status(f"Perfil renomeado: {old_name} -> {new_name}", 3000)

    def _delete_profile(self) -> None:
        name = self._clean_profile_name(self.profile_var.get())
        profiles = self.settings.profiles or {}
        if name not in profiles:
            messagebox.showinfo("Excluir perfil", "Este perfil ainda nao esta salvo, entao nao ha o que excluir.")
            return
        if not messagebox.askyesno("Excluir perfil", f"Excluir o perfil {name}? Um backup sera criado antes."):
            return

        create_settings_backup("antes_excluir_perfil")
        profiles.pop(name, None)
        self.settings.profiles = profiles
        fallback = next(iter(sorted(profiles)), "Default")
        self.settings.active_profile = fallback
        self.profile_var.set(fallback)
        self._refresh_profile_select()
        self.settings.save()
        if fallback in profiles:
            self._load_profile(fallback)
        else:
            self._save_settings()
        self._set_status(f"Perfil excluido: {name}", 3000)

    def _load_profile(self, name: str) -> None:
        name = self._clean_profile_name(name)
        profile = (self.settings.profiles or {}).get(name)
        if not profile:
            return
        self.profile_var.set(name)
        self.idle_images = self._profile_list(profile, "idle_images")
        self.speaking_images = self._profile_list(profile, "speaking_images")
        self.speaking_low_images = self._profile_list(profile, "speaking_low_images")
        self.speaking_mid_images = self._profile_list(profile, "speaking_mid_images")
        self.speaking_high_images = self._profile_list(profile, "speaking_high_images")
        self.blink_images = self._profile_list(profile, "blink_images")
        self.pet_images = self._profile_list(profile, "pet_images")
        self.pet_speaking_images = self._profile_list(profile, "pet_speaking_images")
        self.pet_loud_images = self._profile_list(profile, "pet_loud_images")
        self.sensitivity_var.set(float(profile.get("sensitivity", self.settings.sensitivity)))
        self.smoothing_var.set(float(profile.get("smoothing", self.settings.smoothing)))
        self.animation_fps_var.set(int(profile.get("animation_fps", self.settings.animation_fps)))
        self.avatar_scale_var.set(float(profile.get("avatar_scale", self.settings.avatar_scale)))
        self.avatar_x_var.set(float(profile.get("avatar_offset_x", self.settings.avatar_offset_x)))
        self.avatar_y_var.set(float(profile.get("avatar_offset_y", self.settings.avatar_offset_y)))
        self.avatar_rotation_var.set(float(profile.get("avatar_rotation", self.settings.avatar_rotation)))
        self.pet_enabled_var.set(bool(profile.get("pet_enabled", self.settings.pet_enabled)))
        self.pet_size_var.set(float(profile.get("pet_size", self.settings.pet_size)))
        self.pet_x_var.set(float(profile.get("pet_offset_x", self.settings.pet_offset_x)))
        self.pet_y_var.set(float(profile.get("pet_offset_y", self.settings.pet_offset_y)))
        self.pet_reaction_var.set(profile.get("pet_reaction", self.settings.pet_reaction))
        self.pet_strength_var.set(float(profile.get("pet_reaction_strength", self.settings.pet_reaction_strength)))
        self.pet_layer_var.set(profile.get("pet_layer", self.settings.pet_layer))
        self.pet_opacity_var.set(float(profile.get("pet_opacity", self.settings.pet_opacity)))
        self.pet_mirror_var.set(bool(profile.get("pet_mirror", self.settings.pet_mirror)))
        self.mouth_hold_var.set(int(profile.get("mouth_hold_ticks", self.settings.mouth_hold_ticks)))
        self.obs_background_var.set(profile.get("obs_background", self.settings.obs_background))
        self.obs_resolution_var.set(profile.get("obs_resolution", self.settings.obs_resolution))
        self.settings.active_profile = name
        self.settings.avatar3d_path = profile.get('avatar3d_path', '')
        self.settings.camera3d = profile.get('camera3d')
        self._camera_revision += 1
        self.expression3d_var.set(profile.get('expression3d', 'neutral'))
        self.speech_mode_var.set(profile.get('speech_mode', 'volume'))
        self.model_label.configure(text=self._model_description())
        self._save_studio(True)
        self._save_settings()
        self._save_obs_settings()
        self._save_image_sets()
        self._set_status(f"Perfil carregado: {name}", 2600)

    def _restore_latest_backup(self) -> None:
        if not messagebox.askyesno("Restaurar backup", "Restaurar o ultimo backup local de configuracoes e perfis?"):
            return
        try:
            restored = restore_settings_backup()
        except Exception as exc:
            messagebox.showerror("Backup", str(exc))
            return
        self.settings = Settings.load()
        self._apply_settings_to_ui()
        self._set_status(f"Backup restaurado: {restored.name}", 3200)

