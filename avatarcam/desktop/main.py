import os
import sys
import logging
from avatarcam.core.settings import APP_DIR
from avatarcam.desktop.instance import InstanceGuard


def main():
    os.environ.setdefault('MPLCONFIGDIR',str(APP_DIR/'cache/matplotlib'))
    logger = logging.getLogger('avatarcam')
    logger.info('Verificando a instância do aplicativo.')
    guard=InstanceGuard(APP_DIR)
    logger.info('Instância principal: %s', guard.primary)
    if not guard.primary:
        notified = guard.notify()
        logger.info('Recuperação dos controles: %s', notified)
        if notified: return 0
        from PySide6.QtWidgets import QApplication, QMessageBox
        app=QApplication(sys.argv)
        QMessageBox.information(None,'2DCam','O app já está aberto ou iniciando. Aguarde e tente novamente.')
        return 0
    from PySide6.QtWidgets import QApplication
    from avatarcam.desktop.webview import register_scheme
    register_scheme()
    app=QApplication(sys.argv)
    app.setApplicationName('2DCam Studio'); app.setOrganizationName('2DCam')
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel
        loading=QLabel('2DCam Studio\n\nPreparando o personagem…')
        loading.setWindowFlags(Qt.WindowType.SplashScreen)
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter); loading.resize(360,130)
        loading.setStyleSheet('background:#151b23;color:#e7edf4;font:16px Segoe UI;border:1px solid #394351;')
        loading.show(); app.processEvents()
        try:
            from avatarcam.desktop.window import StudioWindow
            window=StudioWindow(); window.show()
        finally:
            loading.close()
        if not guard.listen(window.restore_controls):
            window.show_notice('Abertura única ativa. A comunicação para restaurar controles não está disponível.')
        return app.exec()
    finally:
        guard.close()
