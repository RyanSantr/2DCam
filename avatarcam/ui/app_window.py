from __future__ import annotations

import math
import os
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from avatarcam.core.app_log import setup_logger
from avatarcam.core.avatar_pack import export_avatar_pack, import_avatar_folder, import_avatar_pack
from avatarcam.core.hotkeys import HotkeyManager
from avatarcam.core.settings import APP_DIR, LOG_DIR, SETTINGS_FILE
from avatarcam.audio.microphone import MicrophoneInput
from avatarcam.core.settings import Settings
from avatarcam.core.speech_detector import SpeechDetector
from avatarcam.ui.avatar_canvas import AvatarCanvas
from avatarcam.ui.obs_window import ObsOutputWindow
from avatarcam.ui.theme import DARK, LIGHT, OBS_BACKGROUNDS
from avatarcam.ui.tray import TrayController


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
        self.detector = SpeechDetector(self.settings.sensitivity, self.settings.smoothing)
        self.test_ticks = 0
        self.calibration_samples: list[float] = []
        self.calibration_ticks = 0
        self.render_frames = 0
        self.last_fps_time = 0.0
        self.render_fps = 0
        self.obs_window: ObsOutputWindow | None = None
        self.idle_images = list(self.settings.idle_images or [])
        self.speaking_images = list(self.settings.speaking_images or [])
        self.speaking_low_images = list(self.settings.speaking_low_images or [])
        self.speaking_mid_images = list(self.settings.speaking_mid_images or [])
        self.speaking_high_images = list(self.settings.speaking_high_images or [])
        self.expression_var = tk.StringVar(value=self.settings.active_expression)
        self.hotkeys = HotkeyManager()
        self.tray = TrayController(self)

        self._configure_style()
        self._build_layout()
        self._apply_theme()
        self._bind_hotkeys()
        self.tray.start()
        self.protocol("WM_DELETE_WINDOW", self._hide_controls)
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
        )
        self.avatar_canvas.set_animation_fps(self.settings.animation_fps)
        self.avatar_canvas.set_background(self.settings.background)
        self.avatar_canvas.set_transform(
            self.settings.avatar_scale,
            self.settings.avatar_offset_x,
            self.settings.avatar_offset_y,
        )
        self.avatar_canvas.set_visual_options(self.settings.idle_motion, self.settings.avatar_shadow)

        meter_box = ttk.Frame(self.stage_frame)
        meter_box.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        meter_box.columnconfigure(0, weight=1)
        ttk.Label(meter_box, text="Volume do microfone", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        self.volume_label = ttk.Label(meter_box, text="0%", style="Strong.TLabel")
        self.volume_label.grid(row=0, column=1, sticky="e")
        self.volume_bar = ttk.Progressbar(meter_box, maximum=100, mode="determinate")
        self.volume_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.control_canvas = tk.Canvas(self.container, highlightthickness=0, borderwidth=0)
        self.control_canvas.grid(row=0, column=1, sticky="nsew")
        self.control_scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.control_canvas.yview)
        self.control_scrollbar.grid(row=0, column=2, sticky="ns")
        self.control_canvas.configure(yscrollcommand=self.control_scrollbar.set)
        self.control_frame = ttk.Frame(self.control_canvas, padding=18)
        self.control_window = self.control_canvas.create_window((0, 0), window=self.control_frame, anchor="nw")
        self.control_frame.bind("<Configure>", self._sync_control_scroll)
        self.control_canvas.bind("<Configure>", self._sync_control_width)
        self.control_frame.columnconfigure(0, weight=1)

        ttk.Label(self.control_frame, text="Controles", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.control_frame, text="Operacao ao vivo", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 16))

        self.mic_button = ttk.Button(self.control_frame, text="Ativar microfone", command=self._toggle_microphone, style="Primary.TButton")
        self.mic_button.grid(row=2, column=0, sticky="ew", pady=5)

        profile_row = ttk.Frame(self.control_frame)
        profile_row.grid(row=3, column=0, sticky="ew", pady=(0, 5))
        profile_row.columnconfigure(0, weight=1)
        self.profile_var = tk.StringVar(value=self.settings.active_profile)
        self.profile_select = ttk.Combobox(profile_row, textvariable=self.profile_var, values=self._profile_names(), state="readonly")
        self.profile_select.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.profile_select.bind("<<ComboboxSelected>>", lambda _event: self._load_profile(self.profile_var.get()))
        ttk.Button(profile_row, text="Salvar", command=self._save_profile).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(profile_row, text="Novo", command=self._new_profile).grid(row=0, column=2)

        self.idle_button = ttk.Button(self.control_frame, text="Escolher imagens idle", command=self._choose_idle_images)
        self.idle_button.grid(row=4, column=0, sticky="ew", pady=5)
        self.speaking_button = ttk.Button(self.control_frame, text="Escolher fala padrao", command=self._choose_speaking_images)
        self.speaking_button.grid(row=5, column=0, sticky="ew", pady=5)
        self.speaking_levels_button = ttk.Button(self.control_frame, text="Escolher fala baixa/media/alta", command=self._choose_level_images)
        self.speaking_levels_button.grid(row=6, column=0, sticky="ew", pady=5)
        self.import_folder_button = ttk.Button(self.control_frame, text="Importar pasta de avatar", command=self._import_avatar_folder)
        self.import_folder_button.grid(row=7, column=0, sticky="ew", pady=5)
        self.pack_row = ttk.Frame(self.control_frame)
        self.pack_row.grid(row=8, column=0, sticky="ew", pady=5)
        self.pack_row.columnconfigure(0, weight=1)
        ttk.Button(self.pack_row, text="Importar .avatarpack", command=self._import_pack).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(self.pack_row, text="Exportar", command=self._export_pack).grid(row=0, column=1, sticky="ew")
        self.clear_images_button = ttk.Button(self.control_frame, text="Limpar imagens", command=self._clear_images)
        self.clear_images_button.grid(row=9, column=0, sticky="ew", pady=5)

        self.test_button = ttk.Button(self.control_frame, text="Teste de fala", command=self._trigger_test)
        self.test_button.grid(row=10, column=0, sticky="ew", pady=5)
        self.calibrate_button = ttk.Button(self.control_frame, text="Calibrar ruido ambiente", command=self._start_calibration)
        self.calibrate_button.grid(row=11, column=0, sticky="ew", pady=5)

        self.settings_frame = ttk.LabelFrame(self.control_frame, text="Configuracoes", padding=14)
        self.settings_frame.grid(row=12, column=0, sticky="ew", pady=(18, 10))
        self.settings_frame.columnconfigure(0, weight=1)

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
        self.performance_var = tk.BooleanVar(value=self.settings.performance_mode)
        self.idle_motion_var = tk.BooleanVar(value=self.settings.idle_motion)
        self.avatar_shadow_var = tk.BooleanVar(value=self.settings.avatar_shadow)
        self.streamer_safe_var = tk.BooleanVar(value=self.settings.streamer_safe)

        self._add_slider("Sensibilidade", self.sensitivity_var, 0.04, 0.7, 0)
        self._add_slider("Suavizacao", self.smoothing_var, 0.1, 0.95, 1)
        self._add_slider("FPS da animacao", self.animation_fps_var, 1, 30, 2)
        self._add_slider("Escala avatar", self.avatar_scale_var, 0.25, 2.5, 3)
        self._add_slider("Posicao X", self.avatar_x_var, -0.8, 0.8, 4)
        self._add_slider("Posicao Y", self.avatar_y_var, -0.8, 0.8, 5)

        ttk.Label(self.settings_frame, text="Fundo preview", style="Body.TLabel").grid(row=12, column=0, sticky="w", pady=(12, 4))
        self.background_select = ttk.Combobox(
            self.settings_frame,
            textvariable=self.background_var,
            values=("studio", "aurora", "grid", "clean"),
            state="readonly",
        )
        self.background_select.grid(row=13, column=0, sticky="ew")
        self.background_select.bind("<<ComboboxSelected>>", lambda _event: self._save_settings())

        self.dark_check = ttk.Checkbutton(self.settings_frame, text="Modo escuro", variable=self.dark_var, command=self._toggle_theme_from_check)
        self.dark_check.grid(row=14, column=0, sticky="w", pady=(14, 0))
        self.performance_check = ttk.Checkbutton(self.settings_frame, text="Modo performance: pausar preview", variable=self.performance_var, command=self._save_settings)
        self.performance_check.grid(row=15, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(self.settings_frame, text="Movimento vertical automatico", variable=self.idle_motion_var, command=self._save_settings).grid(row=16, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(self.settings_frame, text="Sombra do avatar", variable=self.avatar_shadow_var, command=self._save_settings).grid(row=17, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(self.settings_frame, text="Modo streamer seguro", variable=self.streamer_safe_var, command=self._save_settings).grid(row=18, column=0, sticky="w", pady=(8, 0))

        self.expression_frame = ttk.LabelFrame(self.control_frame, text="Expressoes", padding=14)
        self.expression_frame.grid(row=13, column=0, sticky="ew", pady=(10, 10))
        self.expression_frame.columnconfigure(0, weight=1)
        self.expression_select = ttk.Combobox(self.expression_frame, textvariable=self.expression_var, values=self._expression_names(), state="readonly")
        self.expression_select.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.expression_select.bind("<<ComboboxSelected>>", lambda _event: self._load_expression(self.expression_var.get()))
        ttk.Button(self.expression_frame, text="Salvar expressao atual", command=self._save_expression).grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(self.expression_frame, text="Nova expressao", command=self._new_expression).grid(row=2, column=0, sticky="ew")

        self.obs_frame = ttk.LabelFrame(self.control_frame, text="OBS", padding=14)
        self.obs_frame.grid(row=14, column=0, sticky="ew", pady=(10, 10))
        self.obs_frame.columnconfigure(0, weight=1)

        self.obs_button = ttk.Button(self.obs_frame, text="Abrir janela OBS", command=self._toggle_obs_window, style="Primary.TButton")
        self.obs_button.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(self.obs_frame, text="Fundo da captura", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 4))
        self.obs_background_select = ttk.Combobox(
            self.obs_frame,
            textvariable=self.obs_background_var,
            values=tuple(OBS_BACKGROUNDS.keys()),
            state="readonly",
        )
        self.obs_background_select.grid(row=2, column=0, sticky="ew")
        self.obs_background_select.bind("<<ComboboxSelected>>", lambda _event: self._save_obs_settings())

        self.obs_top_check = ttk.Checkbutton(
            self.obs_frame,
            text="Manter janela OBS no topo",
            variable=self.obs_top_var,
            command=self._save_obs_settings,
        )
        self.obs_top_check.grid(row=3, column=0, sticky="w", pady=(10, 0))

        ttk.Label(self.obs_frame, text="Resolucao", style="Body.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 4))
        self.obs_resolution_select = ttk.Combobox(
            self.obs_frame,
            textvariable=self.obs_resolution_var,
            values=("1280x720", "1920x1080", "1080x1920", "960x540", "640x360"),
            state="readonly",
        )
        self.obs_resolution_select.grid(row=5, column=0, sticky="ew")
        self.obs_resolution_select.bind("<<ComboboxSelected>>", lambda _event: self._save_obs_settings())

        self.obs_borderless_check = ttk.Checkbutton(
            self.obs_frame,
            text="Janela OBS sem borda",
            variable=self.obs_borderless_var,
            command=self._save_obs_settings,
        )
        self.obs_borderless_check.grid(row=6, column=0, sticky="w", pady=(8, 0))

        self.auto_hide_check = ttk.Checkbutton(
            self.obs_frame,
            text="Esconder controles ao abrir OBS",
            variable=self.auto_hide_var,
            command=self._save_obs_settings,
        )
        self.auto_hide_check.grid(row=7, column=0, sticky="w", pady=(8, 0))

        self.hide_button = ttk.Button(self.obs_frame, text="Modo live: ocultar controles", command=self._hide_controls)
        self.hide_button.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        self.back_button = ttk.Button(self.obs_frame, text="Enviar OBS para tras", command=self._send_obs_to_back)
        self.back_button.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(self.obs_frame, text="Assistente OBS", command=self._show_obs_assistant).grid(row=10, column=0, sticky="ew", pady=(8, 0))

        self.privacy_frame = ttk.LabelFrame(self.control_frame, text="Privacidade e diagnostico", padding=14)
        self.privacy_frame.grid(row=15, column=0, sticky="ew", pady=(10, 10))
        self.privacy_frame.columnconfigure(0, weight=1)
        ttk.Button(self.privacy_frame, text="Abrir pasta de logs", command=self._open_logs).grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(self.privacy_frame, text="Apagar configuracoes locais", command=self._reset_privacy).grid(row=1, column=0, sticky="ew")

        self.status_label = ttk.Label(self.control_frame, text="Microfone desligado", style="Status.TLabel")
        self.status_label.grid(row=16, column=0, sticky="ew", pady=(10, 0))
        self.avatar_label = ttk.Label(
            self.control_frame,
            text="Assets carregados" if self.settings.streamer_safe else self._image_summary(),
            style="Body.TLabel",
        )
        self.avatar_label.grid(row=17, column=0, sticky="w", pady=(8, 0))
        hotkey_text = "Hotkeys: F8 mic, F9 teste, F10 controles, F11 OBS"
        if self.hotkeys.available:
            hotkey_text += " | globais ativos"
        self.hotkey_label = ttk.Label(self.control_frame, text=hotkey_text, style="Body.TLabel")
        self.hotkey_label.grid(row=18, column=0, sticky="w", pady=(8, 0))

    def _sync_control_scroll(self, _event: tk.Event) -> None:
        self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))

    def _sync_control_width(self, event: tk.Event) -> None:
        self.control_canvas.itemconfigure(self.control_window, width=event.width)

    def _add_slider(self, label: str, variable: tk.DoubleVar, start: float, end: float, row: int) -> None:
        ttk.Label(self.settings_frame, text=label, style="Body.TLabel").grid(row=row * 2, column=0, sticky="w", pady=(4, 4))
        slider = ttk.Scale(self.settings_frame, from_=start, to=end, variable=variable, command=lambda _value: self._save_settings())
        slider.grid(row=row * 2 + 1, column=0, sticky="ew")

    def _apply_theme(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.style.configure(".", background=c["bg"], foreground=c["text"], font=("Segoe UI", 10))
        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("TLabel", background=c["bg"], foreground=c["text"])
        self.style.configure("TLabelframe", background=c["panel"], foreground=c["text"], bordercolor=c["line"])
        self.style.configure("TLabelframe.Label", background=c["panel"], foreground=c["muted"], font=("Segoe UI", 10, "bold"))
        self.style.configure("TButton", padding=11, font=("Segoe UI", 10, "bold"), background=c["panel_2"], foreground=c["text"])
        self.style.configure("Primary.TButton", background=c["primary"], foreground="#ffffff")
        self.style.map("Primary.TButton", background=[("active", c["primary_dark"])])
        self.style.configure("Eyebrow.TLabel", foreground=c["muted"], font=("Segoe UI", 9, "bold"))
        self.style.configure("Title.TLabel", foreground=c["text"], font=("Segoe UI", 22, "bold"))
        self.style.configure("PanelTitle.TLabel", foreground=c["text"], font=("Segoe UI", 18, "bold"))
        self.style.configure("Body.TLabel", foreground=c["muted"], font=("Segoe UI", 10))
        self.style.configure("Strong.TLabel", foreground=c["text"], font=("Segoe UI", 11, "bold"))
        self.style.configure("Status.TLabel", foreground=c["text"], background=c["panel_2"], padding=12, font=("Segoe UI", 10, "bold"))
        self.style.configure("Horizontal.TProgressbar", background=c["meter"], troughcolor=c["panel_2"], bordercolor=c["line"])
        self.stage_frame.configure(style="Panel.TFrame")
        self.control_frame.configure(style="Panel.TFrame")
        self.style.configure("Panel.TFrame", background=c["panel"])
        self.avatar_canvas.configure(bg=c["panel"])
        self.control_canvas.configure(bg=c["bg"])

    def _bind_hotkeys(self) -> None:
        self.bind("<F8>", lambda _event: self._toggle_microphone())
        self.bind("<F9>", lambda _event: self._trigger_test())
        self.bind("<F10>", lambda _event: self.show_controls())
        self.bind("<F11>", lambda _event: self._toggle_obs_window())
        for index in range(1, 5):
            self.bind(f"<Control-Key-{index}>", lambda _event, i=index: self._load_expression_by_index(i))
        self.hotkeys.register("f8", lambda: self.after(0, self._toggle_microphone))
        self.hotkeys.register("f9", lambda: self.after(0, self._trigger_test))
        self.hotkeys.register("f10", lambda: self.after(0, self.show_controls))
        self.hotkeys.register("f11", lambda: self.after(0, self._toggle_obs_window))
        for index in range(1, 5):
            self.hotkeys.register(f"ctrl+{index}", lambda i=index: self.after(0, lambda: self._load_expression_by_index(i)))

    def _profile_names(self) -> tuple[str, ...]:
        profiles = self.settings.profiles or {}
        names = sorted(set(profiles.keys()) | {self.settings.active_profile, "Default"})
        return tuple(names)

    def _expression_names(self) -> tuple[str, ...]:
        expressions = self.settings.expressions or {}
        names = sorted(set(expressions.keys()) | {self.settings.active_expression, "Default"})
        return tuple(names)

    def _toggle_microphone(self) -> None:
        if self.microphone.is_running:
            self.microphone.stop()
            self.detector.reset()
            self.mic_button.configure(text="Ativar microfone")
            self.status_label.configure(text="Microfone desligado")
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
        self.status_label.configure(text="Ouvindo microfone")

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
            self.profile_var.get() or "Avatar",
            self._current_image_sets(),
            {
                "sensitivity": float(self.sensitivity_var.get()),
                "smoothing": float(self.smoothing_var.get()),
                "animation_fps": int(float(self.animation_fps_var.get())),
                "avatar_scale": float(self.avatar_scale_var.get()),
                "avatar_offset_x": float(self.avatar_x_var.get()),
                "avatar_offset_y": float(self.avatar_y_var.get()),
                "idle_motion": self.idle_motion_var.get(),
                "avatar_shadow": self.avatar_shadow_var.get(),
            },
        )
        self.status_label.configure(text="Avatarpack exportado")

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
        settings = pack.get("settings", {})
        self.sensitivity_var.set(float(settings.get("sensitivity", self.sensitivity_var.get())))
        self.smoothing_var.set(float(settings.get("smoothing", self.smoothing_var.get())))
        self.animation_fps_var.set(int(settings.get("animation_fps", self.animation_fps_var.get())))
        self.avatar_scale_var.set(float(settings.get("avatar_scale", self.avatar_scale_var.get())))
        self.avatar_x_var.set(float(settings.get("avatar_offset_x", self.avatar_x_var.get())))
        self.avatar_y_var.set(float(settings.get("avatar_offset_y", self.avatar_y_var.get())))
        self.idle_motion_var.set(bool(settings.get("idle_motion", self.idle_motion_var.get())))
        self.avatar_shadow_var.set(bool(settings.get("avatar_shadow", self.avatar_shadow_var.get())))
        self.profile_var.set(pack.get("name", "Imported"))
        self._save_settings()
        self._save_image_sets()
        self._save_profile()
        self.status_label.configure(text="Avatarpack importado")

    def _current_image_sets(self) -> dict:
        return {
            "idle": self.idle_images,
            "talk": self.speaking_images,
            "talk_low": self.speaking_low_images,
            "talk_mid": self.speaking_mid_images,
            "talk_high": self.speaking_high_images,
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
        self._save_image_sets()

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
        self.avatar_canvas.set_image_sets(
            self.idle_images,
            self.speaking_images,
            self.speaking_low_images,
            self.speaking_mid_images,
            self.speaking_high_images,
        )
        self.avatar_canvas.set_transform(
            self.settings.avatar_scale,
            self.settings.avatar_offset_x,
            self.settings.avatar_offset_y,
        )
        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_image_sets(
                self.idle_images,
                self.speaking_images,
                self.speaking_low_images,
                self.speaking_mid_images,
                self.speaking_high_images,
            )
        self.avatar_label.configure(text="Assets carregados" if self.settings.streamer_safe else self._image_summary())
        self.settings.save()

    def _image_summary(self) -> str:
        level_count = len(self.speaking_low_images) + len(self.speaking_mid_images) + len(self.speaking_high_images)
        return f"Idle: {len(self.idle_images)} | Fala: {len(self.speaking_images)} | Niveis: {level_count}"

    def _save_profile(self) -> None:
        name = self.profile_var.get() or "Default"
        profiles = self.settings.profiles or {}
        profiles[name] = {
            "idle_images": self.idle_images,
            "speaking_images": self.speaking_images,
            "speaking_low_images": self.speaking_low_images,
            "speaking_mid_images": self.speaking_mid_images,
            "speaking_high_images": self.speaking_high_images,
            "sensitivity": float(self.sensitivity_var.get()),
            "smoothing": float(self.smoothing_var.get()),
            "animation_fps": int(float(self.animation_fps_var.get())),
            "avatar_scale": float(self.avatar_scale_var.get()),
            "avatar_offset_x": float(self.avatar_x_var.get()),
            "avatar_offset_y": float(self.avatar_y_var.get()),
            "obs_background": self.obs_background_var.get(),
            "obs_resolution": self.obs_resolution_var.get(),
            "expressions": self.settings.expressions or {},
        }
        self.settings.profiles = profiles
        self.settings.active_profile = name
        self.profile_select.configure(values=self._profile_names())
        self.settings.save()
        self.status_label.configure(text=f"Perfil salvo: {name}")

    def _save_expression(self) -> None:
        name = self.expression_var.get() or "Default"
        expressions = self.settings.expressions or {}
        expressions[name] = self._current_image_sets()
        self.settings.expressions = expressions
        self.settings.active_expression = name
        self.expression_select.configure(values=self._expression_names())
        self.settings.save()
        self.status_label.configure(text=f"Expressao salva: {name}")

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
        self.settings.active_expression = name
        self.expression_var.set(name)
        self._save_image_sets()
        self.status_label.configure(text=f"Expressao: {name}")

    def _new_profile(self) -> None:
        name = simpledialog.askstring("Novo perfil", "Nome do perfil:")
        if not name:
            return
        self.profile_var.set(name)
        self._save_profile()

    def _load_profile(self, name: str) -> None:
        profile = (self.settings.profiles or {}).get(name)
        if not profile:
            return
        self.idle_images = list(profile.get("idle_images") or [])
        self.speaking_images = list(profile.get("speaking_images") or [])
        self.speaking_low_images = list(profile.get("speaking_low_images") or [])
        self.speaking_mid_images = list(profile.get("speaking_mid_images") or [])
        self.speaking_high_images = list(profile.get("speaking_high_images") or [])
        self.sensitivity_var.set(float(profile.get("sensitivity", self.settings.sensitivity)))
        self.smoothing_var.set(float(profile.get("smoothing", self.settings.smoothing)))
        self.animation_fps_var.set(int(profile.get("animation_fps", self.settings.animation_fps)))
        self.avatar_scale_var.set(float(profile.get("avatar_scale", self.settings.avatar_scale)))
        self.avatar_x_var.set(float(profile.get("avatar_offset_x", self.settings.avatar_offset_x)))
        self.avatar_y_var.set(float(profile.get("avatar_offset_y", self.settings.avatar_offset_y)))
        self.obs_background_var.set(profile.get("obs_background", self.settings.obs_background))
        self.obs_resolution_var.set(profile.get("obs_resolution", self.settings.obs_resolution))
        self.settings.active_profile = name
        self._save_settings()
        self._save_obs_settings()
        self._save_image_sets()
        self.status_label.configure(text=f"Perfil carregado: {name}")

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
        self.status_label.configure(text="Calibrando ruido por 3 segundos...")

    def _toggle_theme(self) -> None:
        self.dark_var.set(not self.dark_var.get())
        self._toggle_theme_from_check()

    def _toggle_theme_from_check(self) -> None:
        self.settings.dark_mode = self.dark_var.get()
        self.colors = DARK if self.settings.dark_mode else LIGHT
        self._apply_theme()
        self.settings.save()

    def _save_settings(self) -> None:
        self.settings.sensitivity = float(self.sensitivity_var.get())
        self.settings.smoothing = float(self.smoothing_var.get())
        self.settings.background = self.background_var.get()
        self.settings.animation_fps = int(float(self.animation_fps_var.get()))
        self.settings.avatar_scale = float(self.avatar_scale_var.get())
        self.settings.avatar_offset_x = float(self.avatar_x_var.get())
        self.settings.avatar_offset_y = float(self.avatar_y_var.get())
        self.settings.performance_mode = self.performance_var.get()
        self.settings.idle_motion = self.idle_motion_var.get()
        self.settings.avatar_shadow = self.avatar_shadow_var.get()
        self.settings.streamer_safe = self.streamer_safe_var.get()
        self.detector.sensitivity = self.settings.sensitivity
        self.detector.smoothing = self.settings.smoothing
        self.avatar_canvas.set_background(self.settings.background)
        self.avatar_canvas.set_animation_fps(self.settings.animation_fps)
        self.avatar_canvas.set_transform(
            self.settings.avatar_scale,
            self.settings.avatar_offset_x,
            self.settings.avatar_offset_y,
        )
        self.avatar_canvas.set_visual_options(self.settings.idle_motion, self.settings.avatar_shadow)
        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_animation_fps(self.settings.animation_fps)
            self.obs_window.set_transform(
                self.settings.avatar_scale,
                self.settings.avatar_offset_x,
                self.settings.avatar_offset_y,
            )
            self.obs_window.set_visual_options(self.settings.idle_motion, self.settings.avatar_shadow)
        self.settings.save()

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
            )
            self.obs_window.set_visual_options(self.settings.idle_motion, self.settings.avatar_shadow)
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

        self.settings.save()

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
        self.status_label.configure(text="OBS rodando atras das janelas")

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

    def _reset_privacy(self) -> None:
        if not messagebox.askyesno("Apagar dados locais", "Apagar configuracoes, perfis, caminhos de imagens e logs locais?"):
            return
        self.microphone.stop()
        self.hotkeys.close()
        self.tray.stop()
        try:
            if APP_DIR.exists():
                shutil.rmtree(APP_DIR)
        except Exception as exc:
            messagebox.showerror("Privacidade", f"Nao foi possivel apagar tudo:\n{exc}")
            return
        messagebox.showinfo("Privacidade", "Dados locais apagados. O app sera fechado.")
        super().destroy()

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
                self.status_label.configure(text=f"Sensibilidade calibrada: {int(calibrated * 100)}%")

        speaking = state.speaking or self.test_ticks > 0
        if not self.settings.performance_mode and self.state() != "withdrawn":
            self.avatar_canvas.update_state(speaking, state.level)
        if self.obs_window and self.obs_window.winfo_exists() and self.obs_window.state() != "withdrawn":
            self.obs_window.update_state(speaking, state.level)

        percent = int(max(0.0, min(1.0, state.level)) * 100)
        self.volume_bar["value"] = percent
        self.volume_label.configure(text=f"{percent}%")

        if self.microphone.is_running:
            if self.calibration_ticks <= 0:
                self.status_label.configure(text="Voz detectada" if speaking else f"Ouvindo microfone | FPS {self.render_fps}")
        elif self.test_ticks > 0:
            self.status_label.configure(text="Teste de fala ativo")
        else:
            self.status_label.configure(text="Microfone desligado")

        self.render_frames += 1
        now = int(self.tk.call("clock", "milliseconds"))
        if self.last_fps_time == 0:
            self.last_fps_time = now
        elif now - self.last_fps_time >= 1000:
            self.render_fps = self.render_frames
            self.render_frames = 0
            self.last_fps_time = now

        self.after(16, self._tick)

    def destroy(self) -> None:
        self.log.info("AvatarCam encerrado")
        self.tray.stop()
        self.hotkeys.close()
        self.microphone.stop()
        super().destroy()
