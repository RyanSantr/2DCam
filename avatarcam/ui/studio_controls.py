"""Ferramentas do Studio: 3D, edicao direta, tarefas e diagnostico."""
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
import tkinter as tk
import webbrowser
import time
import json
import platform
import queue
from concurrent.futures import ThreadPoolExecutor
from avatarcam.core.model3d import import_model
from avatarcam.core.viewer_server import ViewerServer
from avatarcam.core.persistence import atomic_write_text
from avatarcam.core.settings import APP_DIR
from avatarcam.audio.microphone import MicrophoneInput


class StudioControls:
    def _init_studio(self):
        self.viewer_server = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='AvatarImport')
        self.jobs = []
        self.gui_events = queue.SimpleQueue()
        self._closing = False
        self._camera_revision = 0
        self._animation_epoch = time.time()
        self.advanced_var = tk.BooleanVar(value=self.settings.advanced_mode)
        self.speech_mode_var = tk.StringVar(value=self.settings.speech_mode)
        self.expression3d_var = tk.StringVar(value=self.settings.expression3d)
        self.fps3d_var = tk.IntVar(value=self.settings.fps3d)
        self.rotate3d_var = tk.BooleanVar(value=self.settings.auto_rotate3d)
        self.microphone.speech_mode = self.settings.speech_mode

    def _build_studio(self, header):
        self.avatar_canvas.transform_callback = self._edit_transform
        try: self.iconbitmap(str(Path(__file__).resolve().parent.parent / 'assets' / 'studio.ico'))
        except tk.TclError: pass
        self.title('2DCam Studio Â· 2D + 3D')
        toolbar = ttk.Frame(self.stage_frame)
        toolbar.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        ttk.Button(toolbar, text='Centralizar avatar', command=self._center_avatar).pack(side='left')
        ttk.Label(toolbar, text='Arraste: avatar Â· Botao direito: pet Â· Roda: tamanho', style='Body.TLabel').pack(side='left', padx=12)
        ttk.Checkbutton(header, text='Controles avancados', variable=self.advanced_var, command=self._set_simple_mode).grid(row=2, column=0, columnspan=2, sticky='w', pady=(8, 0))
        self.model_tab = ttk.Frame(self.control_tabs, padding=12, style='Panel.TFrame')
        self.model_tab.columnconfigure(0, weight=1)
        self.control_tabs.insert(2, self.model_tab, text='Avatar 3D')
        ttk.Label(self.model_tab, text='Um novo jeito de aparecer', style='PanelTitle.TLabel').grid(row=0, sticky='w', pady=(0, 8))
        ttk.Label(self.model_tab, text='Importe VRM ou GLB com texturas incorporadas. O visualizador e a captura funcionam no seu PC.', wraplength=320, style='Body.TLabel').grid(row=1, sticky='w', pady=(0, 12))
        ttk.Button(self.model_tab, text='Importar avatar 3D', command=self._choose_model3d, style='Primary.TButton').grid(row=2, sticky='ew', pady=4)
        ttk.Button(self.model_tab, text='Experimentar avatar de exemplo', command=self._demo_model3d).grid(row=3, sticky='ew', pady=4)
        self.model_label = ttk.Label(self.model_tab, text=self._model_description(), wraplength=320, style='Body.TLabel')
        self.model_label.grid(row=4, sticky='w', pady=(8, 12))
        ttk.Button(self.model_tab, text='Abrir visualizador 3D', command=self._open_viewer3d).grid(row=5, sticky='ew', pady=4)
        ttk.Button(self.model_tab, text='Copiar URL para o OBS', command=self._copy_obs3d).grid(row=6, sticky='ew', pady=4)
        ttk.Button(self.model_tab, text='Abrir captura limpa 3D', command=lambda: self._open_viewer3d(True)).grid(row=7, sticky='ew', pady=4)
        ttk.Label(self.model_tab, text='No OBS: Fonte de navegador â†’ cole a URL. Use 1280 Ã— 720 ou a resolucao da sua cena.', wraplength=320, style='Body.TLabel').grid(row=8, sticky='w', pady=12)
        ttk.Label(self.model_tab, text='Expressao facial (VRM)', style='Body.TLabel').grid(row=9, sticky='w', pady=4)
        expressions = ttk.Combobox(self.model_tab, textvariable=self.expression3d_var, values=('neutral', 'happy', 'angry', 'sad', 'relaxed', 'surprised'), state='readonly')
        expressions.grid(row=10, sticky='ew')
        expressions.bind('<<ComboboxSelected>>', lambda e: self._save_studio())
        ttk.Label(self.model_tab, text='FPS 3D', style='Body.TLabel').grid(row=11, sticky='w', pady=(12, 4))
        ttk.Scale(self.model_tab, from_=15, to=60, variable=self.fps3d_var, command=lambda v: self._save_studio(True)).grid(row=12, sticky='ew')
        ttk.Checkbutton(self.model_tab, text='Rotacao automatica', variable=self.rotate3d_var, command=self._save_studio).grid(row=13, sticky='w', pady=8)
        ttk.Button(self.model_tab, text='Restaurar enquadramento 3D', command=self._reset_camera3d).grid(row=14, sticky='ew', pady=4)
        ttk.Button(self.model_tab, text='Remover modelo da cena', command=self._clear_model3d).grid(row=15, sticky='ew', pady=4)
        audio = ttk.LabelFrame(self.live_tab, text='Leitura do microfone', padding=10)
        audio.grid(row=3, column=0, sticky='ew', pady=(12, 0))
        audio.columnconfigure(0, weight=1)
        self.audio_meter = ttk.Progressbar(audio, maximum=1)
        self.audio_meter.grid(row=0, sticky='ew')
        self.audio_hint = ttk.Label(audio, text='Volume Â· filtro de voz', style='Body.TLabel')
        self.audio_hint.grid(row=1, sticky='w', pady=4)
        filter_box = ttk.Combobox(audio, textvariable=self.speech_mode_var, values=('volume', 'vad') if self.microphone.vad_available else ('volume',), state='readonly')
        filter_box.grid(row=2, sticky='ew')
        filter_box.bind('<<ComboboxSelected>>', lambda e: self._save_studio())
        ttk.Label(audio, text='volume: resposta por intensidade Â· vad: filtro de voz', wraplength=310, style='Body.TLabel').grid(row=3, sticky='w', pady=4)
        ttk.Button(audio, text='Atualizar lista de microfones', command=self._refresh_microphones).grid(row=4, sticky='ew', pady=4)
        ttk.Button(self.system_tab, text='Exportar diagnostico', command=self._export_diagnostics).grid(row=2, column=0, sticky='ew', pady=10)
        ttk.Button(self.system_tab, text='Sair do app', command=self.destroy).grid(row=3, column=0, sticky='ew', pady=4)
        ttk.Button(self.live_tab, text='Sair do app', command=self.destroy).grid(row=4, column=0, sticky='ew', pady=(12, 0))
        ttk.Button(self.assets_tab, text='Experimentar avatar 2D de exemplo', command=self._demo_model2d).grid(row=3, column=0, sticky='ew', pady=10)
        self._set_simple_mode(save=False)

    def _demo_model2d(self):
        from avatarcam.core.avatar_pack import import_avatar_folder
        path = Path(__file__).resolve().parent.parent / 'assets' / 'StudioBot2D'
        self._run_job('Preparando avatar 2D...', lambda: import_avatar_folder(str(path), 'StudioBot2D'), self._use_imported_sets)

    def _set_simple_mode(self, save=True):
        for tab, label in ((self.tuning_tab, 'Ajustes'), (self.shortcuts_tab, 'Atalhos'), (self.system_tab, 'Sistema')):
            if self.advanced_var.get():
                self.control_tabs.add(tab, text=label)
            else:
                self.control_tabs.hide(tab)
        if save:
            self.settings.advanced_mode = self.advanced_var.get()
            self._save_settings_file()

    def _save_studio(self, defer=False):
        self.settings.speech_mode = self.speech_mode_var.get()
        self.microphone.speech_mode = self.settings.speech_mode
        self.settings.expression3d = self.expression3d_var.get()
        self.settings.fps3d = int(float(self.fps3d_var.get()))
        self.settings.auto_rotate3d = self.rotate3d_var.get()
        self._save_settings_file(defer=defer)

    def _edit_transform(self, target, x, y, scale):
        xv, yv, sv = (self.pet_x_var, self.pet_y_var, self.pet_size_var) if target == 'pet' else (self.avatar_x_var, self.avatar_y_var, self.avatar_scale_var)
        if x is not None: xv.set(x)
        if y is not None: yv.set(y)
        if scale is not None: sv.set(scale)
        self._save_settings(defer=True)

    def _center_avatar(self):
        self.avatar_rotation_var.set(0)
        self._edit_transform('avatar', 0, 0, 1)

    def _model_description(self):
        return Path(self.settings.avatar3d_path).name if self.settings.avatar3d_path else 'Nenhum modelo importado. Experimente o exemplo.'

    def _run_job(self, label, worker, success):
        if self.jobs:
            self._set_status('Aguarde a importacao atual.', 3000)
            return
        self._set_status(label, 60_000)
        self.jobs.append((self.executor.submit(worker), success))

    def _poll_jobs(self):
        for future, success in list(self.jobs):
            if future.done():
                self.jobs.remove((future, success))
                try:
                    success(future.result())
                except Exception as exc:
                    self.log.exception('Falha na importacao')
                    self._set_status('Importacao nao concluida; biblioteca anterior preservada.', 4000)
                    messagebox.showerror('Importacao', str(exc))
        while not self.gui_events.empty():
            self.gui_events.get_nowait()()

    def enqueue_ui(self, callback):
        if not self._closing:
            self.gui_events.put(callback)

    def _choose_model3d(self):
        path = filedialog.askopenfilename(title='Importar avatar 3D', filetypes=(('Avatar VRM / GLB', '*.vrm *.glb'),))
        if path:
            self._run_job('Importando avatar 3D...', lambda: import_model(path), self._use_model3d)

    def _demo_model3d(self):
        path = Path(__file__).resolve().parent.parent / 'assets' / 'AvatarHumanoide.vrm'
        self._run_job('Preparando avatar de exemplo...', lambda: import_model(str(path)), self._use_model3d)

    def _use_model3d(self, path):
        self.settings.avatar3d_path = path
        self.settings.camera3d = None
        self._camera_revision += 1
        self.model_label.configure(text=self._model_description())
        self._save_settings_file()
        self._open_viewer3d()
        self._set_status('Avatar 3D pronto. A boca depende das expressoes do modelo.', 5000)

    def _ensure_viewer3d(self):
        if self.viewer_server is None:
            server = ViewerServer(self.settings.viewer_token or None)
            try:
                server.start(self.settings.viewer_port)
            except OSError as exc:
                raise RuntimeError(f'Porta {self.settings.viewer_port} em uso. Feche a outra instancia do Studio e tente novamente.') from exc
            self.viewer_server = server
            self.settings.viewer_token = server.token
            self._save_settings_file()
        self._publish3d(0, False)
        return self.viewer_server.url

    def _open_viewer3d(self, capture=False):
        try:
            url = self._ensure_viewer3d() + ('?capture=1' if capture else '')
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showerror('Visualizador 3D', str(exc))

    def _copy_obs3d(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self._ensure_viewer3d() + '?capture=1')
            self._set_status('URL copiada. Cole em uma Fonte de navegador no OBS.', 4000)
        except Exception as exc:
            messagebox.showerror('OBS 3D', str(exc))

    def _reset_camera3d(self):
        self.settings.camera3d = None
        self._camera_revision += 1
        self._save_settings_file()

    def _clear_model3d(self):
        self.settings.avatar3d_path = ''
        self.settings.camera3d = None
        self.model_label.configure(text=self._model_description())
        self._save_settings_file()

    def _publish3d(self, level, speaking):
        if not self.viewer_server:
            return
        self.viewer_server.publish({
            'level': level, 'speaking': speaking, 'microphone': self.microphone.is_running,
            'expression': self.settings.expression3d, 'fps': self.settings.fps3d,
            'rotate': self.settings.auto_rotate3d, 'camera': self.settings.camera3d,
            'cameraRevision': self._camera_revision, 'animationEpoch': self._animation_epoch,
        }, self.settings.avatar3d_path)
        while not self.viewer_server.commands.empty():
            command = self.viewer_server.commands.get_nowait()
            action = command['action']
            if action == 'camera':
                self.settings.camera3d = command['value']
                self._schedule_settings_save()
            elif action == 'expression':
                self.expression3d_var.set(command['value'])
                self._save_studio()
            elif action == 'test': self._trigger_test()
            elif action == 'microphone': self._toggle_microphone()
            elif action == 'reset_camera': self._reset_camera3d()

    def _refresh_microphones(self):
        self.input_devices = MicrophoneInput.list_input_devices()
        self.microphone_names = [name for name, _ in self.input_devices]
        self.microphone_select.configure(values=self.microphone_names)
        current = next((name for name, index in self.input_devices if index == self.settings.microphone_device), None)
        if current is None:
            self.microphone_var.set(self.microphone_names[0])
            self._change_microphone()
        self._set_status('Lista de microfones atualizada.', 2500)

    def _export_diagnostics(self):
        path = filedialog.asksaveasfilename(title='Salvar diagnostico', defaultextension='.json', initialfile='2DCam-diagnostico.json', filetypes=(('JSON', '*.json'),))
        if not path: return
        data = {'app': '2DCam Studio 2.0', 'python': platform.python_version(), 'system': platform.platform(), 'audio_running': self.microphone.is_running, 'vad_available': self.microphone.vad_available, 'audio_warnings': self.microphone.audio_warnings, 'performance': self.settings.performance_preset, 'panel_fps': self.render_fps, 'model3d_loaded': bool(self.settings.avatar3d_path), 'asset_sets_cached': len(self.asset_store.cache), 'viewer_running': bool(self.viewer_server)}
        atomic_write_text(Path(path), json.dumps(data, indent=2))
        self._set_status('Diagnostico exportado sem caminhos pessoais.', 3000)

    def report_callback_exception(self, exc_type, exc_value, traceback):
        self.log.error('Erro no painel', exc_info=(exc_type, exc_value, traceback))
        messagebox.showerror('2DCam Studio', f'Nao foi possivel concluir a acao:\n{exc_value}')
