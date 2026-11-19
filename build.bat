@echo off
REM Compila la app en dist\ConvertidorMultimedia\  (actualiza yt-dlp antes de compilar)
cd /d "%~dp0"
python -m pip install -U -r requirements.txt || goto :error
python tools\make_icon.py || goto :error
python -m PyInstaller ConvertidorMultimedia.spec --noconfirm --clean || goto :error
echo.
echo Listo: dist\ConvertidorMultimedia\ConvertidorMultimedia.exe
goto :eof
:error
echo.
echo La compilacion fallo.
exit /b 1
