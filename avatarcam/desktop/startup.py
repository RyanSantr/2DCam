"""Diagnostico de abertura com tamanho limitado, sem imagens ou audio."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def setup_logging(data_dir):
    directory = Path(data_dir) / 'logs'
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / 'studio.log', maxBytes=1024 * 1024, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger = logging.getLogger('avatarcam')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler


def report_failure(error, log_path=None):
    logging.getLogger('avatarcam').error('Falha do aplicativo', exc_info=(type(error), error, error.__traceback__))
    text = 'Não foi possível concluir a abertura do 2DCam.\n\n'
    text += 'Feche a versão anterior e tente novamente. Confira se há espaço disponível e permissão para salvar arquivos.\n\n'
    if log_path:
        text += 'Detalhes para suporte: ' + str(log_path) + '\n\n'
    text += str(error)[:600]
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, '2DCam Studio', text)
    except Exception:
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, '2DCam Studio', 0x10)


def launch():
    handler = None
    try:
        from avatarcam.core.settings import APP_DIR
        handler = setup_logging(APP_DIR)
        def hook(kind, error, trace):
            logging.getLogger('avatarcam').error('Erro em uma ação da interface', exc_info=(kind, error, trace))
            from PySide6.QtWidgets import QApplication
            window = QApplication.activeWindow()
            if window and hasattr(window, 'show_notice'):
                window.show_notice('Não foi possível concluir a ação. Os detalhes foram salvos para suporte.')
        sys.excepthook = hook
        logging.getLogger('avatarcam').info('Carregando a entrada do aplicativo.')
        from avatarcam.desktop.main import main
        logging.getLogger('avatarcam').info('Entrada do aplicativo carregada.')
        return main()
    except Exception as error:
        report_failure(error, Path(handler.baseFilename) if handler else None)
        return 1
    finally:
        if handler:
            logging.getLogger('avatarcam').removeHandler(handler)
            handler.close()
