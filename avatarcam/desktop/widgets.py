"""Controles de teclado e tema compartilhados pela interface nativa."""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPalette, QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QSlider, QLabel, QCheckBox, QStyle, QStyleOption, QStyleOptionComboBox, QStyleOptionButton


def apply_theme(app):
    app.setStyle('Fusion')
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, '#1d2026'),
                        (QPalette.ColorRole.WindowText, '#eceef3'),
                        (QPalette.ColorRole.Base, '#171a20'),
                        (QPalette.ColorRole.AlternateBase, '#252932'),
                        (QPalette.ColorRole.Text, '#eceef3'),
                        (QPalette.ColorRole.Button, '#2b3039'),
                        (QPalette.ColorRole.ButtonText, '#eceef3'),
                        (QPalette.ColorRole.Highlight, '#5675b5'),
                        (QPalette.ColorRole.HighlightedText, '#ffffff'),
                        (QPalette.ColorRole.ToolTipBase, '#2b3039'),
                        (QPalette.ColorRole.ToolTipText, '#eceef3')):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor('#838995'))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor('#838995'))
    app.setPalette(palette)


class ToggleBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        area = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        painter = QPainter(self)
        painter.setPen(QPen(QColor('#91a1bb' if self.isEnabled() else '#586274'), 1))
        painter.drawRect(area.adjusted(0, 0, -1, -1))


class ChoiceBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        area = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                          QStyle.SubControl.SC_ComboBoxArrow, self)
        arrow = QStyleOption()
        arrow.palette = option.palette
        arrow.state = option.state
        arrow.rect = QRect(area.center().x() - 6, area.center().y() - 6, 12, 12)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorArrowDown, arrow, painter, self)


class ValueSlider(QSlider):
    def __init__(self, title, record_change, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.record_change = record_change
        self.value_label = QLabel()
        self.value_label.setObjectName('value')
        self.setAccessibleName(title)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.valueChanged.connect(self.update_value)

    def update_value(self, value):
        text = str(value) + '%'
        self.value_label.setText(text)
        self.setAccessibleDescription(text)

    def setValue(self, value):
        super().setValue(value)
        self.update_value(self.value())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.record_change()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                           Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            if not event.isAutoRepeat():
                self.record_change()
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if self.hasFocus():
            self.record_change()
            super().wheelEvent(event)
        else:
            event.ignore()
