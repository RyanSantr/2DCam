from __future__ import annotations


class TrayController:
    """Icone de bandeja opcional. O app funciona mesmo se falhar."""

    def __init__(self, app) -> None:
        self.app = app
        self.icon = None

    def start(self) -> bool:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception as exc:
            self.app.log.warning("Tray indisponivel: %s", exc)
            return False

        image = Image.new("RGB", (64, 64), "#182235")
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill="#4f8cff")
        draw.rectangle((24, 20, 40, 44), fill="#ffffff")

        menu = pystray.Menu(
            pystray.MenuItem("Abrir controles", lambda _icon, _item: self.app.after(0, self.app.show_controls)),
            pystray.MenuItem("Mostrar/Ocultar OBS", lambda _icon, _item: self.app.after(0, self.app._toggle_obs_window)),
            pystray.MenuItem("Microfone on/off", lambda _icon, _item: self.app.after(0, self.app._toggle_microphone)),
            pystray.MenuItem("Sair", lambda _icon, _item: self.app.after(0, self.app.destroy)),
        )
        self.icon = pystray.Icon("AvatarCam2D", image, "AvatarCam 2D", menu)
        self.icon.run_detached()
        return True

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
