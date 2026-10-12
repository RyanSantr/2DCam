"""Ferramentas abertas sob demanda para manter o estúdio compacto."""
from pathlib import Path
import math
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSlider, QSpinBox, QDialogButtonBox, QFileDialog, QScrollArea, QWidget, QStackedWidget)
from avatarcam.desktop.creative import EXPRESSION_ACTIONS
from avatarcam.core.image_sequence import IMAGE_FILTER, image_paths
from avatarcam.desktop.sequence_preview import SequencePreview

NAMES = dict(neutral='Neutro', happy='Feliz', angry='Bravo', sad='Triste', relaxed='Calmo', surprised='Surpreso', mouth='Boca', blink='Piscar')


def push(text, callback):
    button = QPushButton(text); button.clicked.connect(lambda _: callback()); return button


def text(value):
    item = QLabel(value); item.setWordWrap(True); return item


class MotionDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.c = owner.controller
        self.setWindowTitle('Testar movimentos sem câmera'); self.resize(380, 500)
        layout = QVBoxLayout(self)
        layout.addWidget(text('Veja o personagem na janela do app. O teste simula os movimentos e não liga câmera nem microfone.'))
        self.status = text('Arraste um controle ou reproduza o teste completo.'); layout.addWidget(self.status)
        self.sliders = {}; grid = QGridLayout()
        fields = [('yaw','Virar cabeça',-45,45), ('pitch','Subir / baixar',-45,45),
                  ('roll','Inclinar',-45,45), ('gazeX','Olhar lateral',-100,100),
                  ('gazeY','Olhar vertical',-100,100), ('jaw','Abrir boca',0,100),
                  ('blinkLeft','Fechar olhos',0,100), ('smile','Sorriso',0,100)]
        for row, (key, title, low, high) in enumerate(fields):
            slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(low,high)
            slider.setAccessibleName(title); slider.setToolTip(title)
            slider.valueChanged.connect(lambda _: self.apply())
            self.sliders[key] = slider; grid.addWidget(text(title),row,0); grid.addWidget(slider,row,1)
        layout.addLayout(grid)
        self.play_button = push('Reproduzir teste · 12 segundos', self.play); layout.addWidget(self.play_button)
        layout.addWidget(push('Voltar ao normal', self.reset))
        layout.addWidget(push('Fechar', self.accept))
        self.finished.connect(lambda _: self.c.stop_motion_preview())
        self.c.changed.connect(self.refresh)

    def apply(self):
        values = {key: math.radians(slider.value()) if key in ('yaw','pitch','roll') else slider.value()/100 for key, slider in self.sliders.items()}
        values['blinkRight'] = values['blinkLeft']
        self.c.preview_motion(values)

    def play(self): self.c.preview_motion(sequence=True)

    def reset(self):
        for slider in self.sliders.values():
            slider.blockSignals(True); slider.setValue(0); slider.blockSignals(False)
        self.c.stop_motion_preview()

    def refresh(self):
        allowed = not self.c.paused and not self.c.inputs.wanted['camera']
        self.play_button.setEnabled(allowed)
        for slider in self.sliders.values(): slider.setEnabled(allowed)
        preview = self.c.motion_preview
        if not allowed: message = 'Retome o personagem e desligue o rastreamento para testar.'
        elif preview.active and preview.sequence:
            elapsed = min(11, max(0, int(self.c.last_tick-preview.started)))
            message = ('Cabeça','Olhos','Boca','Piscar e sorrir')[elapsed//3] + f' · {elapsed+1}/12 segundos'
        elif preview.active: message = 'Prévia manual. Voltar ao normal encerra a simulação.'
        else: message = 'Pronto. Arraste um controle ou reproduza o teste completo.'
        if self.status.text() != message: self.status.setText(message)


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
        paths, _ = QFileDialog.getOpenFileNames(self, 'Imagens para '+self.name, '', IMAGE_FILTER)
        if paths: self.assign(paths)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Sequência para ' + self.name)
        if path: self.assign([path])

    def assign(self, paths):
        valid = image_paths(paths)
        if not valid: return
        if len(valid) > 256: self.owner.error.setText('Use até 256 arquivos por pose.'); return
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
        layout = QVBoxLayout(self)
        layout.addWidget(text('Cada pose aceita PNG, GIF ou WebP, um ou vários arquivos. Arraste uma sequência ou uma pasta; os nomes seguem a ordem 1, 2, 10. Parado é obrigatório.'))
        body = QHBoxLayout(); slots = QVBoxLayout(); self.slots = {}
        for role, name in [('idle', 'Parado'), ('talk', 'Falando'), ('blink', 'Piscando'), *[(key, NAMES[key]) for key in ('happy', 'angry', 'sad', 'relaxed', 'surprised')]]:
            row = QHBoxLayout(); slot = PoseSlot(role, name, self); row.addWidget(slot)
            if self.poses.get(role): slot.setText(name+' · '+str(len(self.poses[role]))+' arquivo(s)')
            row.addWidget(push('Pasta', slot.choose_folder))
            row.addWidget(push('▶', lambda r=role: self.preview(r)))
            row.addWidget(push('×', lambda r=role: self.clear_role(r)))
            slots.addLayout(row); self.slots[role] = slot
        body.addLayout(slots, 1); self.image = SequencePreview(self); self.image.set_fps(c.settings.animation_fps); self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(280, 280); self.image.setStyleSheet('background:#1a1c20;border-radius:8px;'); body.addWidget(self.image, 1); layout.addLayout(body, 1)
        playback = QHBoxLayout(); self.frame_count = text(''); playback.addWidget(self.frame_count, 1)
        self.pause_button = push('Pausar prévia', self.pause_preview); self.pause_button.setEnabled(False); playback.addWidget(self.pause_button)
        playback.addWidget(push('Reiniciar', self.restart_preview)); layout.addLayout(playback)
        speed = QHBoxLayout(); speed.addWidget(text('Velocidade das imagens em sequência'))
        self.fps = QSpinBox(); self.fps.setRange(1, 30); self.fps.setSuffix(' quadros/s'); self.fps.setValue(c.settings.animation_fps)
        self.fps.setAccessibleName('Velocidade da sequência'); self.fps.valueChanged.connect(self.change_fps); speed.addWidget(self.fps); layout.addLayout(speed)
        layout.addWidget(text('GIF, WebP e PNG animados mantêm seus tempos originais. Até 256 quadros por pose; reduza o tamanho se a animação for pesada.'))
        self.error = text(''); layout.addWidget(self.error)
        self.image.failed.connect(self.error.setText); self.image.progress.connect(self.show_frame)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salvar'); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.finished.connect(lambda _: self.image.release()); self.preview('idle')

    def clear_role(self, role):
        self.poses.pop(role, None); self.slots[role].setText(self.slots[role].name); self.preview(role)

    def show_frame(self, index, total):
        self.frame_count.setText(f'Quadro {index} de {total}')
        self.pause_button.setEnabled(total > 1)

    def pause_preview(self):
        self.image.toggle_pause(); self.pause_button.setText('Reproduzir prévia' if self.image.paused else 'Pausar prévia')

    def restart_preview(self):
        self.image.restart(); self.pause_button.setText('Pausar prévia')

    def change_fps(self, fps):
        self.image.set_fps(fps); self.pause_button.setText('Pausar prévia')

    def preview(self, role):
        self.image.stop(); self.frame_count.clear(); self.error.clear(); self.pause_button.setEnabled(False); self.pause_button.setText('Pausar prévia')
        paths = self.poses.get(role, [])
        if not paths: self.image.setText('Esta pose está vazia.'); return
        self.image.play(list(paths))

    def save(self):
        if not self.poses.get('idle'): self.error.setText('Adicione pelo menos uma imagem em Parado.'); return
        if self.owner.controller.import_pose_set(self.poses, self.fps.value()): self.accept()


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
