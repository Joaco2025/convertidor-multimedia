# Convertidor Multimedia (Chito version) · v2

App de escritorio para Windows que **descarga** audio/video de más de 1800 sitios y **convierte**
archivos entre 45 formatos de video, audio e imagen.

## Funciones

**Descargar** (yt-dlp)
- Varios enlaces a la vez (uno por línea) en cola, con descargas en paralelo, cancelación y progreso real (MB, velocidad, tiempo restante).
- Top 15 sitios: YouTube, YouTube Music, TikTok, Instagram, Facebook, X/Twitter, Vimeo, SoundCloud, Twitch, Reddit, Dailymotion, Bandcamp, Bilibili, Pinterest, Mixcloud.
- Audio: MP3, M4A, AAC, OPUS, OGG, FLAC, WAV, ALAC u original · bitrate 96–320 kbps.
- Video: MP4, MKV, WEBM, MOV, AVI · resolución de 360p a 4K.
- Listas de reproducción completas, portada incrustada, metadatos/capítulos, subtítulos, cookies del navegador (para contenido privado o con restricción de edad).

**Convertir** (FFmpeg + Pillow)
| Tipo | Formatos de salida (15 c/u) |
|---|---|
| Video | MP4, MKV, AVI, MOV, WEBM, WMV, FLV, M4V, MPG, 3GP, TS, MTS, OGV, VOB, GIF |
| Audio | MP3, WAV, AAC, FLAC, OGG, M4A, WMA, OPUS, AIFF, ALAC, AC3, AMR, MP2, MKA, CAF |
| Imagen | JPG, PNG, WEBP, GIF, BMP, TIFF, ICO, HEIC, AVIF, PDF, TGA, JP2, PPM, PCX, ICNS |

- Entrada: ~70 extensiones (incluye HEIC de iPhone, PSD, M2TS, RMVB, APE…). Video → audio también funciona.
- Arrastrar y soltar archivos/carpetas (o enlaces, que van a Descargar).
- Calidad, resolución, recorte por tiempo, canales, copia sin recodificar (instantánea), redimensionar imágenes, unir varias imágenes en un PDF.
- Tema claro/oscuro; la configuración y el registro se guardan en `%APPDATA%\ConvertidorMultimedia`.

## Ejecutar desde el código

```bash
python -m pip install -r requirements.txt
```
```bash
python main.py
```
Necesita `ffmpeg.exe` y `ffprobe.exe` en el PATH o en la carpeta `bin/` (`winget install yt-dlp.FFmpeg`).
Para YouTube, yt-dlp usa Deno o Node.js si están instalados.

## Compilar la versión portable

```bash
build.bat
```
Resultado: `dist\ConvertidorMultimedia\` (~430 MB, incluye FFmpeg). Comprime esa carpeta en un zip para compartirla.
`build.bat` actualiza yt-dlp antes de compilar: **vuelve a compilar cada cierto tiempo**, porque los sitios cambian y una versión vieja de yt-dlp deja de funcionar.

## Estructura

```
main.py                    punto de entrada
convertidor/
  formats.py               catálogo de sitios y formatos
  downloader.py            motor yt-dlp
  converter.py             motor FFmpeg / Pillow
  jobs.py                  cola de trabajos en hilos (sin tocar la UI)
  settings.py, paths.py    preferencias, rutas, búsqueda de FFmpeg
  ui/                      ventana, pestañas y componentes (CustomTkinter)
legacy/                    versión 1 original
```
