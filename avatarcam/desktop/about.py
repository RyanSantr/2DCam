"""Ajuda e creditos acessiveis dentro do executavel."""
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QTextBrowser, QDialogButtonBox

VERSION = '3.9.0'
ROOT = Path(__file__).resolve().parents[2]


def show_about(parent):
    from avatarcam.core.settings import APP_DIR
    dialog = QDialog(parent); dialog.setWindowTitle('Sobre o 2DCam'); dialog.resize(720,520)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('2DCam Studio ' + VERSION + '\nConfigurações e personagens: ' + str(APP_DIR)))
    choices=QComboBox(); layout.addWidget(choices)
    documents=[('Como usar',ROOT/'README.md'),('Créditos',ROOT/'THIRD_PARTY_NOTICES.txt'),('Licença do app',ROOT/'LICENSE')]
    licenses=ROOT/'third-party-licenses'
    documents.extend((str(path.relative_to(licenses)),path) for path in sorted(licenses.rglob('*')) if path.is_file())
    for name,path in documents: choices.addItem(name,str(path))
    browser=QTextBrowser(); browser.setOpenLinks(False); browser.setOpenExternalLinks(False); layout.addWidget(browser,1)
    def show_document(index):
        path=Path(choices.itemData(index))
        try:
            content=path.read_text(encoding='utf-8',errors='replace')
            if path.suffix=='.md': browser.setMarkdown(content)
            elif path.suffix=='.html': browser.setHtml(content)
            else: browser.setPlainText(content)
        except OSError: browser.setPlainText('Este documento não está disponível nesta cópia.')
    choices.currentIndexChanged.connect(show_document); show_document(0)
    close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.button(QDialogButtonBox.StandardButton.Close).setText('Fechar')
    close.rejected.connect(dialog.reject);layout.addWidget(close)
    dialog.exec();dialog.deleteLater()
