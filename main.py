"""Punto de entrada: python main.py"""
import ctypes
import os
import sys


def _dpi_aware() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    _dpi_aware()
    from convertidor.ui.app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    if os.name == "nt":
        # Identidad propia en la barra de tareas (icono separado del de Python)
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Chito.ConvertidorMultimedia")
        except Exception:  # noqa: BLE001
            pass
    sys.exit(main())
