"""Rutas de recursos, FFmpeg y utilidades de sistema."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

APP_NAME = "Convertidor Multimedia"
APP_VERSION = "2.0.0"

# Evita que se abra una consola negra por cada proceso de FFmpeg en Windows
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_dir() -> str:
    """Carpeta de recursos: la interna del .exe o la raíz del proyecto."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def exe_dir() -> str:
    if is_frozen():
        return os.path.dirname(sys.executable)
    return resource_dir()


def _find_tool(name: str) -> str | None:
    exe = name + (".exe" if os.name == "nt" else "")
    # 1) junto al .exe / proyecto (permite actualizar ffmpeg sin recompilar)
    # 2) dentro del .exe empaquetado   3) carpeta bin/   4) PATH del sistema
    for folder in (exe_dir(), resource_dir(), os.path.join(exe_dir(), "bin"),
                   os.path.join(resource_dir(), "bin")):
        candidate = os.path.join(folder, exe)
        if os.path.isfile(candidate):
            return candidate
    return shutil.which(name)


FFMPEG = _find_tool("ffmpeg")
FFPROBE = _find_tool("ffprobe")


def js_runtimes() -> dict:
    """Runtimes de JavaScript para que yt-dlp resuelva los retos de YouTube."""
    found = {}
    for name in ("deno", "node", "bun"):
        path = shutil.which(name)
        if path:
            found[name] = {"path": path}
    return found


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    path = os.path.join(base, "ConvertidorMultimedia")
    os.makedirs(path, exist_ok=True)
    return path


def downloads_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Downloads")


def unique_path(path: str) -> str:
    """Devuelve una ruta que no exista agregando ' (1)', ' (2)', ..."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{root} ({i}){ext}"):
        i += 1
    return f"{root} ({i}){ext}"


def open_folder(path: str) -> None:
    """Abre la carpeta; si es un archivo, lo deja seleccionado en el Explorador."""
    if not path:
        return
    if os.name == "nt":
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            os.startfile(os.path.normpath(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R" if os.path.isfile(path) else "", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path) if os.path.isfile(path) else path])
