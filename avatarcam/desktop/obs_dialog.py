"""Conexão local e vínculos visuais das cenas do OBS."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView)
from avatarcam.desktop.widgets import ChoiceBox as QComboBox, ToggleBox as QCheckBox
from avatarcam.desktop.obs_sync import obs_config, protect_password


class ObsDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.owner=owner; self.sync=owner.obs_sync
        self.setWindowTitle('Cenas do OBS'); self.resize(680,640)
        layout=QVBoxLayout(self)
        help_label=QLabel('No OBS, abra Ferramentas → Configurações do servidor WebSocket.\n'
            'Marque Habilitar servidor WebSocket e clique em Aplicar no OBS.\n'
            'Use aqui a mesma porta e a senha exibidas pelo OBS.\n'
            'A conexão fica neste computador; não precisa instalar outro complemento.')
        help_label.setWordWrap(True); layout.addWidget(help_label)
        config=obs_config(owner.controller.preferences.get('obs'))
        fields=QHBoxLayout(); fields.addWidget(QLabel('Porta'))
        self.port=QSpinBox(); self.port.setRange(1024,65535); self.port.setValue(config['port']); fields.addWidget(self.port)
        fields.addWidget(QLabel('Senha'))
        self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMaxLength(1024); self.password.setText(self.sync.password or owner.obs_password())
        fields.addWidget(self.password,1); layout.addLayout(fields)
        self.remember=QCheckBox('Lembrar senha neste usuário do Windows'); self.remember.setChecked(config['remember']); layout.addWidget(self.remember)
        buttons=QHBoxLayout(); connect=QPushButton('Conectar / Reconectar'); connect.clicked.connect(self.connect_obs); buttons.addWidget(connect)
        disconnect=QPushButton('Desconectar'); disconnect.clicked.connect(owner.disconnect_obs); buttons.addWidget(disconnect); layout.addLayout(buttons)
        self.status=QLabel(self.sync.status); self.status.setTextFormat(Qt.TextFormat.PlainText); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.current_scene=QLabel(); self.current_scene.setTextFormat(Qt.TextFormat.PlainText); self.current_scene.setWordWrap(True); layout.addWidget(self.current_scene)
        self.empty=QLabel(); self.empty.setWordWrap(True); layout.addWidget(self.empty)
        self.table=QTableWidget(0,2); self.table.setHorizontalHeaderLabels(['Cena no OBS','Personagem / cena no 2DCam'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide(); layout.addWidget(self.table,1)
        note=QLabel('A troca segue a cena em programa do OBS, pelo teclado ou pelo mouse.\n'
            'No Modo Estúdio, o personagem muda ao enviar a cena para o programa.\n'
            'Escolha abaixo qual cena salva do 2DCam corresponde a cada cena do OBS.\n'
            'Não é necessário repetir os atalhos do OBS. Os vínculos são salvos ao escolher.')
        note.setWordWrap(True); layout.addWidget(note)
        repair=QPushButton('Corrigir captura preta nas fontes do 2DCam'); repair.setEnabled(self.sync.ready)
        repair.clicked.connect(self.sync.repair_capture); self.sync.availability_changed.connect(repair.setEnabled); layout.addWidget(repair)
        self.capture_status=QLabel(); self.capture_status.setWordWrap(True); layout.addWidget(self.capture_status)
        self.sync.capture_status_changed.connect(self.capture_status.setText)
        close=QPushButton('Concluído'); close.clicked.connect(self.accept); layout.addWidget(close)
        self.sync.status_changed.connect(self.status.setText); self.sync.scenes_changed.connect(self.refresh)
        self.sync.program_changed.connect(self.update_program)
        self.sync.availability_changed.connect(lambda _:self.update_program())
        self.refresh()

    def connect_obs(self):
        password=self.password.text(); config=obs_config(self.owner.controller.preferences.get('obs'))
        try: secret=protect_password(password) if self.remember.isChecked() and password else ''
        except (OSError,ValueError): self.status.setText('Não foi possível lembrar a senha neste Windows. Desmarque essa opção para conectar.'); return
        config.update(enabled=True,port=self.port.value(),remember=self.remember.isChecked(),secret=secret)
        self.owner.controller.preferences['obs']=config; self.owner.controller.defer_save()
        self.owner.obs_sync.connect_obs(config['port'],password)

    def refresh(self):
        config=obs_config(self.owner.controller.preferences.get('obs')); names=list(self.owner.controller.settings.profiles or {})
        self.empty.setText('Salve um personagem em Salvar cena no 2DCam para criar os vínculos.' if not names else
            'Conecte ao OBS para listar as cenas.' if not self.sync.ready else
            'Aguardando a lista de cenas do OBS…' if not self.sync.scenes else '')
        self.empty.setVisible(bool(self.empty.text())); self.update_program()
        self.table.setRowCount(0)
        for index,scene in enumerate(self.sync.scenes):
            self.table.insertRow(index)
            item=QTableWidgetItem(scene['name']); item.setFlags(Qt.ItemFlag.ItemIsEnabled); self.table.setItem(index,0,item)
            combo=QComboBox(); combo.addItem('Manter personagem atual','')
            for name in names: combo.addItem(name,name)
            target=config['links'].get(scene['key'],scene['name'] if scene['name'] in names else '')
            combo.setCurrentIndex(max(0,combo.findData(target))); self.table.setCellWidget(index,1,combo)
            combo.currentIndexChanged.connect(lambda _,key=scene['key'],field=combo:self.link(key,field.currentData()))
        self.table.resizeRowsToContents()

    def update_program(self):
        name=self.sync.program.get('name') if self.sync.ready else None
        self.current_scene.setText('Cena em programa: '+name if name else '')

    def link(self,key,name):
        self.owner.set_obs_link(key,name)
