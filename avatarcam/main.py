from avatarcam.ui.app_window import AvatarCamApp


def _enable_windows_dpi_awareness() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main() -> None:
    _enable_windows_dpi_awareness()
    app = AvatarCamApp()
    app.mainloop()
