# Convertidor Multimedia (Chito version) · v2

App de escritorio para Windows que **descarga** audio/video de más de 1800 sitios y **convierte**
archivos entre 45 formatos de video, audio e imagen.

## Instalación

Ejecuta **`Instalar-ConvertidorMultimedia.exe`** (~12 MB). Es un asistente clásico:

1. **Bienvenida**
2. **Ubicación**: por defecto `%LOCALAPPDATA%\Programs\ConvertidorMultimedia`, con accesos directos opcionales en el Escritorio y en el menú Inicio.
3. **Componentes**: revisa qué tienes y descarga e instala sólo lo que falta. Después vuelve a revisar, hasta que no falte nada:
   | Componente | Si falta |
   |---|---|
   | Python 3.10+ | winget o instalador oficial de python.org (~26 MB) |
   | FFmpeg | build de yt-dlp/FFmpeg-Builds (~87 MB) |
   | Deno (motor JS para YouTube) | release oficial de Deno (~41 MB); también sirve Node.js |
   | La app | última versión de `main` desde este repositorio |
   | Librerías | entorno `venv` propio con `requirements.txt` |
4. **Listo**: se abre la app.

No necesita permisos de administrador. Se desinstala desde *Configuración › Aplicaciones*: sólo borra lo que instaló, nunca tus archivos.

## Actualizaciones automáticas

- **yt-dlp**: cada vez que abres la app, consulta PyPI y, si hay una versión nueva, la instala **antes de la primera descarga**, sin reiniciar. Mientras la app siga abierta, vuelve a comprobar cada 6 h.
- **La app**: si hay commits nuevos en `main`, aparece un aviso con el botón *Actualizar ahora*, que vuelve a abrir el instalador en modo actualización.
- Las dos opciones se pueden desactivar en *Ajustes*.

## Funciones

**Descargar** (yt-dlp)
- Puedes poner varios enlaces a la vez. Se descargan en cola y en paralelo, con progreso real y opción de cancelar.
- Top 15 sitios: YouTube, YouTube Music, TikTok, Instagram, Facebook, X/Twitter, Vimeo, SoundCloud, Twitch, Reddit, Dailymotion, Bandcamp, Bilibili, Pinterest y Mixcloud.
- Audio: MP3, M4A, AAC, OPUS, OGG, FLAC, WAV, ALAC u original.
- Video: MP4, MKV, WEBM, MOV o AVI, de 360p a 4K.
- Listas de reproducción, portada, metadatos, subtítulos y cookies del navegador.

**Convertir** (FFmpeg + Pillow)
| Tipo | Formatos de salida (15 c/u) |
|---|---|
| Video | MP4, MKV, AVI, MOV, WEBM, WMV, FLV, M4V, MPG, 3GP, TS, MTS, OGV, VOB, GIF |
| Audio | MP3, WAV, AAC, FLAC, OGG, M4A, WMA, OPUS, AIFF, ALAC, AC3, AMR, MP2, MKA, CAF |
| Imagen | JPG, PNG, WEBP, GIF, BMP, TIFF, ICO, HEIC, AVIF, PDF, TGA, JP2, PPM, PCX, ICNS |

También tiene arrastrar y soltar, recorte por tiempo, copia sin recodificar, redimensionado de imágenes y unión de imágenes en un PDF.

## Desarrollo

```bash
python -m pip install -r requirements.txt
```
```bash
python main.py
```
Para compilar el instalador (queda en `dist\`):
```bash
build_installer.bat
```

```
main.py                    punto de entrada
convertidor/               la app (formats, downloader, converter, jobs, updater, ui/)
installer/                 asistente de instalación (deps.py = lógica, instalador.py = interfaz)
legacy/                    versión 1 original
```
