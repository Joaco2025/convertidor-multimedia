# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller ConvertidorMultimedia.spec --noconfirm   (o simplemente build.bat)
# Genera dist/ConvertidorMultimedia/ (carpeta portable). Se usa "onedir" porque
# FFmpeg pesa ~330 MB y en "onefile" se descomprimiría en cada arranque.
import os
import shutil
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [("assets", "assets")], [], []
for pkg in ("customtkinter", "tkinterdnd2", "pillow_heif", "yt_dlp", "yt_dlp_ejs"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception as exc:
        print(f"[spec] aviso: no se pudo recolectar {pkg}: {exc}")

# FFmpeg: primero ./bin, luego el PATH del sistema
for tool in ("ffmpeg", "ffprobe"):
    local = os.path.join("bin", tool + ".exe")
    path = local if os.path.isfile(local) else shutil.which(tool)
    if not path:
        raise SystemExit(f"No se encontró {tool}.exe: colócalo en ./bin o instálalo (winget install yt-dlp.FFmpeg)")
    binaries.append((path, "."))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "numpy", "pandas", "scipy", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="ConvertidorMultimedia",
    icon="assets/icon.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ConvertidorMultimedia", upx=False)
