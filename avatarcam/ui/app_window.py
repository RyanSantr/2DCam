from __future__ import annotations

import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from avatarcam.audio.microphone import MicrophoneInput
from avatarcam.core.settings import Settings
from avatarcam.core.speech_detector import SpeechDetector
from avatarcam.ui.avatar_canvas import AvatarCanvas
from avatarcam.ui.obs_window import ObsOutputWindow
from avatarcam.ui.theme import DARK, LIGHT, OBS_BACKGROUNDS


class AvatarCamApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AvatarCam 2D")
        self.geometry("1180x820")
        self.minsize(980, 760)

        self.settings = Settings.load()
        self.colors = DARK if self.settings.dark_mode else LIGHT
        self.microphone = MicrophoneInput()
        self.detector = SpeechDetector(self.settings.sensitivity, self.settings.smoothing)
        self.test_ticks = 0
        self.obs_window: ObsOutputWindow | None = None
        self.idle_images = list(self.settings.idle_images or [])
        self.speaking_images = list(self.settings.speaking_images or [])

        self._configure_style()
        self._build_layout()
        self._apply_theme()
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
        self.avatar_canvas.set_image_sets(self.idle_images, self.speaking_images)
        self.avatar_canvas.set_animation_fps(self.settings.animation_fps)
        self.avatar_canvas.set_background(self.settings.background)

        meter_box = ttk.Frame(self.stage_frame)
        meter_box.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        meter_box.columnconfigure(0, weight=1)
        ttk.Label(meter_box, text="Volume do microfone", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        self.volume_label = ttk.Label(meter_box, text="0%", style="Strong.TLabel")
        self.volume_label.grid(row=0, column=1, sticky="e")
        self.volume_bar = ttk.Progressbar(meter_box, maximum=100, mode="determinate")
        self.volume_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.control_frame = ttk.Frame(self.container, padding=18)
        self.control_frame.grid(row=0, column=1, sticky="nsew")
        self.control_frame.columnconfigure(0, weight=1)

        ttk.Label(self.control_frame, text="Controles", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.control_frame, text="Operacao ao vivo", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 16))

        self.mic_button = ttk.Button(self.control_frame, text="Ativar microfone", command=self._toggle_microphone, style="Primary.TButton")
        self.mic_button.grid(row=2, column=0, sticky="ew", pady=5)

        self.idle_button = ttk.Button(self.control_frame, text="Escolher imagens idle", command=self._choose_idle_images)
        self.idle_button.grid(row=3, column=0, sticky="ew", pady=5)
        self.speaking_button = ttk.Button(self.control_frame, text="Escolher imagens falando", command=self._choose_speaking_images)
        self.speaking_button.grid(row=4, column=0, sticky="ew", pady=5)
        self.clear_images_button = ttk.Button(self.control_frame, text="Limpar imagens", command=self._clear_images)
        self.clear_images_button.grid(row=5, column=0, sticky="ew", pady=5)

        self.test_button = ttk.Button(self.control_frame, text="Teste de fala", command=self._trigger_test)
        self.test_button.grid(row=6, column=0, sticky="ew", pady=5)

        self.settings_frame = ttk.LabelFrame(self.control_frame, text="Configuracoes", padding=14)
        self.settings_frame.grid(row=7, column=0, sticky="ew", pady=(18, 10))
        self.settings_frame.columnconfigure(0, weight=1)

        self.sensitivity_var = tk.DoubleVar(value=self.settings.sensitivity)
        self.smoothing_var = tk.DoubleVar(value=self.settings.smoothing)
        self.dark_var = tk.BooleanVar(value=self.settings.dark_mode)
        self.background_var = tk.StringVar(value=self.settings.background)
        self.obs_background_var = tk.StringVar(value=self.settings.obs_background)
        self.obs_top_var = tk.BooleanVar(value=self.settings.obs_always_on_top)
        self.auto_hide_var = tk.BooleanVar(value=self.settings.auto_hide_controls)
        self.animation_fps_var = tk.IntVar(value=self.settings.animation_fps)

        self._add_slider("Sensibilidade", self.sensitivity_var, 0.04, 0.7, 0)
        self._add_slider("Suavizacao", self.smoothing_var, 0.1, 0.95, 1)
        self._add_slider("FPS da animacao", self.animation_fps_var, 1, 30, 2)

        ttk.Label(self.settings_frame, text="Fundo preview", style="Body.TLabel").grid(row=6, column=0, sticky="w", pady=(12, 4))
        self.background_select = ttk.Combobox(
            self.settings_frame,
            textvariable=self.background_var,
            values=("studio", "aurora", "grid", "clean"),
            state="readonly",
        )
        self.background_select.grid(row=7, column=0, sticky="ew")
        self.background_select.bind("<<ComboboxSelected>>", lambda _event: self._save_settings())

        self.dark_check = ttk.Checkbutton(self.settings_frame, text="Modo escuro", variable=self.dark_var, command=self._toggle_theme_from_check)
        self.dark_check.grid(row=8, column=0, sticky="w", pady=(14, 0))

        self.obs_frame = ttk.LabelFrame(self.control_frame, text="OBS", padding=14)
        self.obs_frame.grid(row=8, column=0, sticky="ew", pady=(10, 10))
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

        self.auto_hide_check = ttk.Checkbutton(
            self.obs_frame,
            text="Esconder controles ao abrir OBS",
            variable=self.auto_hide_var,
            command=self._save_obs_settings,
        )
        self.auto_hide_check.grid(row=4, column=0, sticky="w", pady=(8, 0))

        self.hide_button = ttk.Button(self.obs_frame, text="Modo live: ocultar controles", command=self._hide_controls)
        self.hide_button.grid(row=5, column=0, sticky="ew", pady=(10, 0))

        self.status_label = ttk.Label(self.control_frame, text="Microfone desligado", style="Status.TLabel")
        self.status_label.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        self.avatar_label = ttk.Label(self.control_frame, text=self._image_summary(), style="Body.TLabel")
        self.avatar_label.grid(row=10, column=0, sticky="w", pady=(8, 0))

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
            messagebox.showerror("Microfone indisponivel", str(exc))
            return
        except Exception as exc:
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

    def _clear_images(self) -> None:
        self.idle_images = []
        self.speaking_images = []
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
        self.avatar_canvas.set_image_sets(self.idle_images, self.speaking_images)
        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_image_sets(self.idle_images, self.speaking_images)
        self.avatar_label.configure(text=self._image_summary())
        self.settings.save()

    def _image_summary(self) -> str:
        return f"Idle: {len(self.idle_images)} imagem(ns) | Fala: {len(self.speaking_images)} imagem(ns)"

    def _trigger_test(self) -> None:
        self.test_ticks = 90

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
        self.detector.sensitivity = self.settings.sensitivity
        self.detector.smoothing = self.settings.smoothing
        self.avatar_canvas.set_background(self.settings.background)
        self.avatar_canvas.set_animation_fps(self.settings.animation_fps)
        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_animation_fps(self.settings.animation_fps)
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
                self.settings.obs_background,
                self.settings.obs_always_on_top,
                self.settings.animation_fps,
            )
        else:
            self.obs_window.deiconify()
            self.obs_window.lift()

        self.obs_button.configure(text="Ocultar janela OBS")
        if self.settings.auto_hide_controls:
            self._hide_controls()

    def _save_obs_settings(self) -> None:
        self.settings.obs_background = self.obs_background_var.get()
        self.settings.obs_always_on_top = self.obs_top_var.get()
        self.settings.auto_hide_controls = self.auto_hide_var.get()

        if self.obs_window and self.obs_window.winfo_exists():
            self.obs_window.set_background(self.settings.obs_background)
            self.obs_window.set_always_on_top(self.settings.obs_always_on_top)

        self.settings.save()

    def _hide_controls(self) -> None:
        if not self.obs_window or not self.obs_window.winfo_exists() or self.obs_window.state() == "withdrawn":
            self._toggle_obs_window()
        self.withdraw()

    def show_controls(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tick(self) -> None:
        if self.test_ticks > 0:
            raw_level = 0.32 + math.sin(self.test_ticks / 3) * 0.12
            self.test_ticks -= 1
        else:
            raw_level = self.microphone.read_level()

        state = self.detector.update(raw_level)
        speaking = state.speaking or self.test_ticks > 0
        self.avatar_canvas.update_state(speaking, state.level)
        if self.obs_window and self.obs_window.winfo_exists() and self.obs_window.state() != "withdrawn":
            self.obs_window.update_state(speaking, state.level)

        percent = int(max(0.0, min(1.0, state.level)) * 100)
        self.volume_bar["value"] = percent
        self.volume_label.configure(text=f"{percent}%")

        if self.microphone.is_running:
            self.status_label.configure(text="Voz detectada" if speaking else "Ouvindo microfone")
        elif self.test_ticks > 0:
            self.status_label.configure(text="Teste de fala ativo")
        else:
            self.status_label.configure(text="Microfone desligado")

        self.after(16, self._tick)

    def destroy(self) -> None:
        self.microphone.stop()
        super().destroy()
