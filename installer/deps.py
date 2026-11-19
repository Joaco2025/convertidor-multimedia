"""Lógica del instalador: detectar e instalar dependencias (sin interfaz).

Estructura instalada (por usuario, sin permisos de administrador):

    %LOCALAPPDATA%\\Programs\\ConvertidorMultimedia\\
        app\\           código descargado del repo de GitHub
        venv\\          entorno de Python con las librerías
        bin\\           ffmpeg/ffprobe (+dll) y deno, si hubo que descargarlos
        version.json   commit instalado
        setup.exe      este instalador (para actualizar / desinstalar)
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

APP_NAME = "Convertidor Multimedia"
REPO = "Joaco2025/convertidor-multimedia"
UA = "ConvertidorMultimedia-Installer"
DEFAULT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs",
                           "ConvertidorMultimedia")
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ConvertidorMultimedia"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

FFMPEG_URL = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip"
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"
PYTHON_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
MIN_PY = (3, 10)
IMPORT_CHECK = "import customtkinter, yt_dlp, PIL, pillow_heif, tkinterdnd2"


class Aborted(Exception):
    pass


class Ctx:
    """Canal de comunicación con la UI (thread-safe vía callbacks)."""

    def __init__(self, log=print, progress=lambda frac, text: None):
        self.log = log
        self.progress = progress
        self.cancelled = False

    def check(self):
        if self.cancelled:
            raise Aborted("Instalación cancelada")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def run(cmd: list[str], ctx: Ctx | None = None, timeout: int = 1800, cwd: str | None = None,
        on_line=None) -> tuple[int, str]:
    """Ejecuta un comando sin ventana, enviando la salida al registro línea por línea."""
    if ctx:
        ctx.log("> " + subprocess.list2cmdline(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", cwd=cwd, creationflags=NO_WINDOW)
    except OSError as exc:
        return -1, str(exc)
    lines: list[str] = []
    start = time.time()
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.rstrip()
        if not line:
            continue
        lines.append(line)
        if ctx:
            ctx.log(line)
            if ctx.cancelled:
                proc.kill()
                raise Aborted("Instalación cancelada")
        if on_line:
            on_line(line)
        if time.time() - start > timeout:
            proc.kill()
            return -1, "Tiempo de espera agotado"
    proc.wait()
    return proc.returncode, "\n".join(lines[-80:])


def quick(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)


def get_json(url: str, timeout: float = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def download(url: str, dest: str, ctx: Ctx, label: str) -> str:
    ctx.log(f"Descargando {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as fh:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last = 0.0
        while True:
            ctx.check()
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            now = time.time()
            if now - last > 0.15:
                last = now
                if total:
                    ctx.progress(done / total, f"{label}: {done / 1048576:.1f} de {total / 1048576:.1f} MB")
                else:
                    ctx.progress(None, f"{label}: {done / 1048576:.1f} MB")
    return dest


def _tmp(name: str) -> str:
    folder = os.path.join(tempfile.gettempdir(), "ConvertidorMultimedia-setup")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)


def _vt(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".")[:3] if p.isdigit())


def winget() -> str | None:
    w = shutil.which("winget")
    if w:
        return w
    cand = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "winget.exe")
    return cand if os.path.isfile(cand) else None


def bin_dir(root: str) -> str:
    return os.path.join(root, "bin")


def venv_python(root: str, windowed: bool = False) -> str:
    return os.path.join(root, "venv", "Scripts", "pythonw.exe" if windowed else "python.exe")


# ---------------------------------------------------------------------------
# 1. Python
# ---------------------------------------------------------------------------
def probe_python(exe: str) -> tuple[str, str] | None:
    code, out = quick([exe, "-c", "import sys, tkinter, venv; print(sys.version.split()[0]); print(sys.executable)"])
    if code != 0:
        return None
    lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    version, path = lines[0], lines[1]
    return (version, path) if _vt(version) >= MIN_PY else None


def _python_candidates() -> list[str]:
    cands: list[str] = []
    code, out = quick(["py", "-0p"])
    if code == 0:
        for line in out.splitlines():
            part = line.strip().split()
            if part and part[-1].lower().endswith("python.exe"):
                cands.append(part[-1])
    for name in ("python", "python3"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    local = os.environ.get("LOCALAPPDATA", "")
    cands += sorted(glob.glob(os.path.join(local, "Programs", "Python", "Python3*", "python.exe")), reverse=True)
    for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        if pf:
            cands += sorted(glob.glob(os.path.join(pf, "Python3*", "python.exe")), reverse=True)
    cands += sorted(glob.glob(r"C:\Python3*\python.exe"), reverse=True)
    seen, out_list = set(), []
    for c in cands:
        k = os.path.normcase(c)
        if k not in seen:
            seen.add(k)
            out_list.append(c)
    return out_list


def find_python(root: str) -> tuple[str, str] | None:
    """Devuelve (versión, ruta) del mejor Python ≥ 3.10 con tkinter."""
    vp = venv_python(root)
    if os.path.isfile(vp):
        info = probe_python(vp)
        if info:
            return info[0], vp
    best = None
    for c in _python_candidates():
        info = probe_python(c)
        if info and (best is None or _vt(info[0]) > _vt(best[0])):
            best = info
    return best


def install_python(root: str, ctx: Ctx) -> None:
    wg = winget()
    if wg:
        ctx.progress(None, "Instalando Python 3.12 con winget...")
        run([wg, "install", "-e", "--id", "Python.Python.3.12", "--scope", "user", "--silent",
             "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"], ctx)
        if find_python(root):
            return
        ctx.log("winget no dejó un Python utilizable; uso el instalador oficial.")
    exe = download(PYTHON_URL, _tmp("python-installer.exe"), ctx, "Python 3.12")
    ctx.progress(None, "Instalando Python 3.12 (puede tardar un minuto)...")
    code, out = run([exe, "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0",
                     "Include_launcher=0", "Include_doc=0", "SimpleInstall=1"], ctx)
    if code != 0:
        raise RuntimeError(f"El instalador de Python falló (código {code}).")


# ---------------------------------------------------------------------------
# 2. FFmpeg
# ---------------------------------------------------------------------------
def _find_exe(root: str, name: str) -> str | None:
    local = os.path.join(bin_dir(root), name + ".exe")
    if os.path.isfile(local):
        return local
    w = shutil.which(name)
    if w:
        return w
    link = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", name + ".exe")
    return link if os.path.isfile(link) else None


def find_ffmpeg(root: str) -> str | None:
    ff, fp = _find_exe(root, "ffmpeg"), _find_exe(root, "ffprobe")
    if not ff or not fp:
        return None
    code, out = quick([ff, "-hide_banner", "-version"])
    if code != 0:
        return None
    first = out.splitlines()[0] if out else "ffmpeg"
    return first.replace("ffmpeg version ", "").split(" Copyright")[0][:40]


def install_ffmpeg(root: str, ctx: Ctx) -> None:
    z = download(FFMPEG_URL, _tmp("ffmpeg.zip"), ctx, "FFmpeg")
    ctx.progress(None, "Descomprimiendo FFmpeg...")
    os.makedirs(bin_dir(root), exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        for m in zf.infolist():
            parts = m.filename.replace("\\", "/").split("/")
            if len(parts) >= 2 and parts[-2] == "bin" and parts[-1].lower().endswith((".exe", ".dll")):
                if parts[-1].lower() == "ffplay.exe":
                    continue
                with zf.open(m) as src, open(os.path.join(bin_dir(root), parts[-1]), "wb") as dst:
                    shutil.copyfileobj(src, dst)
    os.remove(z)


# ---------------------------------------------------------------------------
# 3. Motor de JavaScript (YouTube)
# ---------------------------------------------------------------------------
def find_js(root: str) -> str | None:
    for name in ("deno", "node", "bun"):
        exe = _find_exe(root, name)
        if exe:
            code, out = quick([exe, "--version"])
            if code == 0:
                import re
                m = re.search(r"(\d+\.\d+\.\d+)", out)
                return f"{name.capitalize()} {m.group(1) if m else ''}".strip()
    return None


def install_deno(root: str, ctx: Ctx) -> None:
    z = download(DENO_URL, _tmp("deno.zip"), ctx, "Deno")
    os.makedirs(bin_dir(root), exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        with zf.open("deno.exe") as src, open(os.path.join(bin_dir(root), "deno.exe"), "wb") as dst:
            shutil.copyfileobj(src, dst)
    os.remove(z)


# ---------------------------------------------------------------------------
# 4. La app (desde GitHub)
# ---------------------------------------------------------------------------
def installed_app(root: str) -> dict | None:
    try:
        with open(os.path.join(root, "version.json"), encoding="utf-8") as fh:
            info = json.load(fh)
    except (OSError, ValueError):
        return None
    return info if os.path.isfile(os.path.join(root, "app", "main.py")) else None


def latest_app() -> dict | None:
    try:
        data = get_json(f"https://api.github.com/repos/{REPO}/commits/main")
        return {"sha": data["sha"], "date": data["commit"]["committer"]["date"][:10],
                "message": data["commit"]["message"].splitlines()[0][:80]}
    except Exception:  # noqa: BLE001 - límite de la API o sin internet
        return None


def install_app(root: str, ctx: Ctx, latest: dict | None) -> None:
    ref = latest["sha"] if latest else "refs/heads/main"
    z = download(f"https://github.com/{REPO}/archive/{ref}.zip", _tmp("app.zip"), ctx, "App")
    ctx.progress(None, "Descomprimiendo la app...")
    staging = os.path.join(root, "app.new")
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(z) as zf:
        for m in zf.infolist():
            name = m.filename.split("/", 1)[1] if "/" in m.filename else ""
            if not name or m.is_dir():
                continue
            target = os.path.join(staging, *name.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(m) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    os.remove(z)
    if not os.path.isfile(os.path.join(staging, "main.py")):
        raise RuntimeError("El paquete descargado no contiene la app.")
    app = os.path.join(root, "app")
    old = os.path.join(root, "app.old")
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(app):
        os.replace(app, old)
    os.replace(staging, app)
    shutil.rmtree(old, ignore_errors=True)
    info = {"sha": latest["sha"] if latest else "main", "date": (latest or {}).get("date", ""),
            "installed_at": time.strftime("%Y-%m-%d %H:%M")}
    with open(os.path.join(root, "version.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)


# ---------------------------------------------------------------------------
# 5. Librerías de Python (venv)
# ---------------------------------------------------------------------------
def libs_ok(root: str) -> str | None:
    vp = venv_python(root)
    if not os.path.isfile(vp):
        return None
    code, _ = quick([vp, "-c", IMPORT_CHECK], timeout=60)
    if code != 0:
        return None
    code, out = quick([vp, "-c", "from importlib.metadata import version as v; print(v('yt-dlp'))"])
    return f"yt-dlp {out.strip()}" if code == 0 else "instaladas"


def install_libs(root: str, python: str, ctx: Ctx) -> None:
    vp = venv_python(root)
    if not os.path.isfile(vp) or not probe_python(vp):
        ctx.progress(None, "Creando entorno de Python...")
        shutil.rmtree(os.path.join(root, "venv"), ignore_errors=True)
        code, out = run([python, "-m", "venv", os.path.join(root, "venv")], ctx)
        if code != 0 or not os.path.isfile(vp):
            raise RuntimeError("No se pudo crear el entorno de Python (venv).")
    req = os.path.join(root, "app", "requirements.txt")
    count = {"n": 0}

    def on_line(line: str) -> None:
        if line.startswith(("Collecting", "Downloading", "Installing", "Successfully", "Requirement")):
            count["n"] += 1
            ctx.progress(None, "Librerías: " + line[:90])

    code, out = run([vp, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
                     "--no-input", "-r", req], ctx, on_line=on_line)
    if code != 0:
        last = next((l for l in reversed(out.splitlines()) if l.strip()), "error")
        raise RuntimeError(f"pip falló: {last[:160]}")


# ---------------------------------------------------------------------------
# Accesos directos, registro y desinstalación
# ---------------------------------------------------------------------------
def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _shortcut_paths() -> dict[str, str]:
    code, out = quick(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"])
    desktop = out.strip() if code == 0 and out.strip() else os.path.join(os.path.expanduser("~"), "Desktop")
    start = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    return {"desktop": os.path.join(desktop, f"{APP_NAME}.lnk"), "start": os.path.join(start, f"{APP_NAME}.lnk")}


def create_shortcuts(root: str, desktop: bool, start_menu: bool, ctx: Ctx) -> None:
    target = venv_python(root, windowed=True)
    main = os.path.join(root, "app", "main.py")
    icon = os.path.join(root, "app", "assets", "icon.ico")
    paths = _shortcut_paths()
    wanted = {"desktop": desktop, "start": start_menu}
    for key, path in paths.items():
        if not wanted[key]:
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        script = (
            f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(path)});"
            f"$s.TargetPath={_ps_quote(target)};$s.Arguments={_ps_quote(chr(34) + main + chr(34))};"
            f"$s.WorkingDirectory={_ps_quote(os.path.join(root, 'app'))};"
            f"$s.IconLocation={_ps_quote(icon)};$s.Description={_ps_quote(APP_NAME)};$s.Save()"
        )
        code, out = quick(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], 60)
        ctx.log(f"Acceso directo {path}: {'ok' if code == 0 else out}")


def register(root: str) -> None:
    import winreg
    setup = os.path.join(root, "setup.exe")
    size_kb = 0
    for dirpath, _d, files in os.walk(root):
        for f in files:
            try:
                size_kb += os.path.getsize(os.path.join(dirpath, f)) // 1024
            except OSError:
                pass
    info = installed_app(root) or {}
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        vals = {
            "DisplayName": APP_NAME, "DisplayVersion": f"2.x ({info.get('sha', '')[:7]})", "Publisher": "Chito",
            "InstallLocation": root, "DisplayIcon": os.path.join(root, "app", "assets", "icon.ico"),
            "UninstallString": f'"{setup}" --uninstall', "URLInfoAbout": f"https://github.com/{REPO}",
        }
        for name, val in vals.items():
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, min(size_kb, 0xFFFFFFFF))
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)


def registered_dir() -> str | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            return winreg.QueryValueEx(k, "InstallLocation")[0]
    except OSError:
        return None


def copy_self(root: str) -> None:
    if not getattr(sys, "frozen", False):
        return
    dst = os.path.join(root, "setup.exe")
    if os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(dst):
        shutil.copy2(sys.executable, dst)


def launch_app(root: str) -> None:
    subprocess.Popen([venv_python(root, windowed=True), os.path.join(root, "app", "main.py")],
                     cwd=os.path.join(root, "app"), close_fds=True)


def uninstall(root: str) -> None:
    import winreg
    for p in _shortcut_paths().values():
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    # Sólo borra lo que creó el instalador. setup.exe está en uso: un cmd aparte lo
    # elimina (y la carpeta, sólo si quedó vacía) cuando este proceso termina.
    for name in OWNED_ENTRIES:
        p = os.path.join(root, name)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif name != "setup.exe":
            _rm(p)
    setup = os.path.join(root, "setup.exe")
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 > nul & del /f /q "{setup}" & rmdir "{root}"', shell=True,
                     creationflags=NO_WINDOW, close_fds=True, cwd=os.path.dirname(root))


OWNED_ENTRIES = ("app", "app.new", "app.old", "venv", "bin", "version.json", "setup.exe")


def is_our_install(root: str) -> bool:
    return os.path.isfile(os.path.join(root, "version.json")) or os.path.isfile(os.path.join(root, "setup.exe"))


def safe_install_dir(path: str) -> str:
    """Si el usuario elige una carpeta con otras cosas, instala en una subcarpeta propia."""
    path = os.path.abspath(path)
    if os.path.isdir(path) and os.listdir(path) and not is_our_install(path):
        return os.path.join(path, "ConvertidorMultimedia")
    return path


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
