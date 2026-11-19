"""Actualizaciones automáticas: yt-dlp (PyPI) y la propia app (GitHub).

yt-dlp se importa de forma diferida (ver downloader.py). Al arrancar, la app
consulta PyPI y, si hay versión nueva, la instala con pip ANTES de la primera
descarga: las descargas esperan a que `YTDLP_READY` esté activo, así usan la
versión nueva sin reiniciar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.request
from importlib import metadata

from .paths import NO_WINDOW, install_root, is_frozen

REPO = "Joaco2025/convertidor-multimedia"
USER_AGENT = "ConvertidorMultimedia-Updater"

# Se activa cuando terminó la comprobación inicial (con o sin actualización)
YTDLP_READY = threading.Event()


def _get_json(url: str, timeout: float = 10) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _vtuple(v: str) -> tuple:
    out = []
    for part in v.replace("-", ".").split("."):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out)


# ---------------------------------------------------------------------------
# yt-dlp
# ---------------------------------------------------------------------------
def ytdlp_installed() -> str:
    try:
        return metadata.version("yt-dlp")
    except metadata.PackageNotFoundError:
        return "no instalado"


def ytdlp_latest() -> str:
    return _get_json("https://pypi.org/pypi/yt-dlp/json")["info"]["version"]


def ytdlp_loaded() -> bool:
    return "yt_dlp" in sys.modules


def can_self_update() -> bool:
    """Sólo si la app corre desde Python (instalación normal), no desde un .exe congelado."""
    return not is_frozen()


def _python_for_pip() -> str:
    exe = sys.executable
    # pythonw.exe -> python.exe (mismo entorno) para que pip se comporte normal
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.isfile(cand):
            return cand
    return exe


def ytdlp_upgrade(log) -> tuple[bool, str]:
    cmd = [_python_for_pip(), "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
           "yt-dlp[default]"]
    log("[update] " + " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode != 0:
        log(proc.stdout[-2000:] + proc.stderr[-2000:])
        return False, (proc.stderr.strip().splitlines() or ["pip falló"])[-1]
    return True, ytdlp_installed()


def check_ytdlp(auto_install: bool, log, notify) -> None:
    """Corre en un hilo. notify(kind, text) informa a la UI de forma thread-safe."""
    try:
        current = ytdlp_installed()
        try:
            latest = ytdlp_latest()
        except Exception as exc:  # noqa: BLE001 - sin internet: seguimos con lo instalado
            log(f"[update] No se pudo consultar PyPI: {exc}")
            notify("ytdlp", ("offline", current, ""))
            return
        if current != "no instalado" and _vtuple(current) >= _vtuple(latest):
            log(f"[update] yt-dlp al día ({current})")
            notify("ytdlp", ("ok", current, latest))
            return
        if not auto_install or not can_self_update():
            notify("ytdlp", ("available", current, latest))
            return
        if ytdlp_loaded():
            # Ya está en memoria: actualizar ahora podría romper la sesión; se hace al reiniciar
            notify("ytdlp", ("restart_needed", current, latest))
            return
        YTDLP_READY.clear()  # las descargas nuevas esperan a que pip termine
        notify("ytdlp", ("installing", current, latest))
        ok, info = ytdlp_upgrade(log)
        notify("ytdlp", ("updated", current, info) if ok else ("failed", current, info))
    finally:
        YTDLP_READY.set()


# ---------------------------------------------------------------------------
# App (repositorio de GitHub, instalada con el instalador)
# ---------------------------------------------------------------------------
def installed_app_info() -> dict | None:
    root = install_root()
    if not root:
        return None
    try:
        with open(os.path.join(root, "version.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def latest_app_sha() -> str:
    return _get_json(f"https://api.github.com/repos/{REPO}/commits/main")["sha"]


def check_app(log, notify) -> None:
    info = installed_app_info()
    if not info or not info.get("sha"):
        return  # no se instaló con el instalador (p. ej. corriendo desde el repo)
    try:
        sha = latest_app_sha()
    except Exception as exc:  # noqa: BLE001
        log(f"[update] No se pudo consultar GitHub: {exc}")
        return
    if sha != info["sha"]:
        log(f"[update] Nueva versión de la app: {info['sha'][:7]} → {sha[:7]}")
        notify("app", sha)


def launch_installer_update() -> bool:
    root = install_root()
    setup = os.path.join(root, "setup.exe") if root else ""
    if not setup or not os.path.isfile(setup):
        return False
    subprocess.Popen([setup, "--update", "--dir", root], close_fds=True)
    return True
