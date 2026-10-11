"""Renderizador incorporado; nao abre navegador nem servidor HTTP."""
from pathlib import Path
import json
import os
from PySide6.QtCore import QObject, Slot, QUrl, QFile, QIODevice, Qt
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (QWebEngineUrlScheme, QWebEngineUrlSchemeHandler,
    QWebEngineUrlRequestJob, QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
    QWebEngineUrlRequestInterceptor)
from PySide6.QtWebEngineWidgets import QWebEngineView

WEB = Path(__file__).resolve().parents[1] / 'web3d'


def register_scheme():
    # A saída de live precisa continuar quando o OBS cobre a janela.
    # Pausa/minimização e limites de FPS continuam sob controle do app.
    flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
    if '--disable-backgrounding-occluded-windows' not in flags.split():
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (flags + ' --disable-backgrounding-occluded-windows').strip()
    scheme = QWebEngineUrlScheme(b'avatarcam')
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.HostAndPort)
    scheme.setDefaultPort(443)
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme | QWebEngineUrlScheme.Flag.CorsEnabled
                    | QWebEngineUrlScheme.Flag.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)


class LocalOnly(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        info.block(info.requestUrl().scheme() not in ('avatarcam', 'qrc', 'data', 'blob'))


class Assets(QWebEngineUrlSchemeHandler):
    def __init__(self, controller, parent):
        super().__init__(parent); self.controller = controller

    def requestStarted(self, job):
        path = job.requestUrl().path().lstrip('/')
        if job.requestUrl().host() != 'app' or job.requestMethod() != b'GET':
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied); return
        if path in ('embedded.html', 'viewer.js', 'style.css', 'live2d.html', 'live2d.js'):
            target = WEB / path
        elif path == 'cubism-core.js':
            from avatarcam.desktop.live2d import core_path
            target = core_path()
        elif path.startswith('live2d/') and self.controller.mode == 'Live2D':
            from urllib.parse import unquote
            from avatarcam.desktop.live2d import local_resource
            try: target = local_resource(Path(self.controller.model_path).parent, unquote(path[len('live2d/'):]))
            except ValueError:
                job.fail(QWebEngineUrlRequestJob.Error.RequestDenied); return
        elif path.startswith('model/') and path == self.controller.model_route():
            target = Path(self.controller.model_path)
        else:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound); return
        stream = QFile(str(target), job)
        if not stream.open(QIODevice.OpenModeFlag.ReadOnly):
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound); return
        mime = {'.html': b'text/html', '.js': b'application/javascript', '.css': b'text/css'}.get(target.suffix, b'application/octet-stream')
        job.reply(mime, stream)


class Bridge(QObject):
    def __init__(self, controller, parent):
        super().__init__(parent); self.controller = controller

    @Slot(result=str)
    def state(self):
        return json.dumps(self.controller.snapshot())

    @Slot(str, str, result=bool)
    def command(self, action, value):
        try:
            return self.controller.command(action, json.loads(value))
        except (ValueError, TypeError):
            return False

    @Slot(str)
    def report(self, report):
        try: self.controller.renderer_report = json.loads(report)
        except ValueError: pass


class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.console_errors.append(message)
            self.console_errors=self.console_errors[-32:]

    def acceptNavigationRequest(self, url, navigation_type, is_main):
        return url.scheme() in ('avatarcam', 'qrc', 'data', 'blob', 'about')


class EmbeddedAvatar(QWebEngineView):
    def __init__(self, controller, capture=False, parent=None):
        super().__init__(parent)
        self.kind = controller.mode
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_output_menu)
        self.profile = QWebEngineProfile(self)
        self.assets = Assets(controller, self.profile)
        self.filter = LocalOnly(self.profile)
        self.profile.installUrlSchemeHandler(b'avatarcam', self.assets)
        self.profile.setUrlRequestInterceptor(self.filter)
        page = Page(self.profile, self); page.console_errors = []
        page.setBackgroundColor(QColor('#00ff00' if capture else '#111b2a'))
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        self.setPage(page)
        self.bridge = Bridge(controller, page)
        self.channel = QWebChannel(page)
        self.channel.registerObject('studio', self.bridge)
        page.setWebChannel(self.channel)
        self.released=False
        document = 'live2d.html' if self.kind == 'Live2D' else 'embedded.html'
        self.load(QUrl('avatarcam://app/'+document+'?embedded=1'+('&capture=1' if capture else '')))

    def show_output_menu(self, position):
        window=self.window()
        menu=getattr(window,'menu',None)
        if callable(menu): menu(window.mapFromGlobal(self.mapToGlobal(position)))

    def release(self):
        if self.released: return
        self.released=True
        # Destruir a pagina e o perfil libera geometria, texturas e processo de conteudo.
        self.stop(); self.page().setWebChannel(None)
        self.page().deleteLater(); self.deleteLater()
