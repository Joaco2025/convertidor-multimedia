# -*- mode: python ; coding: utf-8 -*-
# Instalador liviano (~15 MB): NO incluye la app ni FFmpeg; los descarga al instalar.
# Build: build_installer.bat  ->  dist\Instalar-ConvertidorMultimedia.exe
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [("icon.ico", ".")], [], []
d, b, h = collect_all("customtkinter")
datas += d; binaries += b; hiddenimports += h

a = Analysis(
    ["instalador.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["deps"],
    excludes=["PIL", "yt_dlp", "numpy", "pillow_heif", "tkinterdnd2", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Instalar-ConvertidorMultimedia",
    icon="icon.ico",
    console=False,
    upx=False,
)
