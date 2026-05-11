from __future__ import annotations

import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from avatarcam.core.app_log import close_logger, setup_logger
from avatarcam.core.avatar_pack import export_avatar_pack, import_avatar_folder, import_avatar_pack
from avatarcam.core.hotkeys import HotkeyManager
from avatarcam.core.profile_backup import BACKUP_DIR, create_settings_backup, restore_settings_backup
from avatarcam.core.settings import APP_DIR, LOG_DIR, SETTINGS_FILE
from avatarcam.audio.microphone import MicrophoneInput
from avatarcam.core.settings import Settings
from avatarcam.core.speech_detector import SpeechDetector
from avatarcam.ui.avatar_canvas import AvatarCanvas
from avatarcam.ui.obs_window import ObsOutputWindow
from avatarcam.ui.setup_wizard import SetupWizard
from avatarcam.ui.theme import DARK, LIGHT, OBS_BACKGROUNDS
from avatarcam.ui.tray import TrayController


DEFAULT_HOTKEYS = {
    "toggle_mic": "f8",
    "test_speech": "f9",
    "show_controls": "f10",
    "toggle_obs": "f11",
    "toggle_pet": "f12",
    "live_mode": "ctrl+f11",
    "scene_1": "ctrl+1",
    "scene_2": "ctrl+2",
    "scene_3": "ctrl+3",
    "scene_4": "ctrl+4",
}

HOTKEY_ACTION_LABELS = {
    "toggle_mic": "Microfone liga/desliga",
    "test_speech": "Teste de fala",
    "show_controls": "Mostrar controles",
    "toggle_obs": "Abrir/ocultar OBS",
    "toggle_pet": "Mostrar/ocultar pet",
    "live_mode": "Ativar modo live",
    "scene_1": "Aplicar cena 1",
    "scene_2": "Aplicar cena 2",
    "scene_3": "Aplicar cena 3",
    "scene_4": "Aplicar cena 4",
}

HOTKEY_CHOICES = (
    "",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "ctrl+1",
    "ctrl+2",
    "ctrl+3",
    "ctrl+4",
    "ctrl+5",
    "ctrl+6",
    "ctrl+7",
    "ctrl+8",
    "ctrl+9",
    "alt+1",
    "alt+2",
    "alt+3",
    "alt+4",
    "ctrl+f9",
    "ctrl+f10",
    "ctrl+f11",
    "ctrl+f12",
    "alt+f9",
    "alt+f10",
    "alt+f11",
    "alt+f12",
)


class AvatarCamApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AvatarCam 2D")
        self.geometry("1180x820")
        self.minsize(980, 760)

        self.log = setup_logger()
        self.log.info("AvatarCam iniciado")
        self.settings = Settings.load()
        self.colors = DARK if self.settings.dark_mode else LIGHT
        self.microphone = MicrophoneInput()
        self.microphone.set_device(self.settings.microphone_device)
        self.detector = SpeechDetector(self.settings.sensitivity, self.settings.smoothing, self.settings.mouth_hold_ticks)
        self.test_ticks = 0
        self.calibration_samples: list[float] = []
        self.calibration_ticks = 0
        self.render_frames = 0
        self.last_fps_time = 0.0
        self.render_fps = 0
        self.ui_tick = 0
        self.status_hold_until = 0
        self.pending_settings_save: str | None = None
        self.last_speaking = False
        self.obs_window: ObsOutputWindow | None = None
        self.idle_images = list(self.settings.idle_images or [])
        self.speaking_images = list(self.settings.speaking_images or [])
        self.speaking_low_images = list(self.settings.speaking_low_images or [])
        self.speaking_mid_images = list(self.settings.speaking_mid_images or [])
        self.speaking_high_images = list(self.settings.speaking_high_images or [])
        self.blink_images = list(self.settings.blink_images or [])
        self.pet_images = list(self.settings.pet_images or [])
        self.pet_speaking_images = list(self.settings.pet_speaking_images or [])
        self.pet_loud_images = list(self.settings.pet_loud_images or [])
        self.expression_var = tk.StringVar(value=self.settings.active_expression)
        self.hotkeys = HotkeyManager()
        self.local_hotkey_sequences: list[str] = []
        self.tray = TrayController(self)

        self._configure_style()
        self._build_layout()
        self._apply_theme()
        self._bind_hotkeys()
        self.tray.start()
        self.protocol("WM_DELETE_WINDOW", self._hide_controls)
        if self.settings.auto_start_minimized:
            self.after(300, self.withdraw)
        self._tick()

    def _configure_style(self) -> None:
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

    def _build_layout(self) -> None:
        self.container = ttk.Frame(self, padding=18)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.container.columnconfigure(0, weight=3)
        self.container.columnconfigure(1, weight=2)
        self.container.rowconfigure(0, weight=1)

        self.stage_frame = ttk.Frame(self.container, padding=14)
        self.stage_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.stage_frame.rowconfigure(1, weight=1)
        self.stage_frame.columnconfigure(0, weight=1)

        header = ttk.Frame(self.stage_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="AvatarCam 2D", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Sua camera vira um avatar animado", style="Title.TLabel").grid(row=1, column=0, sticky="w")
        self.theme_button = ttk.Button(header, text="Tema", command=self._toggle_theme)
        self.theme_button.grid(row=0, column=1, rowspan=2, sticky="e")

        self.avatar_canvas = AvatarCanvas(self.stage_frame)
        self.avatar_canvas.grid(row=1, column=0, sticky="nsew")
        self.avatar_canvas.set_image_sets(
            self.idle_images,
            self.speaking_images,
            self.speaking_low_images,
            self.speaking_mid_images,
            self.speaking_high_images,
            self.blink_images,
        )
        self.avatar_canvas.set_pet_images(self.pet_images, self.pet_speaking_images, self.pet_loud_images)
        self.avatar_canvas.set_animation_fps(self.settings.animation_fps)
        self.avatar_canvas.set_background(self.settings.background)
        self.avatar_canvas.set_transform(
            self.settings.avatar_scale,
            self.settings.avatar_offset_x,
            self.settings.avatar_offset_y,
            self.settings.avatar_rotation,
        )
        self.avatar_canvas.set_visual_options(
            self.settings.idle_motion,
            self.settings.avatar_shadow,
            self.settings.pet_enabled,
            self.settings.pet_size,
            self.settings.pet_offset_x,
            self.settings.pet_offset_y,
            self.settings.pet_reaction,
            self.settings.pet_reaction_strength,
            self.settings.pet_layer,
            self.settings.pet_opacity,
            self.settings.pet_mirror,
        )

        self.control_canvas = tk.Canvas(self.container, highlightthickness=0, borderwidth=0)
        self.control_canvas.grid(row=0, column=1, sticky="nsew")
        self.control_scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.control_canvas.yview)
        self.control_scrollbar.grid(row=0, column=2, sticky="ns")
        self.control_canvas.configure(yscrollcommand=self.control_scrollbar.set)
        self.control_frame = ttk.Frame(self.control_canvas, padding=18)
        self.control_window = self.control_canvas.create_window((0, 0), window=self.control_frame, anchor="nw")
        self.control_frame.bind("<Configure>", self._sync_control_scroll)
        self.control_canvas.bind("<Configure>", self._sync_control_width)
        self.control_canvas.bind("<Enter>", self._bind_control_mousewheel)
        self.control_canvas.bind("<Leave>", self._unbind_control_mousewheel)
        self.control_frame.columnconfigure(0, weight=1)
        self.control_frame.rowconfigure(2, weight=1)

        self.sensitivity_var = tk.DoubleVar(value=self.settings.sensitivity)
        self.smoothing_var = tk.DoubleVar(value=self.settings.smoothing)
        self.dark_var = tk.BooleanVar(value=self.settings.dark_mode)
        self.background_var = tk.StringVar(value=self.settings.background)
        self.obs_background_var = tk.StringVar(value=self.settings.obs_background)
        self.obs_top_var = tk.BooleanVar(value=self.settings.obs_always_on_top)
        self.auto_hide_var = tk.BooleanVar(value=self.settings.auto_hide_controls)
        self.animation_fps_var = tk.IntVar(value=self.settings.animation_fps)
        self.obs_resolution_var = tk.StringVar(value=self.settings.obs_resolution)
        self.obs_borderless_var = tk.BooleanVar(value=self.settings.obs_borderless)
        self.avatar_scale_var = tk.DoubleVar(value=self.settings.avatar_scale)
        self.avatar_x_var = tk.DoubleVar(value=self.settings.avatar_offset_x)
        self.avatar_y_var = tk.DoubleVar(value=self.settings.avatar_offset_y)
        self.avatar_rotation_var = tk.DoubleVar(value=self.settings.avatar_rotation)
        self.performance_var = tk.BooleanVar(value=self.settings.performance_mode)
        self.performance_preset_var = tk.StringVar(value=self.settings.performance_preset)
        self.idle_motion_var = tk.BooleanVar(value=self.settings.idle_motion)
        self.avatar_shadow_var = tk.BooleanVar(value=self.settings.avatar_shadow)
        self.streamer_safe_var = tk.BooleanVar(value=self.settings.streamer_safe)
        self.pet_enabled_var = tk.BooleanVar(value=self.settings.pet_enabled)
        self.pet_size_var = tk.DoubleVar(value=self.settings.pet_size)
        self.pet_x_var = tk.DoubleVar(value=self.settings.pet_offset_x)
        self.pet_y_var = tk.DoubleVar(value=self.settings.pet_offset_y)
        self.pet_reaction_var = tk.StringVar(value=self.settings.pet_reaction)
        self.pet_strength_var = tk.DoubleVar(value=self.settings.pet_reaction_strength)
        self.pet_layer_var = tk.StringVar(value=self.settings.pet_layer)
        self.pet_opacity_var = tk.DoubleVar(value=self.settings.pet_opacity)
        self.pet_mirror_var = tk.BooleanVar(value=self.settings.pet_mirror)
        self.mouth_hold_var = tk.IntVar(value=self.settings.mouth_hold_ticks)
        self.auto_start_var = tk.BooleanVar(value=self.settings.auto_start_minimized)
        self.scene_var = tk.StringVar(value=self.settings.active_scene)
        self.hotkey_vars = {
            action: tk.StringVar(value=self._hotkey_config().get(action, default))
            for action, default in DEFAULT_HOTKEYS.items()
        }

        ttk.Label(self.control_frame, text="Controles", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.control_frame, text="Painel da live", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 12))

        self.control_tabs = ttk.Notebook(self.control_frame)
        self.control_tabs.grid(row=2, column=0, sticky="nsew")
        self.live_tab = ttk.Frame(self.control_tabs, padding=12, style="Panel.TFrame")
        self.assets_tab = ttk.Frame(self.control_tabs, padding=12, style="Panel.TFrame")
        self.tuning_tab = ttk.Frame(self.control_tabs, padding=12, style="Panel.TFrame")
        self.obs_tab = ttk.Frame(self.control_tabs, padding=12, style="Panel.TFrame")
        self.shortcuts_tab = ttk.Frame(self.control_tabs, padding=12, style="Panel.TFrame")
        self.system_tab = ttk.Frame(self.control_tabs, padding=12, style="Panel.TFrame")
        for tab in (self.live_tab, self.assets_tab, self.tuning_tab, self.obs_tab, self.shortcuts_tab, self.system_tab):
            tab.columnconfigure(0, weight=1)
        self.control_tabs.add(self.live_tab, text="Operacao")
        self.control_tabs.add(self.assets_tab, text="Assets")
        self.control_tabs.add(self.tuning_tab, text="Ajustes")
        self.control_tabs.add(self.obs_tab, text="OBS")
        self.control_tabs.add(self.shortcuts_tab, text="Atalhos")
        self.control_tabs.add(self.system_tab, text="Sistema")

        live_actions = ttk.LabelFrame(self.live_tab, text="Live", padding=12)
        live_actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        live_actions.columnconfigure(0, weight=1)
        self.mic_button = ttk.Button(live_actions, text="Ativar microfone", command=self._toggle_microphone, style="Primary.TButton")
        self.mic_button.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.test_button = ttk.Button(live_actions, text="Teste de fala", command=self._trigger_test)
        self.test_button.grid(row=1, column=0, sticky="ew", pady=4)
        self.calibrate_button = ttk.Button(live_actions, text="Calibrar ruido ambiente", command=self._start_calibration)
        self.calibrate_button.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(live_actions, text="Ativar modo live", command=self._enable_live_mode, style="Primary.TButton").grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(live_actions, text="Setup guiado", command=self._open_setup_wizard).grid(row=4, column=0, sticky="ew", pady=(8, 0))

        profile_frame = ttk.LabelFrame(self.live_tab, text="Perfil", padding=12)
        profile_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        profile_frame.columnconfigure(0, weight=1)
        profile_frame.columnconfigure(1, weight=1)
        profile_frame.columnconfigure(2, weight=1)
        profile_frame.columnconfigure(3, weight=1)
        self.profile_var = tk.StringVar(value=self.settings.active_profile)
        self.profile_select = ttk.Combobox(profile_frame, textvariable=self.profile_var, values=self._profile_names(), state="readonly")
        self.profile_select.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        self.profile_select.bind("<<ComboboxSelected>>", lambda _event: self._load_profile(self.profile_var.get()))
        ttk.Button(profile_frame, text="Salvar", command=self._save_profile).grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(profile_frame, text="Novo", command=self._new_profile).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Button(profile_frame, text="Duplicar", command=self._duplicate_profile).grid(row=1, column=2, sticky="ew", padx=4)
        ttk.Button(profile_frame, text="Renomear", command=self._rename_profile).grid(row=1, column=3, sticky="ew", padx=(4, 0))
        ttk.Button(profile_frame, text="Excluir perfil", command=self._delete_profile).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0), padx=(0, 4))
        ttk.Button(profile_frame, text="Restaurar backup", command=self._restore_latest_backup).grid(row=2, column=2, columnspan=2, sticky="ew", pady=(8, 0), padx=(4, 0))

        expression_frame = ttk.LabelFrame(self.live_tab, text="Expressoes", padding=12)
        expression_frame.grid(row=2, column=0, sticky="ew")
        expression_frame.columnconfigure(0, weight=1)
        self.expression_select = ttk.Combobox(expression_frame, textvariable=self.expression_var, values=self._expression_names(), state="readonly")
        self.expression_select.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.expression_select.bind("<<ComboboxSelected>>", lambda _event: self._load_expression(self.expression_var.get()))
        ttk.Button(expression_frame, text="Salvar expressao atual", command=self._save_expression).grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(expression_frame, text="Nova expressao", command=self._new_expression).grid(row=2, column=0, sticky="ew")

        avatar_assets = ttk.LabelFrame(self.assets_tab, text="Avatar", padding=12)
        avatar_assets.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        avatar_assets.columnconfigure(0, weight=1)
        self.idle_button = ttk.Button(avatar_assets, text="Escolher imagens idle", command=self._choose_idle_images)
        self.idle_button.grid(row=0, column=0, sticky="ew", pady=4)
        self.speaking_button = ttk.Button(avatar_assets, text="Escolher fala padrao", command=self._choose_speaking_images)
        self.speaking_button.grid(row=1, column=0, sticky="ew", pady=4)
        self.speaking_levels_button = ttk.Button(avatar_assets, text="Escolher fala baixa/media/alta", command=self._choose_level_images)
        self.speaking_levels_button.grid(row=2, column=0, sticky="ew", pady=4)
        self.blink_button = ttk.Button(avatar_assets, text="Escolher piscar", command=self._choose_blink_images)
        self.blink_button.grid(row=3, column=0, sticky="ew", pady=4)

        pet_assets = ttk.LabelFrame(self.assets_tab, text="Pet", padding=12)
        pet_assets.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        pet_assets.columnconfigure(0, weight=1)
        self.pet_button = ttk.Button(pet_assets, text="Escolher GIF/PNG do pet", command=self._choose_pet_images)
        self.pet_button.grid(row=0, column=0, sticky="ew", pady=4)
        self.pet_states_button = ttk.Button(pet_assets, text="Escolher pet fala/alto", command=self._choose_pet_state_images)
        self.pet_states_button.grid(row=1, column=0, sticky="ew", pady=4)
        self.clear_pet_button = ttk.Button(pet_assets, text="Limpar pet", command=self._clear_pet_images)
        self.clear_pet_button.grid(row=2, column=0, sticky="ew", pady=4)

        library_frame = ttk.LabelFrame(self.assets_tab, text="Biblioteca", padding=12)
        library_frame.grid(row=2, column=0, sticky="ew")
        library_frame.columnconfigure(0, weight=1)
        self.import_folder_button = ttk.Button(library_frame, text="Importar pasta de avatar", command=self._import_avatar_folder)
        self.import_folder_button.grid(row=0, column=0, sticky="ew", pady=4)
        pack_row = ttk.Frame(library_frame)
        pack_row.grid(row=1, column=0, sticky="ew", pady=4)
        pack_row.columnconfigure(0, weight=1)
        pack_row.columnconfigure(1, weight=1)
        ttk.Button(pack_row, text="Importar .avatarpack", command=self._import_pack).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(pack_row, text="Exportar", command=self._export_pack).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.clear_images_button = ttk.Button(library_frame, text="Limpar imagens do avatar", command=self._clear_images)
        self.clear_images_button.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(library_frame, text="Validar assets", command=self._validate_assets).grid(row=3, column=0, sticky="ew", pady=(8, 0))

        audio_frame = ttk.LabelFrame(self.tuning_tab, text="Audio e fala", padding=12)
        audio_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        audio_frame.columnconfigure(0, weight=1)
        self._add_slider_to(audio_frame, "Sensibilidade", self.sensitivity_var, 0.04, 0.7, 0)
        self._add_slider_to(audio_frame, "Suavizacao", self.smoothing_var, 0.1, 0.95, 1)
        self._add_slider_to(audio_frame, "Segurar boca", self.mouth_hold_var, 1, 18, 2)
        ttk.Label(audio_frame, text="Microfone", style="Body.TLabel").grid(row=6, column=0, sticky="w", pady=(12, 4))
        self.input_devices = MicrophoneInput.list_input_devices()
        self.microphone_names = [name for name, _index in self.input_devices]
        current_device = next((name for name, index in self.input_devices if index == self.settings.microphone_device), self.microphone_names[0])
        self.microphone_var = tk.StringVar(value=current_device)
        self.microphone_select = ttk.Combobox(audio_frame, textvariable=self.microphone_var, values=self.microphone_names, state="readonly")
        self.microphone_select.grid(row=7, column=0, sticky="ew")
        self.microphone_select.bind("<<ComboboxSelected>>", lambda _event: self._change_microphone())

        avatar_frame = ttk.LabelFrame(self.tuning_tab, text="Avatar", padding=12)
        avatar_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        avatar_frame.columnconfigure(0, weight=1)
        self._add_slider_to(avatar_frame, "FPS da animacao", self.animation_fps_var, 1, 30, 0)
        self._add_slider_to(avatar_frame, "Escala avatar", self.avatar_scale_var, 0.25, 2.5, 1)
        self._add_slider_to(avatar_frame, "Posicao X", self.avatar_x_var, -0.8, 0.8, 2)
        self._add_slider_to(avatar_frame, "Posicao Y", self.avatar_y_var, -0.8, 0.8, 3)
        self._add_slider_to(avatar_frame, "Rotacao avatar", self.avatar_rotation_var, -35, 35, 4)
        ttk.Checkbutton(avatar_frame, text="Movimento vertical automatico", variable=self.idle_motion_var, command=self._save_settings).grid(row=10, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(avatar_frame, text="Sombra do avatar", variable=self.avatar_shadow_var, command=self._save_settings).grid(row=11, column=0, sticky="w", pady=(8, 0))

        pet_frame = ttk.LabelFrame(self.tuning_tab, text="Pet", padding=12)
        pet_frame.grid(row=2, column=0, sticky="ew")
        pet_frame.columnconfigure(0, weight=1)
        self._add_slider_to(pet_frame, "Tamanho do pet", self.pet_size_var, 0.45, 1.6, 0)
        self._add_slider_to(pet_frame, "Pet posicao X", self.pet_x_var, -0.9, 0.9, 1)
        self._add_slider_to(pet_frame, "Pet posicao Y", self.pet_y_var, -0.9, 0.9, 2)
        self._add_slider_to(pet_frame, "Forca reacao pet", self.pet_strength_var, 0.0, 1.0, 3)
        self._add_slider_to(pet_frame, "Opacidade pet", self.pet_opacity_var, 0.1, 1.0, 4)
        ttk.Label(pet_frame, text="Reacao do pet", style="Body.TLabel").grid(row=10, column=0, sticky="w", pady=(12, 4))
        self.pet_reaction_select = ttk.Combobox(
            pet_frame,
            textvariable=self.pet_reaction_var,
            values=("none", "bounce", "shake", "float", "speed", "bounce_speed", "shake_speed"),
            state="readonly",
        )
        self.pet_reaction_select.grid(row=11, column=0, sticky="ew")
        self.pet_reaction_select.bind("<<ComboboxSelected>>", lambda _event: self._save_settings())
        ttk.Label(pet_frame, text="Camada do pet", style="Body.TLabel").grid(row=12, column=0, sticky="w", pady=(12, 4))
        self.pet_layer_select = ttk.Combobox(
            pet_frame,
            textvariable=self.pet_layer_var,
            values=("front", "back"),
            state="readonly",
        )
        self.pet_layer_select.grid(row=13, column=0, sticky="ew")
        self.pet_layer_select.bind("<<ComboboxSelected>>", lambda _event: self._save_settings())
        ttk.Checkbutton(pet_frame, text="Mostrar pet", variable=self.pet_enabled_var, command=self._save_settings).grid(row=14, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(pet_frame, text="Espelhar pet", variable=self.pet_mirror_var, command=self._save_settings).grid(row=15, column=0, sticky="w", pady=(8, 0))

        obs_capture = ttk.LabelFrame(self.obs_tab, text="Captura", padding=12)
        obs_capture.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        obs_capture.columnconfigure(0, weight=1)
        self.obs_button = ttk.Button(obs_capture, text="Abrir janela OBS", command=self._toggle_obs_window, style="Primary.TButton")
        self.obs_button.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(obs_capture, text="Fundo da captura", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 4))
        self.obs_background_select = ttk.Combobox(
            obs_capture,
            textvariable=self.obs_background_var,
            values=tuple(OBS_BACKGROUNDS.keys()),
            state="readonly",
        )
        self.obs_background_select.grid(row=2, column=0, sticky="ew")
        self.obs_background_select.bind("<<ComboboxSelected>>", lambda _event: self._save_obs_settings())
        ttk.Label(obs_capture, text="Resolucao", style="Body.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 4))
        self.obs_resolution_select = ttk.Combobox(
            obs_capture,
            textvariable=self.obs_resolution_var,
            values=("1280x720", "1920x1080", "1080x1920", "960x540", "640x360"),
            state="readonly",
        )
        self.obs_resolution_select.grid(row=4, column=0, sticky="ew")
        self.obs_resolution_select.bind("<<ComboboxSelected>>", lambda _event: self._save_obs_settings())
        ttk.Checkbutton(obs_capture, text="Manter janela OBS no topo", variable=self.obs_top_var, command=self._save_obs_settings).grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Checkbutton(obs_capture, text="Janela OBS sem borda", variable=self.obs_borderless_var, command=self._save_obs_settings).grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(obs_capture, text="Esconder controles ao abrir OBS", variable=self.auto_hide_var, command=self._save_obs_settings).grid(row=7, column=0, sticky="w", pady=(8, 0))

        obs_actions = ttk.LabelFrame(self.obs_tab, text="Acoes", padding=12)
        obs_actions.grid(row=1, column=0, sticky="ew")
        obs_actions.columnconfigure(0, weight=1)
        self.live_button = ttk.Button(obs_actions, text="Ativar modo live", command=self._enable_live_mode, style="Primary.TButton")
        self.live_button.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.hide_button = ttk.Button(obs_actions, text="Ocultar controles", command=self._hide_controls)
        self.hide_button.grid(row=1, column=0, sticky="ew", pady=4)
        self.back_button = ttk.Button(obs_actions, text="Enviar OBS para tras", command=self._send_obs_to_back)
        self.back_button.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(obs_actions, text="Assistente OBS", command=self._show_obs_assistant).grid(row=3, column=0, sticky="ew", pady=(8, 0))

        scene_frame = ttk.LabelFrame(self.shortcuts_tab, text="Cenas", padding=12)
        scene_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        scene_frame.columnconfigure(0, weight=1)
        scene_frame.columnconfigure(1, weight=1)
        self.scene_select = ttk.Combobox(scene_frame, textvariable=self.scene_var, values=self._scene_names(), state="readonly")
        self.scene_select.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.scene_select.bind("<<ComboboxSelected>>", lambda _event: self._apply_scene(self.scene_var.get()))
        ttk.Button(scene_frame, text="Aplicar cena", command=lambda: self._apply_scene(self.scene_var.get())).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)
        ttk.Button(scene_frame, text="Salvar cena atual", command=lambda: self._save_scene(self.scene_var.get())).grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=4)
        ttk.Button(scene_frame, text="Nova cena", command=self._new_scene).grid(row=2, column=0, sticky="ew", padx=(0, 4), pady=4)
        ttk.Button(scene_frame, text="Excluir cena", command=self._delete_scene).grid(row=2, column=1, sticky="ew", padx=(4, 0), pady=4)
        self.scene_hint = ttk.Label(
            scene_frame,
            text="Cada cena salva posicao, escala, rotacao, fundo OBS, resolucao e composicao do pet.",
            style="Body.TLabel",
            wraplength=320,
        )
        self.scene_hint.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        hotkey_frame = ttk.LabelFrame(self.shortcuts_tab, text="Atalhos configuraveis", padding=12)
        hotkey_frame.grid(row=1, column=0, sticky="ew")
        hotkey_frame.columnconfigure(1, weight=1)
        for row, (action, label) in enumerate(HOTKEY_ACTION_LABELS.items()):
            ttk.Label(hotkey_frame, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            box = ttk.Combobox(hotkey_frame, textvariable=self.hotkey_vars[action], values=HOTKEY_CHOICES)
            box.grid(row=row, column=1, sticky="ew", pady=4)
        hotkey_buttons = ttk.Frame(hotkey_frame, style="Panel.TFrame")
        hotkey_buttons.grid(row=len(HOTKEY_ACTION_LABELS), column=0, columnspan=2, sticky="ew", pady=(10, 0))
        hotkey_buttons.columnconfigure(0, weight=1)
        hotkey_buttons.columnconfigure(1, weight=1)
        ttk.Button(hotkey_buttons, text="Salvar atalhos", command=self._save_hotkeys).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(hotkey_buttons, text="Restaurar padrao", command=self._reset_hotkeys).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        performance_frame = ttk.LabelFrame(self.system_tab, text="Performance e tema", padding=12)
        performance_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        performance_frame.columnconfigure(0, weight=1)
        ttk.Label(performance_frame, text="Preset performance", style="Body.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.performance_preset_select = ttk.Combobox(
            performance_frame,
            textvariable=self.performance_preset_var,
            values=("quality", "balanced", "performance", "ultra"),
            state="readonly",
        )
        self.performance_preset_select.grid(row=1, column=0, sticky="ew")
        self.performance_preset_select.bind("<<ComboboxSelected>>", lambda _event: self._apply_performance_preset())
        ttk.Label(performance_frame, text="Fundo preview", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=(12, 4))
        self.background_select = ttk.Combobox(
            performance_frame,
            textvariable=self.background_var,
            values=("studio", "aurora", "grid", "clean"),
            state="readonly",
        )
        self.background_select.grid(row=3, column=0, sticky="ew")
        self.background_select.bind("<<ComboboxSelected>>", lambda _event: self._save_settings())
        ttk.Checkbutton(performance_frame, text="Modo escuro", variable=self.dark_var, command=self._toggle_theme_from_check).grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Checkbutton(performance_frame, text="Modo performance: pausar preview", variable=self.performance_var, command=self._save_settings).grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(performance_frame, text="Iniciar minimizado", variable=self.auto_start_var, command=self._save_settings).grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(performance_frame, text="Modo streamer seguro", variable=self.streamer_safe_var, command=self._save_settings).grid(row=7, column=0, sticky="w", pady=(8, 0))

        privacy_frame = ttk.LabelFrame(self.system_tab, text="Privacidade e diagnostico", padding=12)
        privacy_frame.grid(row=1, column=0, sticky="ew")
        privacy_frame.columnconfigure(0, weight=1)
        ttk.Button(privacy_frame, text="Abrir pasta de logs", command=self._open_logs).grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(privacy_frame, text="Abrir pasta de backups", command=self._open_backups).grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(privacy_frame, text="Apagar configuracoes locais", command=self._reset_privacy).grid(row=2, column=0, sticky="ew")

        self.status_label = ttk.Label(self.control_frame, text="Microfone desligado", style="Status.TLabel")
        self.status_label.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.avatar_label = ttk.Label(
            self.control_frame,
            text="Assets carregados" if self.settings.streamer_safe else self._image_summary(),
            style="Body.TLabel",
        )
        self.avatar_label.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.hotkey_label = ttk.Label(self.control_frame, text="Atalhos configuraveis", style="Body.TLabel")
        self.hotkey_label.grid(row=5, column=0, sticky="w", pady=(8, 0))

    def _sync_control_scroll(self, _event: tk.Event) -> None:
        self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))

    def _sync_control_width(self, event: tk.Event) -> None:
        self.control_canvas.itemconfigure(self.control_window, width=event.width)
        wrap = max(260, event.width - 56)
        for label in (getattr(self, "status_label", None), getattr(self, "avatar_label", None), getattr(self, "hotkey_label", None)):
            if label is not None:
                label.configure(wraplength=wrap)

    def _bind_control_mousewheel(self, _event: tk.Event) -> None:
        self.bind_all("<MouseWheel>", self._scroll_controls)

    def _unbind_control_mousewheel(self, _event: tk.Event) -> None:
        self.unbind_all("<MouseWheel>")

    def _scroll_controls(self, event: tk.Event) -> None:
        direction = -1 if event.delta > 0 else 1
        self.control_canvas.yview_scroll(direction * 3, "units")

    def _add_slider(self, label: str, variable: tk.DoubleVar, start: float, end: float, row: int) -> None:
        self._add_slider_to(self.tuning_tab, label, variable, start, end, row)

    def _add_slider_to(self, parent: ttk.Frame, label: str, variable: tk.Variable, start: float, end: float, row: int) -> None:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row * 2, column=0, sticky="w", pady=(4, 4))
        slider = ttk.Scale(parent, from_=start, to=end, variable=variable, command=lambda _value: self._save_settings(defer=True))
        slider.grid(row=row * 2 + 1, column=0, sticky="ew")

    def _apply_theme(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.option_add("*TCombobox*Listbox.background", c["panel_2"])
        self.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", c["primary"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.style.configure(".", background=c["bg"], foreground=c["text"], font=("Segoe UI", 10))
        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("TLabel", background=c["bg"], foreground=c["text"])
        self.style.configure("TLabelframe", background=c["panel"], foreground=c["text"], bordercolor=c["line"])
        self.style.configure("TLabelframe.Label", background=c["panel"], foreground=c["muted"], font=("Segoe UI", 10, "bold"))
        self.style.configure("TButton", padding=11, font=("Segoe UI", 10, "bold"), background=c["panel_2"], foreground=c["text"])
        self.style.configure("Primary.TButton", background=c["primary"], foreground="#ffffff")
        self.style.map("Primary.TButton", background=[("active", c["primary_dark"])])
        self.style.map("TButton", background=[("active", c["line"])], foreground=[("disabled", c["muted"])])
        self.style.configure("TCheckbutton", background=c["panel"], foreground=c["text"], font=("Segoe UI", 10))
        self.style.map("TCheckbutton", background=[("active", c["panel"])], foreground=[("active", c["text"])])
        self.style.configure("TCombobox", fieldbackground=c["panel_2"], background=c["panel_2"], foreground=c["text"], arrowcolor=c["muted"], bordercolor=c["line"], lightcolor=c["line"], darkcolor=c["line"])
        self.style.map("TCombobox", fieldbackground=[("readonly", c["panel_2"])], foreground=[("readonly", c["text"])], selectbackground=[("readonly", c["panel_2"])], selectforeground=[("readonly", c["text"])])
        self.style.configure("Horizontal.TScale", background=c["panel"], troughcolor=c["panel_2"])
        self.style.configure("Vertical.TScrollbar", background=c["panel_2"], troughcolor=c["bg"], bordercolor=c["bg"], arrowcolor=c["muted"])
        self.style.configure("Eyebrow.TLabel", foreground=c["muted"], font=("Segoe UI", 9, "bold"))
        self.style.configure("Title.TLabel", foreground=c["text"], font=("Segoe UI", 22, "bold"))
        self.style.configure("PanelTitle.TLabel", foreground=c["text"], font=("Segoe UI", 18, "bold"))
        self.style.configure("Body.TLabel", foreground=c["muted"], font=("Segoe UI", 10))
        self.style.configure("Strong.TLabel", foreground=c["text"], font=("Segoe UI", 11, "bold"))
        self.style.configure("Status.TLabel", foreground=c["text"], background=c["panel_2"], padding=12, font=("Segoe UI", 10, "bold"))
        self.style.configure("Horizontal.TProgressbar", background=c["meter"], troughcolor=c["panel_2"], bordercolor=c["line"])
        self.style.configure("TNotebook", background=c["panel"], borderwidth=0, tabmargins=(0, 4, 0, 0))
        self.style.configure("TNotebook.Tab", background=c["panel_2"], foreground=c["muted"], padding=(10, 8), font=("Segoe UI", 9, "bold"))
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", c["primary"]), ("active", c["panel_2"])],
            foreground=[("selected", "#ffffff"), ("active", c["text"])],
        )
        self.stage_frame.configure(style="Panel.TFrame")
        self.control_frame.configure(style="Panel.TFrame")
        self.style.configure("Panel.TFrame", background=c["panel"])
        self.avatar_canvas.configure(bg=c["panel"])
        self.control_canvas.configure(bg=c["bg"])

    def _bind_hotkeys(self) -> None:
        for sequence in self.local_hotkey_sequences:
            self.unbind_all(sequence)
        self.local_hotkey_sequences.clear()
        self.hotkeys.clear()

        used_sequences: set[str] = set()
        used_hotkeys: set[str] = set()
        for action, hotkey in self._hotkey_config().items():
            normalized = self._normalize_hotkey(hotkey)
            if not normalized or normalized in used_hotkeys:
                continue
            used_hotkeys.add(normalized)
            sequence = self._tk_sequence_for_hotkey(normalized)
            if sequence and sequence not in used_sequences:
                self.bind_all(sequence, lambda _event, selected=action: self._run_hotkey_action(selected))
                self.local_hotkey_sequences.append(sequence)
                used_sequences.add(sequence)
            self.hotkeys.register(normalized, lambda selected=action: self.after(0, lambda: self._run_hotkey_action(selected)))
        self._refresh_hotkey_label()

    def _hotkey_config(self) -> dict[str, str]:
        configured = self.settings.hotkeys or {}
        return {
            action: self._normalize_hotkey(str(configured.get(action, default)))
            for action, default in DEFAULT_HOTKEYS.items()
        }

    def _normalize_hotkey(self, value: str) -> str:
        return value.strip().lower().replace(" ", "").replace("control+", "ctrl+")

    def _tk_sequence_for_hotkey(self, hotkey: str) -> str | None:
        parts = [part for part in hotkey.split("+") if part]
        if not parts:
            return None
        key = parts[-1]
        modifiers = []
        for part in parts[:-1]:
            if part == "ctrl":
                modifiers.append("Control")
            elif part == "alt":
                modifiers.append("Alt")
            elif part == "shift":
                modifiers.append("Shift")
            else:
                return None
        if key.startswith("f") and key[1:].isdigit():
            key_name = key.upper()
        elif len(key) == 1:
            key_name = f"Key-{key}"
        else:
            key_name = key
        return "<" + "-".join([*modifiers, key_name]) + ">"

    def _run_hotkey_action(self, action: str) -> None:
        if action == "toggle_mic":
            self._toggle_microphone()
        elif action == "test_speech":
            self._trigger_test()
        elif action == "show_controls":
            self.show_controls()
        elif action == "toggle_obs":
            self._toggle_obs_window()
        elif action == "toggle_pet":
            self._toggle_pet()
        elif action == "live_mode":
            self._enable_live_mode()
        elif action.startswith("scene_"):
            try:
                self._load_scene_by_index(int(action.rsplit("_", 1)[1]))
            except ValueError:
                return

    def _save_hotkeys(self) -> None:
        self.settings.hotkeys = {
            action: self._normalize_hotkey(variable.get())
            for action, variable in self.hotkey_vars.items()
        }
        self._bind_hotkeys()
        self._save_settings_file()
        self._set_status("Atalhos salvos", 2200)

    def _reset_hotkeys(self) -> None:
        for action, default in DEFAULT_HOTKEYS.items():
            self.hotkey_vars[action].set(default)
        self._save_hotkeys()

    def _refresh_hotkey_label(self) -> None:
        if not hasattr(self, "hotkey_label"):
            return
        enabled = sum(1 for value in self._hotkey_config().values() if value)
        scope = "globais ativos" if self.hotkeys.available else "fallback com janela focada"
        self.hotkey_label.configure(text=f"Atalhos: {enabled} configurados | {scope}")

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

    def _set_status(self, text: str, hold_ms: int = 2200) -> None:
        self.status_label.configure(text=text)
        self.status_hold_until = self._clock_ms() + hold_ms if hold_ms > 0 else 0

    def _status_is_held(self) -> bool:
        return self.status_hold_until > self._clock_ms()

    def _clock_ms(self) -> int:
        return int(self.tk.call("clock", "milliseconds"))

    def _schedule_settings_save(self, delay_ms: int = 700) -> None:
        if self.pending_settings_save is not None:
            self.after_cancel(self.pending_settings_save)
        self.pending_settings_save = self.after(delay_ms, self._flush_settings_save)

    def _flush_settings_save(self) -> None:
        self.pending_settings_save = None
        self.settings.save()

    def _save_settings_file(self, defer: bool = False) -> None:
        if defer:
            self._schedule_settings_save()
            return
        if self.pending_settings_save is not None:
            self.after_cancel(self.pending_settings_save)
            self.pending_settings_save = None
        self.settings.save()

    def _expression_names(self) -> tuple[str, ...]:
        expressions = self.settings.expressions or {}
        names = sorted(set(expressions.keys()) | {self.settings.active_expression, "Default"})
        return tuple(names)

    def _toggle_microphone(self) -> None:
        if self.microphone.is_running:
            self.microphone.stop()
            self.detector.reset()
            self.mic_button.configure(text="Ativar microfone")
            self._set_status("Microfone desligado", 1400)
            return

        try:
            self.microphone.start()
        except RuntimeError as exc:
            self.log.exception("Falha ao iniciar microfone")
            messagebox.showerror("Microfone indisponivel", str(exc))
            return
        except Exception as exc:
            self.log.exception("Falha ao iniciar microfone")
            messagebox.showerror("Erro no microfone", f"Nao foi possivel ativar o microfone:\n{exc}")
            return

        self.mic_button.configure(text="Desativar microfone")
        self._set_status("Ouvindo microfone", 1200)

    def _change_microphone(self) -> None:
        selected = self.microphone_var.get()
        device_index = next((index for name, index in self.input_devices if name == selected), None)
        self.settings.microphone_device = device_index
        try:
            self.microphone.set_device(device_index)
        except Exception as exc:
            self.log.exception("Falha ao trocar microfone")
            messagebox.showerror("Microfone", f"Nao foi possivel trocar microfone:\n{exc}")
            return
        self.settings.save()
        self._set_status(f"Microfone: {selected}")

    def _apply_performance_preset(self) -> None:
        preset = self.performance_preset_var.get()
        if preset == "quality":
            self.performance_var.set(False)
            self.animation_fps_var.set(18)
            self.avatar_shadow_var.set(True)
        elif preset == "balanced":
            self.performance_var.set(False)
            self.animation_fps_var.set(8)
            self.avatar_shadow_var.set(True)
        elif preset == "performance":
            self.performance_var.set(True)
            self.animation_fps_var.set(6)
            self.avatar_shadow_var.set(False)
            self.idle_motion_var.set(False)
        elif preset == "ultra":
            self.performance_var.set(True)
            self.animation_fps_var.set(4)
            self.avatar_shadow_var.set(False)
            self.idle_motion_var.set(False)
        self._save_settings()

    def _toggle_pet(self) -> None:
        self.pet_enabled_var.set(not self.pet_enabled_var.get())
        self._save_settings()
        self._set_status("Pet ligado" if self.pet_enabled_var.get() else "Pet oculto")

    def _open_setup_wizard(self) -> None:
        if getattr(self, "setup_wizard", None) and self.setup_wizard.winfo_exists():
            self.setup_wizard.lift()
            return
        self.setup_wizard = SetupWizard(
            self,
            choose_idle=self._choose_idle_images,
            choose_talk=self._choose_speaking_images,
            toggle_microphone=self._toggle_microphone,
            calibrate=self._start_calibration,
            open_obs=self._toggle_obs_window,
        )

    def _enable_live_mode(self) -> None:
        self.performance_preset_var.set("ultra")
        self.performance_var.set(True)
        self.avatar_shadow_var.set(False)
        self.idle_motion_var.set(False)
        self.obs_top_var.set(False)
        self.auto_hide_var.set(True)
        self._save_settings()
        self._save_obs_settings()
        if not self.obs_window or not self.obs_window.winfo_exists() or self.obs_window.state() == "withdrawn":
            self._toggle_obs_window()
        self._hide_controls()

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
        imported = import_avatar_folder(folder, name)
        self.idle_images = imported["idle"]
        self.speaking_images = imported["talk"]
        self.speaking_low_images = imported["talk_low"]
        self.speaking_mid_images = imported["talk_mid"]
        self.speaking_high_images = imported["talk_high"]
        self.blink_images = imported.get("blink", [])
        self.pet_images = imported.get("pet", [])
        self.pet_speaking_images = imported.get("pet_talk", [])
        self.pet_loud_images = imported.get("pet_loud", [])

        if not self.idle_images and not self.speaking_images:
            messagebox.showinfo("Pasta sem avatar", "Use subpastas idle e talk, ou idle e fala.")
            return

        self._save_image_sets()

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
                "mouth_hold_ticks": int(float(self.mouth_hold_var.get())),
            },
        )
        self._set_status("Avatarpack exportado")

    def _import_pack(self) -> None:
        path = filedialog.askopenfilename(
            title="Importar avatarpack",
            filetypes=(("Avatar pack", "*.avatarpack *.zip"), ("Todos os arquivos", "*.*")),
        )
        if not path:
            return
        pack = import_avatar_pack(path)
        sets = pack["sets"]
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

    def _apply_settings_to_ui(self) -> None:
        self.colors = DARK if self.settings.dark_mode else LIGHT
        self.idle_images = list(self.settings.idle_images or [])
        self.speaking_images = list(self.settings.speaking_images or [])
        self.speaking_low_images = list(self.settings.speaking_low_images or [])
        self.speaking_mid_images = list(self.settings.speaking_mid_images or [])
        self.speaking_high_images = list(self.settings.speaking_high_images or [])
        self.blink_images = list(self.settings.blink_images or [])
        self.pet_images = list(self.settings.pet_images or [])
        self.pet_speaking_images = list(self.settings.pet_speaking_images or [])
        self.pet_loud_images = list(self.settings.pet_loud_images or [])

        self.profile_var.set(self.settings.active_profile)
        self.profile_select.configure(values=self._profile_names())
        self.expression_var.set(self.settings.active_expression)
        self.expression_select.configure(values=self._expression_names())
        self.sensitivity_var.set(self.settings.sensitivity)
        self.smoothing_var.set(self.settings.smoothing)
        self.dark_var.set(self.settings.dark_mode)
        self.background_var.set(self.settings.background)
        self.obs_background_var.set(self.settings.obs_background)
        self.obs_top_var.set(self.settings.obs_always_on_top)
        self.auto_hide_var.set(self.settings.auto_hide_controls)
        self.animation_fps_var.set(self.settings.animation_fps)
        self.obs_resolution_var.set(self.settings.obs_resolution)
        self.obs_borderless_var.set(self.settings.obs_borderless)
        self.avatar_scale_var.set(self.settings.avatar_scale)
        self.avatar_x_var.set(self.settings.avatar_offset_x)
        self.avatar_y_var.set(self.settings.avatar_offset_y)
        self.avatar_rotation_var.set(self.settings.avatar_rotation)
        self.performance_var.set(self.settings.performance_mode)
        self.performance_preset_var.set(self.settings.performance_preset)
        self.idle_motion_var.set(self.settings.idle_motion)
        self.avatar_shadow_var.set(self.settings.avatar_shadow)
        self.streamer_safe_var.set(self.settings.streamer_safe)
        self.pet_enabled_var.set(self.settings.pet_enabled)
        self.pet_size_var.set(self.settings.pet_size)
        self.pet_x_var.set(self.settings.pet_offset_x)
        self.pet_y_var.set(self.settings.pet_offset_y)
        self.pet_reaction_var.set(self.settings.pet_reaction)
        self.pet_strength_var.set(self.settings.pet_reaction_strength)
        self.pet_layer_var.set(self.settings.pet_layer)
        self.pet_opacity_var.set(self.settings.pet_opacity)
        self.pet_mirror_var.set(self.settings.pet_mirror)
        self.mouth_hold_var.set(self.settings.mouth_hold_ticks)
        self.auto_start_var.set(self.settings.auto_start_minimized)
        self.scene_var.set(self.settings.active_scene)
        self._refresh_scene_select()
        for action, value in self._hotkey_config().items():
            self.hotkey_vars[action].set(value)
        self._bind_hotkeys()

        self.microphone.set_device(self.settings.microphone_device)
        self.detector.sensitivity = self.settings.sensitivity
        self.detector.smoothing = self.settings.smoothing
        self.detector.mouth_hold_ticks = self.settings.mouth_hold_ticks
        self._apply_theme()
        self._save_image_sets()
        self._save_obs_settings()

    def _trigger_test(self) -> None:
        self.test_ticks = 90

    def _start_calibration(self) -> None:
        if not self.microphone.is_running:
            try:
                self.microphone.start()
                self.mic_button.configure(text="Desativar microfone")
            except Exception as exc:
                messagebox.showerror("Calibracao", f"Ative o microfone primeiro:\n{exc}")
                return
        self.calibration_samples = []
        self.calibration_ticks = 180
        self._set_status("Calibrando ruido por 3 segundos...", 3200)

    def _toggle_theme(self) -> None:
        self.dark_var.set(not self.dark_var.get())
        self._toggle_theme_from_check()

    def _toggle_theme_from_check(self) -> None:
        self.settings.dark_mode = self.dark_var.get()
        self.colors = DARK if self.settings.dark_mode else LIGHT
        self._apply_theme()
        self._save_settings_file()

    def _save_settings(self, defer: bool = False) -> None:
        self.settings.sensitivity = float(self.sensitivity_var.get())
        self.settings.smoothing = float(self.smoothing_var.get())
        self.settings.background = self.background_var.get()
        self.settings.animation_fps = int(float(self.animation_fps_var.get()))
        self.settings.avatar_scale = float(self.avatar_scale_var.get())
        self.settings.avatar_offset_x = float(self.avatar_x_var.get())
        self.settings.avatar_offset_y = float(self.avatar_y_var.get())
        self.settings.avatar_rotation = float(self.avatar_rotation_var.get())
        self.settings.performance_mode = self.performance_var.get()
        self.settings.performance_preset = self.performance_preset_var.get()
        self.settings.idle_motion = self.idle_motion_var.get()
        self.settings.avatar_shadow = self.avatar_shadow_var.get()
        self.settings.streamer_safe = self.streamer_safe_var.get()
        self.settings.pet_enabled = self.pet_enabled_var.get()
        self.settings.pet_size = float(self.pet_size_var.get())
        self.settings.pet_offset_x = float(self.pet_x_var.get())
        self.settings.pet_offset_y = float(self.pet_y_var.get())
        self.settings.pet_reaction = self.pet_reaction_var.get()
        self.settings.pet_reaction_strength = float(self.pet_strength_var.get())
        self.settings.pet_layer = self.pet_layer_var.get()
        self.settings.pet_opacity = float(self.pet_opacity_var.get())
        self.settings.pet_mirror = self.pet_mirror_var.get()
        self.settings.mouth_hold_ticks = int(float(self.mouth_hold_var.get()))
        self.settings.auto_start_minimized = self.auto_start_var.get()
        self.detector.sensitivity = self.settings.sensitivity
        self.detector.smoothing = self.settings.smoothing
        self.detector.mouth_hold_ticks = self.settings.mouth_hold_ticks
        self.avatar_canvas.set_background(self.settings.background)
        self.avatar_canvas.set_animation_fps(self.settings.animation_fps)
        self.avatar_canvas.set_transform(
            self.settings.avatar_scale,
            self.settings.avatar_offset_x,
            self.settings.avatar_offset_y,
            self.settings.avatar_rotation,
        )
        self.avatar_canvas.set_visual_options(
            self.settings.idle_motion,
            self.settings.avatar_shadow,
            self.settings.pet_enabled,
            self.settings.pet_size,
            self.settings.pet_offset_x,
            self.settings.pet_offset_y,
            self.settings.pet_reaction,
            self.settings.pet_reaction_strength,
            self.settings.pet_layer,
            self.settings.pet_opacity,
            self.settings.pet_mirror,
        )
        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_animation_fps(self.settings.animation_fps)
            self.obs_window.set_transform(
                self.settings.avatar_scale,
                self.settings.avatar_offset_x,
                self.settings.avatar_offset_y,
                self.settings.avatar_rotation,
            )
            self.obs_window.set_visual_options(
                self.settings.idle_motion,
                self.settings.avatar_shadow,
                self.settings.pet_enabled,
                self.settings.pet_size,
                self.settings.pet_offset_x,
                self.settings.pet_offset_y,
                self.settings.pet_reaction,
                self.settings.pet_reaction_strength,
                self.settings.pet_layer,
                self.settings.pet_opacity,
                self.settings.pet_mirror,
            )
        self._save_settings_file(defer=defer)

    def _toggle_obs_window(self) -> None:
        if self.obs_window and self.obs_window.winfo_exists() and self.obs_window.state() != "withdrawn":
            self.obs_window.withdraw()
            self.obs_button.configure(text="Abrir janela OBS")
            return

        if not self.obs_window or not self.obs_window.winfo_exists():
            self.obs_window = ObsOutputWindow(
                self,
                self.idle_images,
                self.speaking_images,
                self.speaking_low_images,
                self.speaking_mid_images,
                self.speaking_high_images,
                self.blink_images,
                self.pet_images,
                self.pet_speaking_images,
                self.pet_loud_images,
                self.settings.obs_background,
                self.settings.obs_always_on_top,
                self.settings.animation_fps,
                self.settings.obs_resolution,
                self.settings.obs_borderless,
            )
            self.obs_window.set_transform(
                self.settings.avatar_scale,
                self.settings.avatar_offset_x,
                self.settings.avatar_offset_y,
                self.settings.avatar_rotation,
            )
            self.obs_window.set_visual_options(
                self.settings.idle_motion,
                self.settings.avatar_shadow,
                self.settings.pet_enabled,
                self.settings.pet_size,
                self.settings.pet_offset_x,
                self.settings.pet_offset_y,
                self.settings.pet_reaction,
                self.settings.pet_reaction_strength,
                self.settings.pet_layer,
                self.settings.pet_opacity,
                self.settings.pet_mirror,
            )
        else:
            self.obs_window.deiconify()
            if self.settings.obs_always_on_top:
                self.obs_window.lift()

        self.obs_button.configure(text="Ocultar janela OBS")
        if self.settings.auto_hide_controls:
            self._hide_controls()

    def _save_obs_settings(self) -> None:
        self.settings.obs_background = self.obs_background_var.get()
        self.settings.obs_always_on_top = self.obs_top_var.get()
        self.settings.auto_hide_controls = self.auto_hide_var.get()
        self.settings.obs_resolution = self.obs_resolution_var.get()
        self.settings.obs_borderless = self.obs_borderless_var.get()

        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_background(self.settings.obs_background)
            self.obs_window.set_always_on_top(self.settings.obs_always_on_top)
            self.obs_window.set_resolution(self.settings.obs_resolution)
            self.obs_window.set_borderless(self.settings.obs_borderless)

        self._save_settings_file()

    def _hide_controls(self) -> None:
        if not self.obs_window or not self.obs_window.winfo_exists() or self.obs_window.state() == "withdrawn":
            self._toggle_obs_window()
        self._send_obs_to_back(save=True)
        self.withdraw()

    def _send_obs_to_back(self, save: bool = False) -> None:
        self.obs_top_var.set(False)
        self.settings.obs_always_on_top = False
        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.send_to_back()
        if save:
            self.settings.save()
        self._set_status("OBS rodando atras das janelas")

    def _show_obs_assistant(self) -> None:
        messagebox.showinfo(
            "Assistente OBS",
            "1. Clique em Abrir janela OBS.\n"
            "2. No OBS, adicione Window Capture.\n"
            "3. Escolha OBS Avatar Output.\n"
            "4. Adicione filtro Chroma Key se usar fundo verde/magenta/azul.\n"
            "5. Desmarque Manter janela OBS no topo antes de jogar.\n"
            "6. Use Enviar OBS para tras ou Modo live.\n"
            "7. Ative OBS Virtual Camera para usar em Discord/Zoom.",
        )

    def show_controls(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _open_logs(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(LOG_DIR)
        except Exception as exc:
            self.log.exception("Falha ao abrir logs")
            messagebox.showerror("Logs", str(exc))

    def _open_backups(self) -> None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(BACKUP_DIR)
        except Exception as exc:
            self.log.exception("Falha ao abrir backups")
            messagebox.showerror("Backups", str(exc))

    def _reset_privacy(self) -> None:
        if not messagebox.askyesno("Apagar dados locais", "Apagar configuracoes, perfis, caminhos de imagens e logs locais?"):
            return
        self.microphone.stop()
        self.hotkeys.close()
        self.tray.stop()
        self.log.info("Apagando dados locais")
        close_logger()
        self._close_explorer_windows_for(APP_DIR)
        try:
            if APP_DIR.exists():
                self._remove_app_dir()
        except Exception as exc:
            messagebox.showerror("Privacidade", f"Nao foi possivel apagar tudo:\n{exc}")
            return
        messagebox.showinfo("Privacidade", "Dados locais apagados. O app sera fechado.")
        super().destroy()

    def _remove_app_dir(self) -> None:
        last_error: Exception | None = None
        for _attempt in range(4):
            try:
                shutil.rmtree(APP_DIR)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.25)
        if last_error is not None:
            raise last_error

    def _close_explorer_windows_for(self, path: Path) -> None:
        target = str(path).replace("\\", "\\\\")
        script = (
            "$shell = New-Object -ComObject Shell.Application; "
            "$shell.Windows() | ForEach-Object { "
            "try { "
            "$p = $_.Document.Folder.Self.Path; "
            f"if ($p -like '{target}*') {{ $_.Quit() }} "
            "} catch {} "
            "}"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except Exception:
            pass

    def _tick(self) -> None:
        if self.test_ticks > 0:
            raw_level = 0.32 + math.sin(self.test_ticks / 3) * 0.12
            self.test_ticks -= 1
        else:
            raw_level = self.microphone.read_level()

        state = self.detector.update(raw_level)
        if self.calibration_ticks > 0:
            self.calibration_samples.append(raw_level)
            self.calibration_ticks -= 1
            if self.calibration_ticks == 0:
                base = max(self.calibration_samples or [0.02])
                calibrated = max(0.05, min(0.45, base * 2.7 + 0.035))
                self.sensitivity_var.set(calibrated)
                self._save_settings()
                self._set_status(f"Sensibilidade calibrada: {int(calibrated * 100)}%", 2600)

        speaking = state.speaking or self.test_ticks > 0
        preset = self.settings.performance_preset
        if not self.settings.performance_mode and self.state() != "withdrawn":
            self.avatar_canvas.update_state(speaking, state.level)
        if self.obs_window and self.obs_window.winfo_exists() and self.obs_window.state() != "withdrawn":
            if preset != "ultra" or speaking != self.last_speaking or self.ui_tick % 2 == 0:
                self.obs_window.update_state(speaking, state.level)

        self.ui_tick += 1

        status_mod = 45 if preset in ("performance", "ultra") else 15
        if self._status_is_held():
            pass
        elif self.microphone.is_running and (speaking != self.last_speaking or self.ui_tick % status_mod == 0):
            if self.calibration_ticks <= 0:
                self.status_label.configure(text="Voz detectada" if speaking else f"Ouvindo microfone | FPS {self.render_fps}")
            self.last_speaking = speaking
        elif self.test_ticks > 0:
            self.status_label.configure(text="Teste de fala ativo")
        else:
            self.status_label.configure(text="Microfone desligado")

        self.render_frames += 1
        now = self._clock_ms()
        if self.last_fps_time == 0:
            self.last_fps_time = now
        elif now - self.last_fps_time >= 1000:
            self.render_fps = self.render_frames
            self.render_frames = 0
            self.last_fps_time = now

        delay = 100 if preset == "ultra" else 50 if preset == "performance" else 33
        idle_background = (
            not self.microphone.is_running
            and self.test_ticks <= 0
            and self.calibration_ticks <= 0
            and (not self.obs_window or not self.obs_window.winfo_exists() or self.obs_window.state() == "withdrawn")
        )
        if idle_background:
            delay = max(delay, 180)
        self.after(delay, self._tick)

    def destroy(self) -> None:
        self.log.info("AvatarCam encerrado")
        if self.pending_settings_save is not None:
            self.after_cancel(self.pending_settings_save)
            self.pending_settings_save = None
            self.settings.save()
        self.tray.stop()
        self.hotkeys.close()
        self.microphone.stop()
        close_logger()
        super().destroy()
