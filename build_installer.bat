@echo off
REM Compila el instalador liviano en dist\Instalar-ConvertidorMultimedia.exe
cd /d "%~dp0installer"
python -m pip install -q -r ..\requirements-build.txt || goto :error
python -m PyInstaller instalador.spec --noconfirm --clean --distpath ..\dist --workpath ..\build || goto :error
echo.
echo Listo: dist\Instalar-ConvertidorMultimedia.exe
goto :eof
:error
echo.
echo La compilacion fallo.
exit /b 1
