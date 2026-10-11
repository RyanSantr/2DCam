"""Ferramentas abertas sob demanda para manter o estúdio compacto."""
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImageReader, QPixmap, QMovie
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSlider, QDialogButtonBox, QFileDialog, QScrollArea, QWidget, QStackedWidget)
from avatarcam.desktop.creative import EXPRESSION_ACTIONS

NAMES = dict(neutral='Neutro', happy='Feliz', angry='Bravo', sad='Triste', relaxed='Calmo', surprised='Surpreso', mouth='Boca', blink='Piscar')


def push(text, callback):
    button = QPushButton(text); button.clicked.connect(lambda _: callback()); return button


def text(value):
    item = QLabel(value); item.setWordWrap(True); return item


class ExpressionEditor(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.c = owner.controller; self.setWindowTitle('Expressões do personagem'); self.resize(640, 540)
        layout = QVBoxLayout(self)
        layout.addWidget(text('Escolha o recurso do modelo para cada ação. Testar mostra a intensidade na prévia; Salvar mantém os vínculos deste personagem.'))
        catalog = self.c.renderer_report.get('expressionCatalog', [])
        grid = QGridLayout(); self.rows = {}
        for row, action in enumerate(EXPRESSION_ACTIONS):
            combo = QComboBox(); combo.addItem('Desativado', '')
            for target in catalog: combo.addItem({'aa':'Boca A (aa)','blink':'Piscar (blink)'}.get(target,target.replace('morph:','Forma: ')), target)
            default = {'mouth': 'ParamMouthOpenY' if self.c.mode == 'Live2D' else 'aa', 'blink': 'ParamEyeLOpen' if self.c.mode == 'Live2D' else 'blink'}.get(action, action)
            item = self.c.expression_mapping.get(action, dict(target=default, intensity=1.))
            combo.setCurrentIndex(max(0, combo.findData(item['target'])))
            slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(0, 100); slider.setValue(round(item['intensity']*100))
            percent = QLabel(str(slider.value())+'%'); slider.valueChanged.connect(lambda v, label=percent: label.setText(str(v)+'%'))
            grid.addWidget(QLabel(NAMES[action]), row, 0); grid.addWidget(combo, row, 1); grid.addWidget(slider, row, 2); grid.addWidget(percent, row, 3)
            grid.addWidget(push('Testar', lambda a=action: self.preview(a)), row, 4)
            self.rows[action] = (combo, slider)
        layout.addLayout(grid)
        layout.addWidget(push('Parar teste', self.stop_preview))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salvar'); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.finished.connect(lambda _: self.stop_preview())

    def preview(self, action):
        combo, slider = self.rows[action]; self.c.expression_preview = dict(target=combo.currentData(), intensity=slider.value()/100)
        self.c.changed.emit()

    def stop_preview(self): self.c.expression_preview = None; self.c.changed.emit()

    def save(self):
        self.c.set_expression_mapping({action: dict(target=combo.currentData(), intensity=slider.value()/100) for action, (combo, slider) in self.rows.items()})
        self.c.remember_avatar(); self.c.notice.emit('Expressões salvas para este personagem.'); self.accept()


class PoseSlot(QPushButton):
    def __init__(self, role, name, owner):
        super().__init__(name); self.role = role; self.owner = owner; self.name = name; self.setAcceptDrops(True)
        self.setMinimumHeight(40); self.clicked.connect(self.choose)

    def choose(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Imagens para '+self.name, '', 'Imagens (*.png *.gif)')
        if paths: self.assign(paths)

    def assign(self, paths):
        valid = [str(Path(path)) for path in paths if Path(path).suffix.lower() in ('.png', '.gif') and Path(path).is_file()][:256]
        if not valid: return
        self.owner.poses[self.role] = valid; self.setText(self.name+' · '+str(len(valid))+' arquivo(s)'); self.owner.preview(self.role)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        self.assign([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]); event.acceptProposedAction()


class PoseEditor(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.owner = owner; self.setWindowTitle('Montar personagem 2D'); self.resize(720, 620)
        c = owner.controller; self.poses = {key: list(paths) for key, paths in c.sets.items() if key in ('idle', 'talk', 'blink')} if c.mode == '2D' else {}
        if c.mode == '2D': self.poses.update({key: list(paths) for key, paths in c.preferences['expressions2d'].items()})
        self.movie = None; layout = QVBoxLayout(self)
        layout.addWidget(text('Arraste PNG/GIF para cada pose ou clique para escolher. Teste as poses antes de salvar. A imagem parada é obrigatória.'))
        body = QHBoxLayout(); slots = QVBoxLayout(); self.slots = {}
        for role, name in [('idle', 'Parado'), ('talk', 'Falando'), ('blink', 'Piscando'), *[(key, NAMES[key]) for key in ('happy', 'angry', 'sad', 'relaxed', 'surprised')]]:
            row = QHBoxLayout(); slot = PoseSlot(role, name, self); row.addWidget(slot)
            if self.poses.get(role): slot.setText(name+' · '+str(len(self.poses[role]))+' arquivo(s)')
            row.addWidget(push('▶', lambda r=role: self.preview(r)))
            row.addWidget(push('×', lambda r=role: self.clear_role(r)))
            slots.addLayout(row); self.slots[role] = slot
        body.addLayout(slots, 1); self.image = QLabel('Escolha uma pose'); self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(280, 280); self.image.setStyleSheet('background:#1a1c20;border-radius:8px;'); body.addWidget(self.image, 1); layout.addLayout(body, 1)
        self.error = text(''); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salvar'); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.finished.connect(lambda _: self.stop_movie()); self.preview('idle')

    def clear_role(self, role):
        self.poses.pop(role, None); self.slots[role].setText(self.slots[role].name); self.preview(role)

    def stop_movie(self):
        if self.movie: self.movie.stop(); self.movie.deleteLater(); self.movie = None

    def preview(self, role):
        self.stop_movie(); paths = self.poses.get(role, [])
        if not paths: self.image.clear(); self.image.setText('Esta pose está vazia.'); return
        reader = QImageReader(paths[0]); size = reader.size()
        if not size.isValid() or size.width()*size.height() > 32_000_000:
            self.image.setText('Imagem inválida ou grande demais.'); return
        size = size.scaled(320, 400, Qt.AspectRatioMode.KeepAspectRatio)
        if paths[0].lower().endswith('.gif'):
            self.movie = QMovie(paths[0], parent=self); self.movie.setScaledSize(size); self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
            self.image.setMovie(self.movie); self.movie.start()
        else:
            reader.setScaledSize(size); self.image.setPixmap(QPixmap.fromImage(reader.read()))

    def save(self):
        if not self.poses.get('idle'): self.error.setText('Adicione pelo menos uma imagem em Parado.'); return
        if self.owner.controller.import_pose_set(self.poses): self.accept()


class AvatarWizard(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.owner = owner; self.c = owner.controller
        self.setWindowTitle('Preparar personagem'); self.resize(520, 430); layout = QVBoxLayout(self)
        self.steps = QStackedWidget(); layout.addWidget(self.steps, 1)
        first = QWidget(); page = QVBoxLayout(first)
        self.summary = text('Verificando o personagem…'); page.addWidget(self.summary)
        page.addWidget(push('Editar poses 2D' if self.c.mode == '2D' else 'Editar expressões', owner.edit_poses if self.c.mode == '2D' else owner.edit_expressions))
        page.addStretch(); self.steps.addWidget(first)
        second = QWidget(); page = QVBoxLayout(second)
        page.addWidget(text('Ative as entradas que quiser usar. Com a câmera ligada, olhe para a frente e calibre a posição neutra. Para o microfone, fique em silêncio durante a calibração.'))
        page.addWidget(push('Ligar / desligar câmera', self.c.toggle_tracking)); page.addWidget(push('Calibrar rosto', self.c.calibrate_face))
        page.addWidget(push('Ligar / desligar microfone', self.c.toggle_microphone)); page.addWidget(push('Calibrar microfone', self.c.calibrate_audio))
        page.addStretch(); self.steps.addWidget(second)
        third = QWidget(); page = QVBoxLayout(third)
        page.addWidget(text('O enquadramento e os ajustes serão guardados para este personagem. Use Desfazer se quiser voltar a uma alteração anterior. Você pode abrir este guia novamente a qualquer momento.'))
        page.addWidget(push('Testar fala', lambda: self.c.command('test'))); page.addStretch(); self.steps.addWidget(third)
        self.status = text(''); layout.addWidget(self.status)
        nav = QHBoxLayout(); self.back = push('Voltar', lambda: self.step(-1)); self.next = push('Continuar', self.advance)
        nav.addWidget(push('Configurar depois', self.reject)); nav.addStretch(); nav.addWidget(self.back); nav.addWidget(self.next); layout.addLayout(nav)
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_status); self.timer.start(700)
        self.finished.connect(lambda _: self.timer.stop()); self.step(0); self.update_status()

    def update_status(self):
        report = self.c.renderer_report
        if self.c.mode == '2D':
            self.summary.setText('Personagem 2D pronto.\nFala: '+('configurada' if self.c.sets.get('talk') else 'adicione uma pose')+'\nPiscar: '+('configurado' if self.c.sets.get('blink') else 'adicione uma pose'))
        elif report.get('loaded'):
            self.summary.setText('Personagem carregado.\n'+str(len(report.get('expressionCatalog', [])))+' recursos de expressão disponíveis.\nBoca: '+('disponível' if report.get('hasMouth') else 'precisa de configuração ou não está no modelo'))
        else: self.summary.setText(str(report.get('error') or 'Aguardando o personagem terminar de carregar…'))
        self.status.setText('Câmera: '+self.c.tracking_status+'\nMicrofone: '+('ligado' if self.c.microphone.is_running else 'desligado'))

    def step(self, offset):
        index = max(0, min(2, self.steps.currentIndex()+offset)); self.steps.setCurrentIndex(index)
        self.back.setEnabled(index > 0); self.next.setText('Salvar e concluir' if index == 2 else 'Continuar')

    def advance(self):
        if self.steps.currentIndex() < 2: self.step(1)
        else:
            self.c.remember_avatar(); self.c.save(); self.c.notice.emit('Personagem configurado e salvo na biblioteca.'); self.accept()


class HealthDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.owner = owner; self.setWindowTitle('Verificar funcionamento'); self.resize(500, 450)
        layout = QVBoxLayout(self); self.area = QWidget(); self.items = QVBoxLayout(self.area)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.area); layout.addWidget(scroll)
        layout.addWidget(push('Fechar', self.accept)); self.signature = None
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(2000)
        self.finished.connect(lambda _: self.timer.stop()); self.refresh()

    def refresh(self):
        issues = self.owner.controller.issues()
        if issues == self.signature: return
        self.signature = issues
        while self.items.count():
            item = self.items.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not issues: self.items.addWidget(text('Nenhum problema identificado nas funções em uso. Câmera e microfone só são verificados quando você os liga.'))
        for title, message, action in issues:
            self.items.addWidget(text(title+'\n'+message))
            self.items.addWidget(push('Ajustar', lambda a=action: self.fix(a)))
        self.items.addStretch()

    def fix(self, action):
        self.accept(); self.owner.resolve_issue(action)
