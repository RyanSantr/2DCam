from pathlib import Path
import json
import time
from PySide6.QtCore import Qt, QTimer, QEvent, QSize
from PySide6.QtGui import QIcon, QImage, QPixmap, QShortcut, QKeySequence, QImageReader
from PySide6.QtWidgets import (QMenu, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QButtonGroup,
    QScrollArea, QGroupBox, QComboBox, QSlider, QCheckBox, QProgressBar,
    QFileDialog, QMessageBox, QInputDialog, QListWidget, QListWidgetItem, QSizePolicy,
    QDialog, QDialogButtonBox, QKeySequenceEdit)
from avatarcam.desktop.controller import StudioController, ASSETS
from avatarcam.desktop.canvas2d import Avatar2D
from avatarcam.desktop.webview import EmbeddedAvatar
from avatarcam.desktop.style import STYLE
from avatarcam.desktop.performance import PRESETS, ProcessUsage
from avatarcam.audio.microphone import MicrophoneInput
from avatarcam.core.persistence import atomic_write_text
from avatarcam.core.settings import APP_DIR
from avatarcam.desktop.output import OUTPUT_SIZES, output_size
from avatarcam.desktop.shortcuts import LiveShortcuts, SHORTCUTS, shortcut_rows, validate_bindings
from avatarcam.desktop.library import avatar_id
from avatarcam.desktop.creative import GESTURES
from avatarcam.desktop.transparent import TransparentOutput


def label(text, name=None, wrap=False):
    widget=QLabel(text)
    if name: widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback, primary=False):
    widget=QPushButton(text); widget.clicked.connect(lambda _=False: callback())
    if primary: widget.setObjectName('primary')
    return widget


def group(title, parent_layout):
    box=QGroupBox(title); layout=QVBoxLayout(box); layout.setSpacing(10)
    parent_layout.addWidget(box); return layout


def details(title, parent_layout):
    toggle = QPushButton('▸ ' + title); toggle.setCheckable(True)
    content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(0, 6, 0, 0)
    content.hide()
    def changed(opened):
        content.setVisible(opened); toggle.setText(('▾ ' if opened else '▸ ') + title)
    toggle.toggled.connect(changed)
    parent_layout.addWidget(toggle); parent_layout.addWidget(content)
    return layout


class CaptureWindow(QMainWindow):
    """A mesma superficie do estudio e transferida, sem copiar o avatar."""
    def __init__(self, controller, parent):
        super().__init__(parent); self.owner=parent; self.controller=controller
        self.setWindowTitle('2DCam - Avatar')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.stack=QStackedWidget(); self.setCentralWidget(self.stack)
        self.hosts=[]
        for _ in range(2):
            host=QWidget(); layout=QVBoxLayout(host); layout.setContentsMargins(0,0,0,0)
            self.stack.addWidget(host); self.hosts.append(host)
        self.resize(*output_size(controller.preferences.get('output_size')))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, controller.preferences.get('output_on_top',False))
        self.shortcuts=[]
        for chord,action,_ in shortcut_rows(controller.preferences['shortcut_bindings']):
            shortcut=QShortcut(QKeySequence(chord),self); shortcut.setAutoRepeat(False)
            shortcut.setEnabled(not controller.preferences['global_shortcuts'])
            shortcut.activated.connect(lambda value=action:parent.handle_live_shortcut(value))
            self.shortcuts.append(shortcut)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.menu)

    def menu(self, position):
        menu=QMenu(self)
        menu.addAction('Mostrar controles',self.owner.restore_controls)
        menu.addAction('Pausar / retomar',self.controller.toggle_pause)
        menu.addAction('Fechar saída',self.close)
        menu.exec(self.mapToGlobal(position))

    def closeEvent(self,event):
        self.owner.return_output(self); event.accept()


class StudioWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.controller=StudioController(); self.capture_window=None
        self.transparent_output = TransparentOutput(self); self.wizard = None; self.motion_dialog = None
        self.controller.remember_avatar()
        self.device_signature=-1
        self.avatar3d=None; self.current_destination=None; self.quitting=False
        self.last_camera_frame=None
        self.live_shortcuts=LiveShortcuts(self); self.live_shortcuts.triggered.connect(self.handle_live_shortcut,Qt.ConnectionType.QueuedConnection)
        self.setWindowTitle('2DCam Studio')
        self.setWindowIcon(QIcon(str(ASSETS/'studio.ico')))
        self.resize(1180,780); self.setMinimumSize(920,620);
        available=self.screen().availableGeometry(); self.resize(min(1180,available.width()-40),min(780,available.height()-60)); self.setStyleSheet(STYLE)
        self.setAcceptDrops(True)
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root)
        outer.setContentsMargins(14,10,14,10); outer.setSpacing(10)
        header=QHBoxLayout(); header.addWidget(label('2DCam','brand')); header.addSpacing(18)
        self.navigation=QButtonGroup(self)
        for index,text in enumerate(('Avatar','Biblioteca','Câmera','Configurações')):
            nav=button(text,lambda i=index:self.select_panel(i)); nav.setObjectName('nav')
            nav.setCheckable(True); self.navigation.addButton(nav,index); header.addWidget(nav)
        self.navigation.button(0).setChecked(True); header.addStretch()
        self.quick_mic=button('Microfone',self.controller.toggle_microphone); self.quick_mic.setCheckable(True); header.addWidget(self.quick_mic)
        self.quick_camera=button('Câmera',self.controller.toggle_tracking); self.quick_camera.setCheckable(True); header.addWidget(self.quick_camera)
        self.pause_button=button('Pausar',self.controller.toggle_pause); header.addWidget(self.pause_button)
        outer.addLayout(header)
        body=QHBoxLayout(); body.setSpacing(14); outer.addLayout(body,1)
        middle=QWidget(); center=QVBoxLayout(middle); center.setContentsMargins(0,0,0,0); center.setSpacing(10)
        imports=QHBoxLayout(); imports.addWidget(button('Importar avatar',self.choose_any,True))
        self.model_name=label('Avatar','section'); imports.addWidget(self.model_name,1)
        self.mode_2d=button('2D',lambda:self.controller.switch_mode('2D')); self.mode_3d=button('3D',self.activate_3d)
        for w in (self.mode_2d,self.mode_3d): w.setCheckable(True); imports.addWidget(w)
        center.addLayout(imports)
        self.preview=QStackedWidget(); self.preview.setMinimumHeight(250)
        self.studio_hosts=[]
        for _ in range(2):
            host=QWidget(); layout=QVBoxLayout(host); layout.setContentsMargins(0,0,0,0)
            self.preview.addWidget(host); self.studio_hosts.append(host)
        placeholder=QWidget(); info=QVBoxLayout(placeholder); info.addStretch()
        message=label('O avatar está na janela de captura.','title'); message.setAlignment(Qt.AlignmentFlag.AlignCenter); info.addWidget(message)
        detail=label('Uma única imagem é renderizada para economizar memória.','muted'); detail.setAlignment(Qt.AlignmentFlag.AlignCenter); info.addWidget(detail)
        info.addWidget(button('Voltar ao editor',self.close_output)); info.addStretch(); self.preview.addWidget(placeholder)
        self.avatar2d=Avatar2D(self.controller); self.studio_hosts[0].layout().addWidget(self.avatar2d)
        center.addWidget(self.preview,1)
        tools=QHBoxLayout(); tools.addWidget(button('Centralizar',self.reset_camera))
        tools.addWidget(button('Salvar posição',self.save_camera)); tools.addWidget(button('Testar fala',lambda:self.controller.command('test')))
        tools.addStretch(); self.output_button=button('Saída OBS',self.open_capture)
        self.output_button.setToolTip('Abrir a janela do avatar para capturar no OBS')
        tools.addWidget(self.output_button)
        center.addLayout(tools); center.addWidget(label('Arraste para enquadrar. Use a roda para aproximar.','muted'))
        body.addWidget(middle,1)
        inspector=QFrame(); inspector.setObjectName('inspector'); inspector.setFixedWidth(294)
        right=QVBoxLayout(inspector); right.setContentsMargins(8,0,8,0)
        self.panels=QStackedWidget(); right.addWidget(self.panels); body.addWidget(inspector)
        self.build_studio_panel(); self.build_library_panel(); self.build_tracking_panel(); self.build_settings_panel()
        self.sync_timer=QTimer(self); self.sync_timer.setSingleShot(True); self.sync_timer.setInterval(100); self.sync_timer.timeout.connect(self.sync)
        self.controller.changed.connect(self.schedule_sync); self.controller.notice.connect(self.show_notice)
        self.controller.imported.connect(self.open_wizard)
        self.build_menu(); self.statusBar().showMessage('Pronto')
        self.usage=ProcessUsage(); self.resource_label=label('','muted'); self.statusBar().addPermanentWidget(self.resource_label)
        self.stats_timer=QTimer(self); self.stats_timer.timeout.connect(self.update_resources); self.stats_timer.start(2000)
        QShortcut(QKeySequence('Ctrl+O'),self).activated.connect(self.choose_any)
        QShortcut(QKeySequence('Space'),self).activated.connect(lambda:self.controller.command('test'))
        QShortcut(QKeySequence('Ctrl+M'),self).activated.connect(self.controller.toggle_microphone)
        QShortcut(QKeySequence('Ctrl+T'),self).activated.connect(self.controller.toggle_tracking)
        QShortcut(QKeySequence('Ctrl+P'),self).activated.connect(self.controller.toggle_pause)
        QShortcut(QKeySequence('Ctrl+Shift+O'),self).activated.connect(self.open_capture)
        QShortcut(QKeySequence('Ctrl+Z'),self).activated.connect(lambda:self.undo_change())
        QShortcut(QKeySequence('Ctrl+Shift+Z'),self).activated.connect(lambda:self.undo_change(True))
        self.local_live_shortcuts=[]
        self.rebuild_shortcuts()
        self.sync()
        self.controller.inputs.request_scan()
        QTimer.singleShot(600, self.recover_session)

    def rebuild_shortcuts(self):
        for shortcut in self.local_live_shortcuts:
            shortcut.setEnabled(False); shortcut.deleteLater()
        self.local_live_shortcuts=[]
        for chord,action,_ in shortcut_rows(self.controller.preferences['shortcut_bindings']):
            shortcut=QShortcut(QKeySequence(chord),self)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(lambda value=action:self.handle_live_shortcut(value))
            self.local_live_shortcuts.append(shortcut)
        self.configure_live_shortcuts(self.controller.preferences['global_shortcuts'])
        if self.capture_window:
            for shortcut in self.capture_window.shortcuts:
                shortcut.setEnabled(False); shortcut.deleteLater()
            self.capture_window.shortcuts=[]
            for chord,action,_ in shortcut_rows(self.controller.preferences['shortcut_bindings']):
                shortcut=QShortcut(QKeySequence(chord),self.capture_window); shortcut.setAutoRepeat(False)
                shortcut.setEnabled(not self.live_shortcuts.enabled)
                shortcut.activated.connect(lambda value=action:self.handle_live_shortcut(value))
                self.capture_window.shortcuts.append(shortcut)

    def schedule_sync(self):
        self.route_avatar()
        if not self.sync_timer.isActive(): self.sync_timer.start()

    def update_resources(self):
        values=self.usage.sample(); self.controller.resource_usage=values
        self.controller.adapt_performance(time.monotonic())
        if values:
            fps=self.controller.renderer_report.get('fps',0) if self.controller.mode=='3D' else self.controller.performance['fps']
            self.resource_label.setText(f"{values['private_mb']:.0f} MB privados · {fps:.0f} FPS")
        self.update_render_visibility()
        self.toggle_camera_preview()
        self.capture_thumbnail()

    def update_render_visibility(self):
        owner=self.capture_window or self
        active=owner.isVisible() and not owner.isMinimized()
        self.controller.set_render_active(active)
        if self.avatar3d and not self.avatar3d.released:
            visible=bool(active and self.avatar3d.isVisible())
            if self.avatar3d.page().isVisible()!=visible: self.avatar3d.page().setVisible(visible)

    def route_avatar(self):
        c=self.controller; capture=self.capture_window
        destination='output' if capture else 'studio'
        if self.avatar3d is not None and (c.mode=='2D' or self.avatar3d.kind != c.mode):
            old=self.avatar3d; self.avatar3d=None; old.release(); c.renderer_report={}
        if c.mode!='2D' and self.avatar3d is None:
            self.avatar2d.clear_cache(); c.store.clear()
            self.avatar3d=EmbeddedAvatar(c)
        c.output_active=bool(capture)
        hosts=capture.hosts if capture else self.studio_hosts
        widget=self.avatar3d if c.mode!='2D' else self.avatar2d
        host=hosts[1 if c.mode!='2D' else 0]
        if widget.parentWidget() is not host:
            widget.setParent(host); host.layout().addWidget(widget); widget.show()
        self.avatar2d.capture=bool(capture)
        if capture: capture.stack.setCurrentIndex(1 if c.mode!='2D' else 0)
        self.preview.setCurrentIndex(2 if capture else 1 if c.mode!='2D' else 0)
        self.output_button.setText('Mostrar saída' if capture else 'Saída OBS')
        self.update_render_visibility()

    def reload_renderer(self):
        if self.avatar3d:
            self.avatar3d.release(); self.avatar3d=None; self.controller.renderer_report={}
        self.route_avatar(); self.show_notice('Prévia recarregada.')

    def close_output(self):
        if self.capture_window: self.capture_window.close()

    def return_output(self,window):
        if self.capture_window is not window: return
        self.capture_window=None; self.controller.output_active=False
        # O canvas 2D pode estar inativo na saída enquanto o 3D está visível.
        # Devolve também esse filho antes de a janela de captura ser destruída.
        host=self.studio_hosts[0]
        if self.avatar2d.parentWidget() is not host:
            self.avatar2d.setParent(host); host.layout().addWidget(self.avatar2d)
        self.route_avatar()
        if not self.quitting: self.restore_controls()

    def restore_controls(self):
        self.showNormal(); self.raise_(); self.activateWindow()
        self.toggle_camera_preview()
        self.controller.set_render_active(True)
        self.update_render_visibility()

    def panel(self,title,subtitle):
        content=QWidget(); layout=QVBoxLayout(content); layout.setContentsMargins(8,0,8,0); layout.setSpacing(14)
        layout.addWidget(label(title,'title')); layout.addWidget(label(subtitle,'muted',True))
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content); self.panels.addWidget(scroll)
        return layout

    def build_studio_panel(self):
        layout=self.panel('Controles','Voz e movimento')
        audio=group('Microfone',layout)
        self.mic_devices=QComboBox(); self.mic_devices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.mic_devices.setMinimumContentsLength(12); self.mic_devices.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.refresh_mics(); self.mic_devices.currentIndexChanged.connect(self.change_mic)
        audio.addWidget(self.mic_devices); self.meter=QProgressBar(); self.meter.setRange(0,100); self.meter.setTextVisible(False); audio.addWidget(self.meter)
        self.voice_status=label('Microfone desligado','muted'); audio.addWidget(self.voice_status)
        self.mic_button=button('Ativar microfone',self.controller.toggle_microphone,True); audio.addWidget(self.mic_button)
        audio_details=details('Ajustar microfone',audio)
        audio_details.addWidget(button('Calibrar em silêncio',self.controller.calibrate_audio))
        face=group('Rosto',layout); self.camera_button=button('Ligar rastreamento',self.controller.toggle_tracking,True); face.addWidget(self.camera_button)
        self.face_status=label('Câmera desligada','muted',True); face.addWidget(self.face_status)
        face.addWidget(button('Calibrar posição neutra',self.controller.calibrate_face))
        without_camera=details('Usar sem webcam',layout)
        self.idle_checkbox=QCheckBox('Movimentos suaves do personagem')
        self.idle_checkbox.setChecked(self.controller.preferences['idle_motion'])
        self.idle_checkbox.toggled.connect(lambda value:self.set_preference('idle_motion',value)); without_camera.addWidget(self.idle_checkbox)
        self.idle_strength_slider=self.add_slider(without_camera,'Intensidade',round(self.controller.preferences['idle_strength']*100),10,150,lambda value:self.set_preference('idle_strength',value/100))
        without_camera.addWidget(button('Testar movimentos sem câmera',self.open_motion_test))
        without_camera.addWidget(label('A voz anima a boca. Os movimentos suaves entram quando não há rosto sendo rastreado.','muted',True))
        expressions=group('Expressões',layout); grid=QGridLayout(); self.expression_buttons={}
        for index,(key,name) in enumerate((('auto','Automático'),('neutral','Neutro'),('happy','Feliz'),('angry','Bravo'),('sad','Triste'),('surprised','Surpreso'))):
            btn=button(name,lambda k=key:self.controller.command('expression',k)); btn.setCheckable(True)
            grid.addWidget(btn,index//2,index%2); self.expression_buttons[key]=btn
        expressions.addLayout(grid); expressions.addWidget(label('Configure as poses 2D na Biblioteca.','muted',True))
        self.edit_expression_button = button('Editar expressões do modelo', self.edit_expressions); expressions.addWidget(self.edit_expression_button)
        actions = details('Ações do personagem', layout); action_grid = QGridLayout(); self.gesture_buttons = {}
        for index, (key, name) in enumerate(GESTURES.items()):
            item = button(name, lambda k=key: self.controller.play_gesture(k)); action_grid.addWidget(item,index//2,index%2); self.gesture_buttons[key]=item
        actions.addLayout(action_grid)
        layout.addWidget(button('Preparar personagem', self.open_wizard))
        layout.addStretch()

    def build_library_panel(self):
        layout=self.panel('Biblioteca','PNG / GIF · VRM / GLB')
        layout.addWidget(button('Usar a moça de exemplo',lambda:self.controller.use_model(str(ASSETS/'AvatarHumanoide.vrm')),True))
        layout.addWidget(button('Exemplo 2D',self.demo_2d))
        recent=group('Meus avatares',layout); self.recent_signature=None
        self.library_filter=QComboBox(); self.library_filter.addItems(['Todos','Favoritos','Somente 2D','Somente 3D'])
        self.library_filter.currentIndexChanged.connect(lambda _:self.refresh_recent(force=True)); recent.addWidget(self.library_filter)
        self.library_list=QListWidget(); self.library_list.setIconSize(QSize(64,64))
        self.library_list.setMinimumHeight(170); self.library_list.setMaximumHeight(270)
        self.library_list.itemClicked.connect(lambda item:self.controller.load_library(item.data(Qt.ItemDataRole.UserRole)))
        self.library_list.currentItemChanged.connect(self.sync_library_actions); recent.addWidget(self.library_list)
        actions=QHBoxLayout(); self.favorite_button=button('Favoritar',self.favorite_avatar); self.rename_button=button('Renomear',self.rename_avatar)
        actions.addWidget(self.favorite_button); actions.addWidget(self.rename_button); recent.addLayout(actions)
        self.refresh_recent()
        assets=details('Poses e expressões 2D',layout)
        assets.addWidget(button('Montar personagem visualmente', self.edit_poses, True))
        for role,text in (('idle','Imagem / animação parada'),('talk','Imagem / animação falando'),('blink','Imagem / animação piscando'),('pet','Adicionar pet')):
            assets.addWidget(button(text,lambda r=role:self.choose_2d(r)))
        assets.addWidget(button('Vincular expressão 2D',self.bind_expression))
        assets.addWidget(button('Importar pasta 2D',self.choose_folder))
        packs=details('Pacotes portáteis',layout); packs.addWidget(button('Importar .avatarpack',self.choose_pack))
        packs.addWidget(button('Exportar avatar atual',self.export_pack))
        packs.addWidget(label('O pacote leva poses, vínculos de expressões, movimentos e enquadramento.','muted',True))
        profiles=details('Perfis salvos',layout); self.profile_combo=QComboBox(); profiles.addWidget(self.profile_combo)
        self.refresh_profiles(); self.profile_combo.activated.connect(self.load_profile)
        profiles.addWidget(button('Salvar perfil atual',self.save_profile))
        profiles.addWidget(button('Excluir perfil',self.delete_profile)); layout.addStretch()

    def build_tracking_panel(self):
        layout=self.panel('Câmera','Selecione e calibre o rastreamento.')
        layout.addWidget(button('Testar movimentos sem webcam',self.open_motion_test))
        camera=group('Câmera',layout); self.camera_devices=QComboBox()
        self.camera_devices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.camera_devices.setMinimumContentsLength(12)
        self.camera_devices.addItem('Câmera selecionada',int(self.controller.preferences['camera_device']))
        self.camera_devices.setCurrentIndex(0)
        self.camera_devices.currentIndexChanged.connect(self.change_camera); camera.addWidget(self.camera_devices)
        camera.addWidget(button('Atualizar dispositivos',self.controller.inputs.request_scan))
        camera.addWidget(button('Ligar / desligar câmera',self.controller.toggle_tracking,True))
        self.tracking_detail=label('Câmera desligada','muted',True); camera.addWidget(self.tracking_detail)
        self.show_camera=QCheckBox('Mostrar prévia da câmera'); self.show_camera.toggled.connect(self.toggle_camera_preview); camera.addWidget(self.show_camera)
        self.camera_image=label('A prévia da câmera fica oculta.','muted',True); self.camera_image.setMinimumHeight(130)
        self.camera_image.setAlignment(Qt.AlignmentFlag.AlignCenter); camera.addWidget(self.camera_image)
        camera.addWidget(button('Calibrar posição neutra',self.controller.calibrate_face))
        movement=details('Ajustar movimentos',layout)
        self.face_smoothing_slider=self.add_slider(movement,'Suavização',int(self.controller.preference('face_smoothing',.55,.1,.9)*100),10,90,lambda x:self.set_preference('face_smoothing',x/100))
        self.face_strength_slider=self.add_slider(movement,'Intensidade',int(self.controller.preference('face_strength',1.,.2,2.)*100),20,200,lambda x:self.set_preference('face_strength',x/100))
        self.face_metrics=label('Boca 0%  ·  Olhos 0%\nCabeça em posição neutra','muted',True); movement.addWidget(self.face_metrics)
        layout.addWidget(label('Boa iluminação e rosto visível melhoram a leitura. PNG/GIF usam troca de imagens e movimento; VRM pode articular olhos e cabeça.','muted',True))
        layout.addStretch()

    def add_slider(self,layout,name,value,low,high,callback):
        layout.addWidget(label(name,'muted')); slider=QSlider(Qt.Orientation.Horizontal); slider.setRange(low,high); slider.setValue(value)
        slider.sliderPressed.connect(self.controller.record_change)
        slider.valueChanged.connect(callback); layout.addWidget(slider); return slider

    def build_settings_panel(self):
        layout=self.panel('Configurações','Desempenho e captura')
        performance=group('Desempenho',layout); self.performance_combo=QComboBox()
        self.performance_combo.addItem('Automático', 'auto')
        for key,values in PRESETS.items(): self.performance_combo.addItem(values['name'],key)
        self.performance_combo.setCurrentIndex(max(0,self.performance_combo.findData(self.controller.preferences.get('performance','balanced'))))
        self.performance_combo.currentIndexChanged.connect(lambda index:self.controller.set_performance(self.performance_combo.itemData(index)))
        performance.addWidget(self.performance_combo)
        self.adaptive_status = label('', 'muted', True); performance.addWidget(self.adaptive_status)
        performance.addWidget(label('Econômico: 24 FPS e câmera reduzida. Equilibrado: 30 FPS. Qualidade: 60 FPS.','muted',True))
        audio=details('Ajustes de áudio',layout); self.sensitivity_slider=self.add_slider(audio,'Sensibilidade',int(self.controller.settings.sensitivity*100),4,70,lambda x:self.set_setting('sensitivity',x/100))
        self.filter_combo=QComboBox(); self.filter_combo.addItems(['Volume','Filtro de voz'])
        self.filter_combo.setCurrentIndex(1 if self.controller.settings.speech_mode=='vad' else 0)
        self.filter_combo.currentIndexChanged.connect(self.change_filter); audio.addWidget(self.filter_combo)
        audio.addWidget(button('Atualizar dispositivos',self.controller.inputs.request_scan))
        display=details('Ajustes de imagem',layout)
        self.rotate=QCheckBox('Girar avatar automaticamente'); self.rotate.setChecked(self.controller.settings.auto_rotate3d)
        self.rotate.toggled.connect(lambda v:self.set_setting('auto_rotate3d',v)); display.addWidget(self.rotate)
        self.pet=QCheckBox('Mostrar pet 2D'); self.pet.setChecked(self.controller.settings.pet_enabled)
        self.pet.toggled.connect(lambda v:self.set_setting('pet_enabled',v)); display.addWidget(self.pet)
        self.scale_slider=self.add_slider(display,'Tamanho 2D',int(self.controller.settings.avatar_scale*100),25,250,lambda x:self.set_setting('avatar_scale',x/100))
        output=group('Saída do avatar',layout); output.addWidget(button('Abrir janela separada',self.open_capture,True))
        output.addWidget(button('Salvar imagem da prévia',self.save_image))
        self.output_size=QComboBox()
        for key,(width,height) in OUTPUT_SIZES.items(): self.output_size.addItem(f'{width} × {height}'+(' · vertical' if height>width else ''),key)
        self.output_size.setCurrentIndex(max(0,self.output_size.findData(self.controller.preferences.get('output_size','540p'))))
        self.output_size.currentIndexChanged.connect(self.change_output_size); output.addWidget(self.output_size)
        self.output_background=QComboBox()
        for text,key in (('Fundo verde','green'),('Fundo azul','blue'),('Fundo cinza','dark')): self.output_background.addItem(text,key)
        self.output_background.setCurrentIndex(max(0,self.output_background.findData(self.controller.preferences.get('output_background','green'))))
        self.output_background.currentIndexChanged.connect(lambda i:self.set_preference('output_background',self.output_background.itemData(i))); output.addWidget(self.output_background)
        self.hide_controls=QCheckBox('Ocultar controles ao abrir saída'); self.hide_controls.setChecked(bool(self.controller.preferences.get('hide_controls',False)))
        self.hide_controls.toggled.connect(lambda v:self.set_preference('hide_controls',v)); output.addWidget(self.hide_controls)
        self.output_on_top=QCheckBox('Saída sempre no topo'); self.output_on_top.setChecked(self.controller.preferences['output_on_top'])
        self.output_on_top.toggled.connect(self.change_output_top); output.addWidget(self.output_on_top)
        output.addWidget(button('Como capturar no OBS',self.obs_help))
        self.transparent_button = button('Ligar saída transparente', self.toggle_transparent); output.addWidget(self.transparent_button)
        output.addWidget(label('Spout2: preserva transparência. Requer o complemento Spout2 no OBS. Até 640 px / 24 FPS; começa desligado.', 'muted', True))
        shortcuts=details('Atalhos de live',layout)
        self.global_shortcuts=QCheckBox('Usar também fora do app'); self.global_shortcuts.setChecked(self.controller.preferences['global_shortcuts'])
        self.global_shortcuts.toggled.connect(self.configure_live_shortcuts); shortcuts.addWidget(self.global_shortcuts)
        self.shortcut_summary=label('','muted',True); shortcuts.addWidget(self.shortcut_summary)
        shortcuts.addWidget(button('Personalizar atalhos',self.edit_shortcuts))
        layout.addWidget(button('Verificar funcionamento', self.show_health))
        layout.addWidget(button('Restaurar ajustes deste avatar', self.reset_avatar_settings))
        layout.addWidget(button('Recarregar prévia 3D',self.reload_renderer)); layout.addWidget(button('Exportar diagnóstico',self.export_diagnostics)); layout.addStretch()

    def build_menu(self):
        menu=self.menuBar().addMenu('Arquivo')
        for text,callback in (('Importar avatar…',self.choose_any),('Importar pasta 2D…',self.choose_folder),('Importar pacote…',self.choose_pack),('Exportar avatar…',self.export_pack),('Sair',self.close)):
            menu.addAction(text,callback)
        editing=self.menuBar().addMenu('Editar')
        self.undo_action=editing.addAction('Desfazer',lambda:self.undo_change())
        self.redo_action=editing.addAction('Refazer',lambda:self.undo_change(True))
        editing.addAction('Montar personagem 2D…',self.edit_poses)
        editing.addAction('Expressões do modelo…',self.edit_expressions)
        menu=self.menuBar().addMenu('Ajuda'); menu.addAction('Como usar',lambda:QMessageBox.information(self,'Comece por aqui','1. Importe um PNG/GIF, VRM ou GLB.\n2. Ative o microfone ou o rastreamento.\n3. Calibre a posição neutra olhando para a câmera.\n4. Ajuste o enquadramento com o mouse.\n5. Abra Janela do avatar para uma saída sem controles.\n\nCtrl+O: importar · Ctrl+M: microfone · Ctrl+T: câmera · Espaço: teste de fala.'))
        from avatarcam.desktop.about import show_about
        menu.addAction('Sobre, ajuda e créditos',lambda:show_about(self))

    def select_panel(self,index):
        self.panels.setCurrentIndex(index); self.navigation.button(index).setChecked(True)
        self.toggle_camera_preview()

    def toggle_camera_preview(self,*args):
        enabled=self.panels.currentIndex()==2 and self.show_camera.isChecked() and self.isVisible() and not self.isMinimized()
        self.controller.tracker.preview_enabled=enabled
        if not enabled:
            with self.controller.tracker.lock: self.controller.tracker.frame=None
            self.controller.camera_frame=None
            self.last_camera_frame=None

    def change_output_size(self,index):
        key=self.output_size.itemData(index); self.set_preference('output_size',key)
        if self.capture_window: self.capture_window.resize(*output_size(key))

    def change_output_top(self,enabled):
        self.set_preference('output_on_top',enabled)
        if self.capture_window:
            geometry=self.capture_window.geometry()
            self.capture_window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,enabled)
            self.capture_window.setGeometry(geometry); self.capture_window.show()

    def configure_live_shortcuts(self,enabled):
        success=self.live_shortcuts.set_enabled(enabled,self.controller.preferences['shortcut_bindings'])
        if not success:
            self.global_shortcuts.blockSignals(True); self.global_shortcuts.setChecked(False); self.global_shortcuts.blockSignals(False)
            self.show_notice('Atalhos globais indisponíveis. Os atalhos dentro do app continuam ativos.')
        enabled=bool(enabled and success)
        for shortcut in self.local_live_shortcuts+(self.capture_window.shortcuts if self.capture_window else []): shortcut.setEnabled(not enabled)
        self.set_preference('global_shortcuts',enabled)
        rows=shortcut_rows(self.controller.preferences['shortcut_bindings'])
        self.shortcut_summary.setText('\n'.join(f'{chord}: {name}' for chord,_,name in rows[:3]))

    def edit_shortcuts(self):
        dialog=QDialog(self); dialog.setWindowTitle('Personalizar atalhos'); dialog.resize(430,520)
        layout=QVBoxLayout(dialog); layout.addWidget(label('Clique no campo e pressione a combinação.\nLimpe o campo para desativar uma ação.','muted',True))
        grid=QGridLayout(); editors={}
        for row,(_,action,name) in enumerate(SHORTCUTS):
            editor=QKeySequenceEdit(QKeySequence(self.controller.preferences['shortcut_bindings'][action]))
            editor.setMaximumSequenceLength(1); editor.setClearButtonEnabled(True)
            grid.addWidget(label(name),row,0); grid.addWidget(editor,row,1); editors[action]=editor
        layout.addLayout(grid); error_label=label('','muted',True); layout.addWidget(error_label)
        restore=button('Restaurar padrões',lambda:[editor.setKeySequence(QKeySequence(chord)) for chord,action,_ in SHORTCUTS for editor in [editors[action]]]); layout.addWidget(restore)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salvar'); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.rejected.connect(dialog.reject)
        def save():
            try: bindings=validate_bindings({action:editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText) for action,editor in editors.items()})
            except ValueError as error: error_label.setText(str(error)); return
            self.controller.preferences['shortcut_bindings']=bindings
            self.controller.defer_save(); dialog.accept()
        buttons.accepted.connect(save); layout.addWidget(buttons)
        existing=[(shortcut,shortcut.isEnabled()) for shortcut in self.findChildren(QShortcut)]
        self.live_shortcuts.close()
        for shortcut,_ in existing: shortcut.setEnabled(False)
        try: dialog.exec()
        finally:
            for shortcut,enabled in existing: shortcut.setEnabled(enabled)
            self.rebuild_shortcuts()

    def handle_live_shortcut(self,action):
        if self.quitting: return
        if action=='controls':
            if self.isVisible() and not self.isMinimized():
                self.open_capture(); self.hide(); self.toggle_camera_preview()
            else: self.restore_controls()
        elif action=='pause': self.controller.toggle_pause()
        elif action=='microphone': self.controller.toggle_microphone()
        elif action.startswith('expression:'):
            key=action.split(':',1)[1]
            button=self.expression_buttons.get(key)
            if button is not None and not button.isEnabled(): self.show_notice('Esta expressão não está disponível neste avatar.'); return
            self.controller.command('expression',key)
        elif action.startswith('gesture:'): self.controller.play_gesture(action.split(':',1)[1])

    def obs_help(self):
        QMessageBox.information(self,'Capturar no OBS','1. Abra a saída do avatar.\n2. No OBS, adicione Captura de janela.\n3. Selecione 2DCam - Avatar.\n4. Use o método Windows 10 (1903 ou superior) se Automático falhar.\n5. Desative Capturar cursor e ative Área do cliente.\n6. Adicione o filtro Chroma Key para remover o fundo verde/azul.\n\nMantenha a janela de saída aberta e sem minimizar. Para poupar recursos, use o modo Econômico e oculte os controles.\n\nA captura depende do Windows, da GPU e do OBS. Guia oficial: obsproject.com/kb/window-capture-sources')
    def show_notice(self,text): self.statusBar().showMessage(text,12000)
    def set_preference(self,key,value):
        if key in ('face_smoothing','face_strength','idle_motion','idle_strength') and not any(slider.isSliderDown() for slider in self.findChildren(QSlider)): self.controller.record_change()
        self.controller.preferences[key]=value; self.controller.defer_save(); self.controller.changed.emit()
    def set_setting(self,key,value):
        if not any(slider.isSliderDown() for slider in self.findChildren(QSlider)): self.controller.record_change()
        setattr(self.controller.settings,key,value); self.controller.defer_save()

    def activate_3d(self):
        c=self.controller
        if c.model_path.lower().endswith('.model3.json'): c.use_model(str(ASSETS/'AvatarHumanoide.vrm'))
        else: c.switch_mode('3D')

    def open_wizard(self):
        if self.wizard: self.wizard.raise_(); return
        from avatarcam.desktop.dialogs import AvatarWizard
        self.wizard=AvatarWizard(self); self.wizard.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.wizard.setWindowModality(Qt.WindowModality.WindowModal)
        def done(_): self.wizard=None
        self.wizard.finished.connect(done); self.wizard.show()

    def edit_expressions(self):
        c=self.controller
        if c.mode=='2D': self.edit_poses(); return
        if not c.renderer_report.get('loaded'): self.show_notice('Aguarde o personagem carregar antes de editar as expressões.'); return
        from avatarcam.desktop.dialogs import ExpressionEditor
        global_enabled=self.live_shortcuts.enabled; self.live_shortcuts.close()
        try:
            dialog=ExpressionEditor(self); dialog.exec(); dialog.deleteLater()
        finally:
            if global_enabled: self.configure_live_shortcuts(True)

    def open_motion_test(self):
        if self.motion_dialog:
            self.motion_dialog.show(); self.motion_dialog.raise_(); return
        from avatarcam.desktop.dialogs import MotionDialog
        self.motion_dialog=MotionDialog(self); self.motion_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.motion_dialog.finished.connect(lambda _:setattr(self,'motion_dialog',None))
        self.motion_dialog.show(); self.motion_dialog.refresh()

    def edit_poses(self):
        from avatarcam.desktop.dialogs import PoseEditor
        dialog=PoseEditor(self); dialog.exec(); dialog.deleteLater()

    def show_health(self):
        from avatarcam.desktop.dialogs import HealthDialog
        dialog=HealthDialog(self); dialog.exec(); dialog.deleteLater()

    def resolve_issue(self,action):
        if action=='resume': self.controller.toggle_pause()
        elif action=='devices': self.controller.inputs.request_scan(); self.select_panel(2)
        elif action=='camera': self.select_panel(2); self.show_camera.setChecked(True)
        elif action=='audio': self.select_panel(0); self.controller.calibrate_audio()
        elif action=='reload': self.reload_renderer()
        elif action=='expressions': self.edit_expressions()
        elif action=='performance': self.controller.set_performance('auto'); self.sync_profile_controls(); self.select_panel(3)
        elif action=='output': self.select_panel(3)

    def undo_change(self,redo=False):
        if self.controller.travel_history(redo): self.sync_profile_controls(); self.sync()

    def reset_avatar_settings(self):
        from avatarcam.core.settings import Settings
        c=self.controller; c.record_change(); defaults=Settings()
        for key in ('avatar_scale','avatar_offset_x','avatar_offset_y','avatar_rotation','camera3d','sensitivity','smoothing','noise_floor'):
            setattr(c.settings,key,getattr(defaults,key))
        c.preferences.update(face_smoothing=.55,face_strength=1.,idle_motion=True,idle_strength=.5)
        c.preferences['face_neutral']=dict(yaw=0.,pitch=0.,roll=0.); c.smoother.neutral=dict(c.preferences['face_neutral'])
        c.preferences['expression_profiles'].pop(c.identity,None)
        c.manual_expression=None; c.camera_revision+=1; c.remember_avatar(); c.defer_save(); c.changed.emit()
        self.sync_profile_controls(); self.show_notice('Ajustes restaurados. Use Desfazer para recuperar os anteriores.')

    def toggle_transparent(self):
        if self.controller.transparent_active: self.transparent_output.stop(); self.show_notice('Saída transparente desligada.')
        else: self.transparent_output.start()
        self.sync()

    def import_live2d(self,path):
        from avatarcam.desktop.live2d import runtime_available
        if not runtime_available():
            QMessageBox.information(self,'Live2D','A integração está preparada, mas o Cubism Core não acompanha esta versão.\n\nA publicação de apps de rastreamento requer autorização da Live2D. Assim que houver autorização, o componente poderá ser incorporado e validado.\n\nPNG/GIF e VRM/GLB continuam disponíveis.'); return
        self.controller.import_live2d(path)

    def recover_session(self):
        c=self.controller
        restore=False
        if c.recovery.previous:
            restore=QMessageBox.question(self,'Recuperar sessão','O app não encerrou normalmente na última vez. Recuperar personagem e ajustes salvos?\n\nCâmera e microfone continuarão desligados.')==QMessageBox.StandardButton.Yes
        c.start_recovery(restore); self.sync_profile_controls()
    def change_filter(self,index):
        self.controller.settings.speech_mode='vad' if index else 'volume'
        self.controller.microphone.speech_mode=self.controller.settings.speech_mode; self.controller.defer_save()

    def refresh_mics(self):
        self.mic_devices.blockSignals(True); self.mic_devices.clear()
        for item in self.controller.inputs.audio_catalog or [{'name':'Padrão do sistema','index':None,'id':''}]:
            self.mic_devices.addItem(item['name'],item['index'])
            self.mic_devices.setItemData(self.mic_devices.count()-1,item['id'],Qt.ItemDataRole.UserRole+1)
        selected=self.mic_devices.findData(self.controller.settings.microphone_device)
        identity=self.controller.preferences['microphone_identity']
        if identity:
            selected=self.mic_devices.findData(identity,Qt.ItemDataRole.UserRole+1)
            if selected<0:
                self.mic_devices.addItem('Microfone selecionado · desconectado',self.controller.settings.microphone_device)
                selected=self.mic_devices.count()-1; self.mic_devices.setItemData(selected,identity,Qt.ItemDataRole.UserRole+1)
        self.mic_devices.setCurrentIndex(max(0,selected)); self.mic_devices.blockSignals(False)

    def refresh_devices(self):
        inputs=self.controller.inputs
        if inputs.catalog_revision==self.device_signature: return
        self.device_signature=inputs.catalog_revision; self.refresh_mics()
        self.camera_devices.blockSignals(True); self.camera_devices.clear()
        catalog=inputs.camera_catalog or [{'name':f'Câmera {i+1} · sem identificação','index':i,'id':''} for i in range(6)]
        for item in catalog:
            self.camera_devices.addItem(item['name'],item['index'])
            self.camera_devices.setItemData(self.camera_devices.count()-1,item['id'],Qt.ItemDataRole.UserRole+1)
        identity=self.controller.preferences['camera_identity']
        selected=self.camera_devices.findData(identity,Qt.ItemDataRole.UserRole+1) if identity else self.camera_devices.findData(int(self.controller.preferences['camera_device']))
        if selected<0:
            self.camera_devices.addItem('Câmera selecionada · desconectada',int(self.controller.preferences['camera_device']))
            selected=self.camera_devices.count()-1; self.camera_devices.setItemData(selected,identity,Qt.ItemDataRole.UserRole+1)
        self.camera_devices.setCurrentIndex(selected); self.camera_devices.blockSignals(False)

    def change_mic(self,index):
        device=self.mic_devices.itemData(index)
        if index<0: return
        wanted=self.controller.inputs.wanted['audio']; self.controller.inputs.request('audio',False)
        self.set_setting('microphone_device',device)
        self.set_preference('microphone_identity',self.mic_devices.itemData(index,Qt.ItemDataRole.UserRole+1) or '')
        if wanted: self.controller.inputs.request('audio',True)

    def change_camera(self,index):
        if index<0: return
        wanted=self.controller.inputs.wanted['camera']; self.controller.inputs.request('camera',False)
        self.set_preference('camera_device',self.camera_devices.itemData(index))
        self.set_preference('camera_identity',self.camera_devices.itemData(index,Qt.ItemDataRole.UserRole+1) or '')
        if wanted: self.controller.inputs.request('camera',True)

    def sync(self):
        c=self.controller; self.route_avatar(); self.refresh_recent(); self.refresh_devices()
        self.undo_action.setEnabled(bool(c.history.undo)); self.redo_action.setEnabled(bool(c.history.redo))
        self.edit_expression_button.setEnabled(c.mode!='2D' and bool(c.renderer_report.get('loaded')))
        for key, item in self.gesture_buttons.items(): item.setEnabled(not c.paused and (c.mode=='2D' or key in c.renderer_report.get('gestures',[])))
        self.adaptive_status.setText('Em uso: '+c.performance['name'] if c.preferences['performance']=='auto' else '')
        self.transparent_button.setText('Desligar saída transparente' if c.transparent_active else 'Ligar saída transparente')
        self.pause_button.setText('Retomar' if c.paused else 'Pausar')
        self.quick_mic.setChecked(c.inputs.wanted['audio']); self.quick_camera.setChecked(c.inputs.wanted['camera'])
        self.quick_mic.setToolTip(('Desligar' if c.inputs.wanted['audio'] else 'Ativar')+' microfone. '+c.inputs.status['audio'])
        self.quick_camera.setToolTip(('Desligar' if c.inputs.wanted['camera'] else 'Ativar')+' rastreamento. '+c.inputs.status['camera'])
        self.mode_2d.setChecked(c.mode=='2D'); self.mode_3d.setChecked(c.mode!='2D'); self.mode_3d.setText('Live2D' if c.mode=='Live2D' else '3D')
        name=c.avatar_name()
        self.model_name.setToolTip(name); self.model_name.setText(name if len(name)<=32 else name[:29]+'…')
        self.model_name.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.meter.setValue(int(c.level*100)); self.mic_button.setText('Desligar microfone' if c.inputs.wanted['audio'] else 'Ativar microfone')
        self.voice_status.setText('Voz detectada' if c.speaking else 'Ouvindo microfone' if c.microphone.is_running else c.inputs.status['audio'] if c.inputs.wanted['audio'] else 'Microfone desligado')
        self.camera_button.setText('Desligar rastreamento' if c.inputs.wanted['camera'] else 'Ligar rastreamento')
        status=c.inputs.status['camera'] or c.tracking_status
        self.tracking_detail.setText(status)
        if c.motion_source=='preview': status='Testando movimentos sem câmera'
        elif not c.inputs.wanted['camera'] and c.motion_source=='idle': status='Sem câmera · movimentos suaves'
        self.face_status.setText(status)
        for key,btn in self.expression_buttons.items(): btn.setChecked(key==(c.manual_expression or 'auto'))
        if c.renderer_report.get('loaded') and c.mode!='2D':
            supported=c.renderer_report.get('expressions',[])
            for key,btn in self.expression_buttons.items():
                btn.setEnabled(key in ('auto','neutral') or key in supported)
                btn.setToolTip('' if btn.isEnabled() else 'Essa expressão não está incluída neste modelo.')
        else:
            for btn in self.expression_buttons.values(): btn.setEnabled(True)
        face=c.visual_face
        self.face_metrics.setText(f"Boca {face['jaw']:.0%}  ·  Olhos {max(face['blinkLeft'],face['blinkRight']):.0%}\nCabeça: {face['yaw']*57.3:.0f}° / {face['pitch']*57.3:.0f}°")
        if self.panels.currentIndex()==2 and self.show_camera.isChecked() and c.camera_frame is not None:
            if self.last_camera_frame is not c.camera_frame:
                rgb=c.camera_frame; h,w=rgb.shape[:2]
                image=QImage(rgb.data,w,h,w*3,QImage.Format.Format_RGB888).copy().mirrored(True,False)
                self.camera_image.setPixmap(QPixmap.fromImage(image).scaled(240,160,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                self.last_camera_frame=c.camera_frame
        else:
            self.last_camera_frame=None
            self.camera_image.clear(); self.camera_image.setText('Prévia oculta' if c.tracker.running else 'Câmera desligada')
        for slider,value in ((self.sensitivity_slider,c.settings.sensitivity),(self.scale_slider,c.settings.avatar_scale),
                             (self.face_smoothing_slider,c.preferences['face_smoothing']),(self.face_strength_slider,c.preferences['face_strength']),
                             (self.idle_strength_slider,c.preferences['idle_strength'])):
            number=round(value*100)
            if not slider.isSliderDown() and slider.value()!=number:
                slider.blockSignals(True); slider.setValue(number); slider.blockSignals(False)
        for widget,value in ((self.rotate,c.settings.auto_rotate3d),(self.pet,c.settings.pet_enabled),(self.idle_checkbox,c.preferences['idle_motion'])):
            if widget.isChecked()!=value:
                widget.blockSignals(True); widget.setChecked(value); widget.blockSignals(False)

    def choose_2d(self,role='idle'):
        paths,_=QFileDialog.getOpenFileNames(self,'Importar imagens 2D','','Imagens (*.png *.gif)')
        if paths: self.controller.import_2d(paths,role)
    def choose_3d(self):
        path,_=QFileDialog.getOpenFileName(self,'Importar avatar 3D','','Avatar 3D (*.vrm *.glb)')
        if path: self.controller.import_3d(path)
    def choose_any(self):
        path,_=QFileDialog.getOpenFileName(self,'Importar avatar','','Avatares (*.vrm *.glb *.png *.gif *.avatarpack *.model3.json)')
        if path: self.import_path(path)
    def import_path(self,path):
        extension=Path(path).suffix.lower()
        if extension in ('.vrm','.glb'): self.controller.import_3d(path)
        elif extension=='.avatarpack': self.controller.import_pack(path)
        elif extension in ('.png','.gif'): self.controller.import_2d([path])
        elif str(path).lower().endswith('.model3.json'): self.import_live2d(path)
        else: self.show_notice('Formato não suportado. Use PNG, GIF, VRM, GLB ou .avatarpack.')
    def choose_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Pasta com idle / talk / blink')
        if path: self.controller.import_folder(path)
    def choose_pack(self):
        path,_=QFileDialog.getOpenFileName(self,'Importar pacote','','Pacote (*.avatarpack)')
        if path: self.controller.import_pack(path)
    def export_pack(self):
        path,_=QFileDialog.getSaveFileName(self,'Exportar avatar','Meu_avatar.avatarpack','Pacote (*.avatarpack)')
        if path: self.controller.export_pack(path if path.endswith('.avatarpack') else path+'.avatarpack')
    def demo_2d(self):
        self.controller.use_sets({role:[str(ASSETS/f'StudioBot2D/{role}/001.png')] for role in ('idle','talk','blink','pet')})
    def bind_expression(self):
        names={'Feliz':'happy','Bravo':'angry','Triste':'sad','Calmo':'relaxed','Surpreso':'surprised'}
        name,ok=QInputDialog.getItem(self,'Expressão 2D','Quando esta expressão estiver ativa:',list(names),0,False)
        if not ok: return
        paths,_=QFileDialog.getOpenFileNames(self,'Imagens para '+name,'','Imagens (*.png *.gif)')
        if not paths: return
        if self.controller.jobs:
            self.show_notice('Aguarde a importação atual antes de vincular uma expressão.'); return
        role='_mapped'; key=names[name]
        def success(result):
            self.controller.preferences.setdefault('expressions2d',{})[key]=result
            self.controller.remember_avatar(); self.controller.changed.emit()
            self.controller.defer_save(); self.show_notice('Expressão vinculada: '+name)
        # Importacao usa a mesma biblioteca de imagens, sem alterar a pose parada.
        self.controller.import_2d(paths,role)
        if self.controller.jobs:
            future,_=self.controller.jobs[-1]; self.controller.jobs[-1]=(future,success)
    def refresh_recent(self, force=False):
        signature=self.controller.library_revision
        if not force and signature==self.recent_signature: return
        self.recent_signature=signature
        selected=self.library_list.currentItem()
        identity=selected.data(Qt.ItemDataRole.UserRole) if selected else avatar_id(dict(mode=self.controller.mode,path=self.controller.model_path,sets=self.controller.sets))
        self.library_list.clear(); mode=self.library_filter.currentIndex()
        entries=sorted(self.controller.preferences['avatar_library'],key=lambda item:not item.get('favorite'))
        for entry in entries:
            if mode==1 and not entry.get('favorite'): continue
            if mode in (2,3) and entry['mode']!=('2D' if mode==2 else '3D'): continue
            key=avatar_id(entry)
            path=APP_DIR/'thumbnails'/(key+'.png') if entry['mode']!='2D' else Path(entry['sets']['idle'][0])
            reader=QImageReader(str(path)); size=reader.size(); icon=QIcon(str(ASSETS/'studio.ico'))
            if size.isValid() and size.width()*size.height()<=32_000_000:
                reader.setScaledSize(size.scaled(96,96,Qt.AspectRatioMode.KeepAspectRatio))
                image=reader.read()
                if not image.isNull(): icon=QIcon(QPixmap.fromImage(image))
            name=entry['name']; text=('★ ' if entry.get('favorite') else '')+name+'\n'+entry['mode']
            item=QListWidgetItem(icon,text,self.library_list); item.setSizeHint(QSize(220,76))
            item.setData(Qt.ItemDataRole.UserRole,key); item.setToolTip(name+' · clique para usar')
            if key==identity: self.library_list.setCurrentItem(item)
        self.sync_library_actions()

    def sync_library_actions(self,*_):
        item=self.library_list.currentItem()
        identity=item.data(Qt.ItemDataRole.UserRole) if item else None
        entry=next((entry for entry in self.controller.preferences['avatar_library'] if avatar_id(entry)==identity),None)
        self.favorite_button.setEnabled(entry is not None); self.rename_button.setEnabled(entry is not None)
        self.favorite_button.setText('Desfavoritar' if entry and entry.get('favorite') else 'Favoritar')

    def favorite_avatar(self):
        item=self.library_list.currentItem()
        if not item: return
        identity=item.data(Qt.ItemDataRole.UserRole)
        entry=next(entry for entry in self.controller.preferences['avatar_library'] if avatar_id(entry)==identity)
        self.controller.edit_library(identity,favorite=not entry.get('favorite'))

    def rename_avatar(self):
        item=self.library_list.currentItem()
        if not item: return
        identity=item.data(Qt.ItemDataRole.UserRole)
        entry=next(entry for entry in self.controller.preferences['avatar_library'] if avatar_id(entry)==identity)
        name,ok=QInputDialog.getText(self,'Renomear avatar','Nome na biblioteca:',text=entry['name'])
        if ok and not self.controller.edit_library(identity,name=name): self.show_notice('Informe um nome para o avatar.')

    def capture_thumbnail(self):
        c=self.controller
        if c.mode=='2D' or not self.avatar3d or not c.renderer_report.get('loaded') or self.capture_window or not self.isVisible(): return
        identity=c.identity
        path=APP_DIR/'thumbnails'/(identity+'.png')
        if path.exists(): return
        pixmap=self.avatar3d.grab()
        if pixmap.isNull(): return
        path.parent.mkdir(parents=True,exist_ok=True)
        if pixmap.scaled(96,96,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation).save(str(path)):
            c.library_revision+=1

    def refresh_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear(); self.profile_combo.addItems(list((self.controller.settings.profiles or {}).keys()))
        index=self.profile_combo.findText(self.controller.settings.active_profile)
        if index>=0: self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
    def save_profile(self):
        name,ok=QInputDialog.getText(self,'Salvar perfil','Nome do perfil:')
        if not ok or not name.strip(): return
        from avatarcam.desktop.profiles import save_profile
        if name.strip() in (self.controller.settings.profiles or {}):
            if QMessageBox.question(self,'Substituir perfil','Substituir o perfil '+name.strip()+'?')!=QMessageBox.StandardButton.Yes: return
        try:
            save_profile(self.controller,name); self.refresh_profiles(); self.show_notice('Perfil salvo.')
        except ValueError as exc: self.show_notice(str(exc))
    def load_profile(self,index):
        try:
            from avatarcam.desktop.profiles import load_profile
            load_profile(self.controller,self.profile_combo.itemText(index)); self.sync_profile_controls()
            self.show_notice('Perfil carregado.')
        except Exception as exc: self.show_notice(str(exc))
    def delete_profile(self):
        name=self.profile_combo.currentText()
        if not name: return
        if QMessageBox.question(self,'Excluir perfil','Excluir o perfil '+name+'? Os arquivos do avatar serão mantidos.')!=QMessageBox.StandardButton.Yes: return
        from avatarcam.desktop.profiles import delete_profile
        delete_profile(self.controller,name); self.refresh_profiles(); self.show_notice('Perfil excluído.')

    def sync_profile_controls(self):
        c=self.controller
        for combo,key in ((self.performance_combo,'performance'),(self.output_size,'output_size'),(self.output_background,'output_background')):
            combo.blockSignals(True); combo.setCurrentIndex(max(0,combo.findData(c.preferences.get(key)))); combo.blockSignals(False)
        self.hide_controls.blockSignals(True); self.hide_controls.setChecked(c.preferences.get('hide_controls',False)); self.hide_controls.blockSignals(False)
        self.output_on_top.blockSignals(True); self.output_on_top.setChecked(c.preferences['output_on_top']); self.output_on_top.blockSignals(False)
        self.change_output_top(c.preferences['output_on_top'])
        self.filter_combo.blockSignals(True); self.filter_combo.setCurrentIndex(1 if c.settings.speech_mode=='vad' else 0); self.filter_combo.blockSignals(False)
        for widget,value in ((self.rotate,c.settings.auto_rotate3d),(self.pet,c.settings.pet_enabled)):
            widget.blockSignals(True); widget.setChecked(value); widget.blockSignals(False)
        for slider,value in ((self.face_smoothing_slider,c.preferences['face_smoothing']), (self.face_strength_slider,c.preferences['face_strength']), (self.scale_slider,c.settings.avatar_scale)):
            slider.blockSignals(True); slider.setValue(round(value*100)); slider.blockSignals(False)
        if self.capture_window:
            key=c.preferences.get('output_size','540p')
            self.capture_window.resize(*output_size(key))
    def reset_camera(self):
        if self.controller.mode!='2D': self.controller.command('reset_camera')
        else:
            self.controller.record_change()
            s=self.controller.settings; s.avatar_offset_x=s.avatar_offset_y=s.avatar_rotation=0.; s.avatar_scale=1.; self.controller.defer_save()
    def save_camera(self):
        if self.controller.mode!='2D' and self.avatar3d: self.avatar3d.page().runJavaScript("window.studioSaveCamera ? window.studioSaveCamera() : document.getElementById('save-camera').click()")
        else: self.controller.save()
        self.show_notice('Posição salva.')
    def open_capture(self):
        if self.capture_window is None:
            self.capture_window=CaptureWindow(self.controller,self)
            self.controller.output_active=True; self.route_avatar()
        self.capture_window.show(); self.capture_window.raise_(); self.capture_window.activateWindow()
        if self.hide_controls.isChecked(): self.hide(); self.toggle_camera_preview()
        self.controller.set_render_active(True)

    def save_image(self):
        path,_=QFileDialog.getSaveFileName(self,'Salvar prévia','Meu_avatar.png','PNG (*.png)')
        if path:
            widget=self.avatar3d if self.controller.mode!='2D' else self.avatar2d
            widget.grab().save(path); self.show_notice('Imagem salva.')
    def export_diagnostics(self):
        path,_=QFileDialog.getSaveFileName(self,'Diagnóstico','2DCam-diagnostico.json','JSON (*.json)')
        if path:
            data={'version':'3.5','mode':self.controller.mode,'embedded_renderer':self.controller.renderer_report,
                  'camera_running':self.controller.tracker.running,'face_detected':self.controller.face['detected'],
                  'vad_available':self.controller.microphone.vad_available,'renderer_errors':self.avatar3d.page().console_errors if self.avatar3d else [],
                  'performance':self.controller.preferences.get('performance'), 'process_usage':getattr(self.controller,'resource_usage',{})}
            atomic_write_text(Path(path),json.dumps(data,indent=2)); self.show_notice('Diagnóstico salvo sem imagens da câmera.')
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if urls and urls[0].isLocalFile(): self.import_path(urls[0].toLocalFile())
    def closeEvent(self,event):
        self.quitting=True; self.stats_timer.stop(); self.sync_timer.stop(); self.live_shortcuts.close()
        if self.motion_dialog: self.motion_dialog.close()
        self.transparent_output.stop()
        if self.capture_window: self.capture_window.close()
        self.controller.close()
        if self.avatar3d: self.avatar3d.release()
        event.accept()

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.WindowStateChange and hasattr(self,'show_camera'):
            self.toggle_camera_preview()
            self.update_render_visibility()
