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
from avatarcam.ui.studio_controls import StudioControls
from avatarcam.ui.profile_controls import ProfileControls
from avatarcam.ui.scene_controls import SceneControls
from avatarcam.ui.asset_controls import AssetControls
from avatarcam.ui.shortcut_controls import ShortcutControls
from avatarcam.ui.shortcut_defaults import DEFAULT_HOTKEYS, HOTKEY_ACTION_LABELS, HOTKEY_CHOICES
from avatarcam.core.timing import Deadline, calibrate_noise


class AvatarCamApp(StudioControls, ProfileControls, SceneControls, AssetControls, ShortcutControls, tk.Tk):
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
        self.test_deadline = None
        self.calibration_samples: list[float] = []
        self.calibration_deadline = None
        self.last_visual_update = 0.0
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
        self._init_studio()

        self._configure_style()
        self._build_layout()
        self._apply_theme()
        self._bind_hotkeys()
        self.tray_available = self.tray.start()
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
        ttk.Label(header, text="2DCam STUDIO", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Sua voz. Seu avatar. Sua live.", style="Title.TLabel").grid(row=1, column=0, sticky="w")
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
        self._build_studio(header)

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
        self.advanced_var.set(self.settings.advanced_mode)
        self.speech_mode_var.set(self.settings.speech_mode)
        self.expression3d_var.set(self.settings.expression3d)
        self.fps3d_var.set(self.settings.fps3d)
        self.rotate3d_var.set(self.settings.auto_rotate3d)
        self.microphone.speech_mode = self.settings.speech_mode
        self.model_label.configure(text=self._model_description())
        self._set_simple_mode(save=False)
        self._apply_theme()
        self._save_image_sets()
        self._save_obs_settings()

    def _trigger_test(self) -> None:
        if self.calibration_deadline and self.calibration_deadline.active:
            self._set_status('Aguarde a calibracao antes do teste.', 2000)
            return
        self.test_deadline = Deadline(3.0)

    def _start_calibration(self) -> None:
        if not self.microphone.is_running:
            try:
                self.microphone.start()
                self.mic_button.configure(text="Desativar microfone")
            except Exception as exc:
                messagebox.showerror("Calibracao", f"Ative o microfone primeiro:\n{exc}")
                return
        self.calibration_samples = []
        self.test_deadline = None
        self.calibration_deadline = Deadline(3.0)
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
        if not getattr(self, 'tray_available', False):
            if messagebox.askyesno('Sair', 'A bandeja esta indisponivel. Deseja encerrar o app?'):
                self.destroy()
            return
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
        if self.jobs:
            self._set_status('Aguarde a importacao antes de apagar dados.', 3000)
            return
        if not messagebox.askyesno("Apagar dados locais", "Apagar configuracoes, perfis, caminhos de imagens e logs locais?"):
            return
        self._closing = True
        if getattr(self, '_tick_id', None): self.after_cancel(self._tick_id)
        if self.pending_settings_save:
            self.after_cancel(self.pending_settings_save)
            self.pending_settings_save = None
        if self.viewer_server: self.viewer_server.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.microphone.stop()
        self.hotkeys.close()
        self.tray.stop()
        self.log.info('Apagando dados locais')
        close_logger()
        self._close_explorer_windows_for(APP_DIR)
        try:
            if APP_DIR.exists():
                self._remove_app_dir()
        except Exception as exc:
            messagebox.showerror("Privacidade", f"Nao foi possivel apagar tudo:\n{exc}")
            super().destroy()
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
        if self._closing:
            return
        self._poll_jobs()
        now = time.monotonic()
        testing = bool(self.test_deadline and self.test_deadline.active)
        raw_level = (.32 + math.sin(now * 10) * .12) if testing else self.microphone.read_level()
        voice_allowed = testing or self.microphone.voice_allowed
        state = self.detector.update(raw_level, voice_allowed)
        if self.calibration_deadline:
            if self.calibration_deadline.active:
                self.calibration_samples.append(raw_level)
                self._set_status(f'Calibrando: fique em silencio por {self.calibration_deadline.remaining:.1f} s', 100)
            else:
                floor, sensitivity = calibrate_noise(self.calibration_samples)
                self.settings.noise_floor = floor
                self.sensitivity_var.set(sensitivity)
                self._save_settings()
                self.calibration_deadline = None
                self.detector.reset()
                self._set_status(f'Calibracao concluida: sensibilidade {sensitivity:.0%}', 3000)
        speaking = state.speaking or testing
        preset = self.settings.performance_preset
        visual_delay = .1 if preset == 'ultra' else .05 if preset == 'performance' else .033
        if now - self.last_visual_update >= visual_delay:
            self.last_visual_update = now
            if not self.settings.performance_mode and self.state() == 'normal':
                self.avatar_canvas.update_state(speaking, state.level)
            if self.obs_window and self.obs_window.winfo_exists() and self.obs_window.state() == 'normal':
                self.obs_window.update_state(speaking, state.level)
            self.render_frames += 1
        self._publish3d(state.level, speaking)
        self.ui_tick += 1
        if self.ui_tick % 5 == 0:
            self.audio_meter['value'] = state.level
            self.audio_hint.configure(text=f'Volume {state.level:.0%} | limiar {self.settings.sensitivity:.0%} | ' + ('Voz detectada' if speaking else 'Silencio'))
        if self.microphone._stream is not None and (not self.microphone.is_running or now - self.microphone.last_audio_time > 3):
            try:
                self.microphone.stop()
            except Exception:
                self.log.exception('Falha ao liberar microfone desconectado')
            self.mic_button.configure(text='Reconectar microfone')
            self.detector.reset()
            self._set_status('Microfone desconectado. Atualize a lista e reconecte.', 6000)
        if not self._status_is_held() and self.ui_tick % 10 == 0:
            text = 'Teste de fala ativo' if testing else ('Voz detectada' if speaking else 'Ouvindo microfone') if self.microphone.is_running else 'Microfone desligado'
            self.status_label.configure(text=text)
        self.last_speaking = speaking
        if not self.last_fps_time:
            self.last_fps_time = now
        elif now - self.last_fps_time >= 1:
            self.render_fps = round(self.render_frames / (now - self.last_fps_time))
            self.render_frames = 0
            self.last_fps_time = now
        # Captura e deteccao de fala continuam rapidas em qualquer preset visual.
        idle = not self.microphone.is_running and not testing and not self.calibration_deadline and not self.jobs and not self.viewer_server and self.state() == 'withdrawn' and (not self.obs_window or self.obs_window.state() == 'withdrawn')
        self._tick_id = self.after(100 if idle else 20, self._tick)

    def destroy(self) -> None:
        self._closing = True
        if getattr(self, '_tick_id', None):
            self.after_cancel(self._tick_id)
        if self.viewer_server:
            self.viewer_server.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.log.info('2DCam Studio encerrado')
        if self.pending_settings_save is not None:
            self.after_cancel(self.pending_settings_save)
            self.pending_settings_save = None
            self.settings.save()
        self.tray.stop()
        self.hotkeys.close()
        try:
            self.microphone.stop()
        except Exception as exc:
            self.log.warning('Microfone ja desconectado durante encerramento: %s', exc)
        finally:
            close_logger()
            super().destroy()
