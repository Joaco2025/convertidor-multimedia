"""Motor de conversión: FFmpeg para audio/video y Pillow para imágenes."""
from __future__ import annotations

import os
import re
import subprocess
import threading
from dataclasses import dataclass, field

from . import formats as F
from .jobs import Cancelled, JobContext
from .paths import FFMPEG, FFPROBE, NO_WINDOW, unique_path


@dataclass
class ConvertOptions:
    category: str                    # video | audio | image
    fmt_id: str
    dest_dir: str | None = None      # None = misma carpeta que el original
    # video
    video_quality: str = "Media"     # Alta | Media | Baja
    video_height: str = "Original"
    video_copy: bool = False         # remux sin recodificar
    # audio
    audio_bitrate: str = "192"
    audio_channels: str = "Original"  # Original | Estéreo | Mono
    # recorte (hh:mm:ss o segundos), vacío = completo
    trim_start: str = ""
    trim_end: str = ""
    # imagen
    image_quality: int = 90
    image_max: str = "Original"      # lado mayor máximo en px
    pdf_merge: bool = True
    extra: dict = field(default_factory=dict)


def output_path(src: str, opts: ConvertOptions, fmt: F.OutFormat) -> str:
    folder = opts.dest_dir or os.path.dirname(src)
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    return unique_path(os.path.join(folder, f"{stem}.{fmt.ext}"))


# ---------------------------------------------------------------------------
# FFmpeg
# ---------------------------------------------------------------------------
def parse_time(text: str) -> float | None:
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError:
        raise ValueError(f"Tiempo inválido: '{text}'. Usa segundos o hh:mm:ss") from None
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return secs


def probe_duration(path: str) -> float | None:
    if not FFPROBE:
        return None
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW,
        ).stdout.strip()
        return float(out) if out and out != "N/A" else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def has_stream(path: str, kind: str) -> bool:
    if not FFPROBE:
        return True
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", kind, "-show_entries", "stream=index",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW,
    ).stdout.strip()
    return bool(out)


_CRF = {"Alta": 18, "Media": 23, "Baja": 28}
_VP9_CRF = {"Alta": 24, "Media": 32, "Baja": 40}
_QSCALE = {"Alta": 2, "Media": 4, "Baja": 7}
_THEORA = {"Alta": 9, "Media": 7, "Baja": 5}
_COPY_OK = {"mp4", "mkv", "mov", "m4v", "ts", "mts", "flv"}


def _h264(q: str, extra_profile: list[str] | None = None) -> list[str]:
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(_CRF[q]), "-pix_fmt", "yuv420p",
            *(extra_profile or [])]


def _aac(br="192") -> list[str]:
    return ["-c:a", "aac", "-b:a", f"{br}k"]


def video_args(fmt: str, o: ConvertOptions) -> list[str]:
    q = o.video_quality
    if o.video_copy and fmt in _COPY_OK:
        args = ["-map", "0:v?", "-map", "0:a?", "-c", "copy"]
        if fmt in ("mp4", "m4v", "mov"):
            args += ["-movflags", "+faststart"]
        if fmt == "m4v":
            args += ["-f", "mp4"]
        if fmt in ("ts", "mts"):
            args += ["-f", "mpegts"]
        return args

    vf = []
    if o.video_height.isdigit() and fmt != "gif":
        h = int(o.video_height)
        vf.append(f"scale=-2:'min({h},ih)'")
    args = ["-map", "0:v:0", "-map", "0:a:0?"]
    if fmt in ("mp4", "mov", "m4v"):
        args += _h264(q) + _aac() + ["-movflags", "+faststart"]
        if fmt == "m4v":
            args += ["-f", "mp4"]
    elif fmt == "mkv":
        args += _h264(q) + _aac()
    elif fmt == "flv":
        args += _h264(q) + _aac() + ["-ar", "44100"]
    elif fmt in ("ts", "mts"):
        args += _h264(q) + _aac() + ["-f", "mpegts"]
    elif fmt == "3gp":
        args += _h264(q, ["-profile:v", "baseline", "-level", "3.0"]) + ["-c:a", "aac", "-b:a", "96k", "-ac", "2"]
        if not o.video_height.isdigit():
            vf.append("scale=-2:'min(480,ih)'")
    elif fmt == "avi":
        args += ["-c:v", "mpeg4", "-vtag", "xvid", "-q:v", str(_QSCALE[q]), "-c:a", "libmp3lame", "-b:a", "192k"]
    elif fmt == "webm":
        args += ["-c:v", "libvpx-vp9", "-crf", str(_VP9_CRF[q]), "-b:v", "0", "-row-mt", "1",
                 "-deadline", "good", "-cpu-used", "4", "-c:a", "libopus", "-b:a", "128k"]
    elif fmt == "wmv":
        args += ["-c:v", "wmv2", "-q:v", str(_QSCALE[q]), "-c:a", "wmav2", "-b:a", "192k"]
    elif fmt in ("mpg", "vob"):
        # MPEG-2 sólo admite framerates estándar: forzamos 29.97 fps
        args += ["-c:v", "mpeg2video", "-q:v", str(_QSCALE[q]), "-r", "30000/1001", "-pix_fmt", "yuv420p"]
        args += (["-c:a", "ac3", "-b:a", "192k", "-f", "vob"] if fmt == "vob"
                 else ["-c:a", "mp2", "-b:a", "192k", "-f", "mpeg"])
    elif fmt == "ogv":
        args += ["-c:v", "libtheora", "-q:v", str(_THEORA[q]), "-c:a", "libvorbis", "-q:a", "5"]
    elif fmt == "gif":
        width = int(o.video_height) * 16 // 9 if o.video_height.isdigit() else 480
        width = min(width, 800)
        fps = {"Alta": 15, "Media": 12, "Baja": 10}[q]
        return ["-map", "0:v:0", "-an", "-vf",
                f"fps={fps},scale='min({width},iw)':-2:flags=lanczos,split[a][b];"
                f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
                "-loop", "0"]
    else:
        raise ValueError(f"Formato de video no soportado: {fmt}")
    vf = [v for v in vf if v]
    if vf:
        args += ["-vf", ",".join(vf)]
    return args


def audio_args(fmt: F.OutFormat, o: ConvertOptions) -> list[str]:
    br = f"{o.audio_bitrate}k"
    codec = {
        "mp3": ["-c:a", "libmp3lame", "-b:a", br],
        "wav": ["-c:a", "pcm_s16le"],
        "aac": ["-c:a", "aac", "-b:a", br, "-f", "adts"],
        "flac": ["-c:a", "flac", "-compression_level", "8"],
        "ogg": ["-c:a", "libvorbis", "-b:a", br],
        "m4a": ["-c:a", "aac", "-b:a", br, "-movflags", "+faststart"],
        "wma": ["-c:a", "wmav2", "-b:a", br],
        "opus": ["-c:a", "libopus", "-b:a", br],
        "aiff": ["-c:a", "pcm_s16be"],
        "alac": ["-c:a", "alac"],
        "ac3": ["-c:a", "ac3", "-b:a", br if int(o.audio_bitrate) >= 192 else "192k"],
        "amr": ["-c:a", "libopencore_amrnb", "-ar", "8000", "-ac", "1", "-b:a", "12.2k"],
        "mp2": ["-c:a", "mp2", "-b:a", br],
        "mka": ["-c:a", "libopus", "-b:a", br],
        "caf": ["-c:a", "alac"],
    }[fmt.id]
    args = ["-map", "0:a:0", "-vn", "-map_metadata", "0"] + codec
    if fmt.id != "amr":
        if o.audio_channels == "Mono":
            args += ["-ac", "1"]
        elif o.audio_channels == "Estéreo":
            args += ["-ac", "2"]
    if fmt.id == "opus":
        args += ["-ar", "48000"]
    return args


_ERR_HINTS = [
    ("does not contain any stream", "El archivo no tiene una pista compatible con el formato elegido."),
    ("matches no streams", "El archivo no tiene pista de audio/video para convertir."),
    ("Invalid data found", "El archivo está dañado o no es un formato multimedia válido."),
    ("No such file", "No se encontró el archivo de entrada."),
    ("Permission denied", "Sin permiso para escribir en la carpeta de destino."),
    ("could not find tag for codec", "Ese contenedor no admite estos códecs: desactiva 'Copiar sin recodificar'."),
    ("not supported by the", "Ese contenedor no admite estos códecs: desactiva 'Copiar sin recodificar'."),
]


def run_ffmpeg(src: str, dst: str, args: list[str], o: ConvertOptions, ctx: JobContext, log) -> None:
    if not FFMPEG:
        raise RuntimeError("No se encontró FFmpeg. Colócalo junto a la app o instálalo.")
    start, end = parse_time(o.trim_start), parse_time(o.trim_end)
    duration = probe_duration(src)
    if duration is not None:
        if end is not None:
            duration = min(duration, end)
        if start is not None:
            duration = max(duration - start, 0.01)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-to", str(end)]
    cmd += ["-i", src, *args, "-progress", "pipe:1", "-nostats", dst]
    log("[ffmpeg] " + subprocess.list2cmdline(cmd))

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    tail: list[str] = []

    def _drain_err():
        for line in proc.stderr:  # type: ignore[union-attr]
            tail.append(line.rstrip())
            del tail[:-40]
    t = threading.Thread(target=_drain_err, daemon=True)
    t.start()

    speed = ""
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            if ctx.cancelled:
                proc.kill()
                break
            key, _, val = line.strip().partition("=")
            if key == "out_time_us" and val.isdigit() and duration:
                secs = int(val) / 1_000_000
                ctx.update(progress=min(secs / duration, 1.0),
                           message=f"Convirtiendo {int(secs)//60}:{int(secs)%60:02d} / "
                                   f"{int(duration)//60}:{int(duration)%60:02d} {speed}")
            elif key == "speed" and val not in ("N/A", ""):
                speed = f"· {val}"
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
        t.join(timeout=2)
    if ctx.cancelled:
        _safe_remove(dst)
        raise Cancelled()
    if proc.returncode != 0:
        _safe_remove(dst)
        log("[ffmpeg] " + "\n".join(tail))
        text = "\n".join(tail)
        for needle, hint in _ERR_HINTS:
            if needle.lower() in text.lower():
                raise RuntimeError(hint)
        last = next((l for l in reversed(tail) if l.strip()), "error desconocido")
        raise RuntimeError(f"FFmpeg falló: {last[:200]}")


def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Imágenes (Pillow)
# ---------------------------------------------------------------------------
def _pil():
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return Image, ImageOps


_NEEDS_RGB = {"jpg", "pdf", "ppm", "pcx", "jp2"}
_ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
_PIL_FORMAT = {"jpg": "JPEG", "tiff": "TIFF", "jp2": "JPEG2000", "tga": "TGA", "pcx": "PCX",
               "ppm": "PPM", "bmp": "BMP", "png": "PNG", "webp": "WEBP", "gif": "GIF", "ico": "ICO",
               "heic": "HEIF", "avif": "AVIF", "pdf": "PDF", "icns": "ICNS"}


def _flatten(img, bg=(255, 255, 255)):
    Image, _ = _pil()
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, bg)
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    return img.convert("RGB")


def _square(img, size=None):
    Image, _ = _pil()
    img = img.convert("RGBA")
    side = size or max(img.size)
    img.thumbnail((side, side), Image.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas


def _prepare(img, fmt: str, o: ConvertOptions):
    Image, ImageOps = _pil()
    img = ImageOps.exif_transpose(img)
    if o.image_max.isdigit():
        m = int(o.image_max)
        if max(img.size) > m:
            img.thumbnail((m, m), Image.LANCZOS)
    if fmt in _NEEDS_RGB:
        return _flatten(img)
    if fmt in ("ico",):
        return _square(img, 256)
    if fmt == "icns":
        return _square(img, 1024 if max(img.size) >= 1024 else 512)
    if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    if fmt == "bmp" and img.mode == "LA":
        img = img.convert("RGBA")
    return img


def _save_kwargs(fmt: str, o: ConvertOptions, img) -> dict:
    q = int(o.image_quality)
    kw: dict = {}
    if fmt == "jpg":
        kw = {"quality": q, "optimize": True, "progressive": True, "subsampling": 0 if q >= 90 else 2}
    elif fmt in ("webp", "heic", "avif"):
        kw = {"quality": q}
    elif fmt == "png":
        kw = {"optimize": True}
    elif fmt == "tiff":
        kw = {"compression": "tiff_lzw"}
    elif fmt == "ico":
        kw = {"sizes": _ICO_SIZES}
    elif fmt == "jp2":
        kw = {"quality_mode": "rates", "quality_layers": [max(1, (100 - q) // 2 + 1)]}
    elif fmt == "pdf":
        kw = {"resolution": 150.0}
    exif = img.info.get("exif")
    if exif and fmt in ("jpg", "webp", "png", "tiff", "heic", "avif"):
        kw["exif"] = exif
    return kw


def convert_image(src: str, dst: str, fmt: str, o: ConvertOptions) -> None:
    Image, _ = _pil()
    try:
        im = Image.open(src)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"No se pudo abrir la imagen: {exc}") from None
    with im:
        animated = getattr(im, "is_animated", False) and fmt in ("gif", "webp", "png", "avif")
        if animated:
            frames, durations = [], []
            for i in range(im.n_frames):
                im.seek(i)
                frames.append(_prepare(im.copy().convert("RGBA"), fmt, o))
                durations.append(im.info.get("duration", 100))
            kw = _save_kwargs(fmt, o, im)
            kw.pop("exif", None)
            frames[0].save(dst, format=_PIL_FORMAT[fmt], save_all=True, append_images=frames[1:],
                           duration=durations, loop=im.info.get("loop", 0),
                           **({"disposal": 2} if fmt == "gif" else {}), **kw)
            return
        out = _prepare(im.copy(), fmt, o)
        out.save(dst, format=_PIL_FORMAT[fmt], **_save_kwargs(fmt, o, im))


def images_to_pdf(srcs: list[str], dst: str, o: ConvertOptions, ctx: JobContext) -> None:
    Image, _ = _pil()
    pages = []
    for i, s in enumerate(srcs):
        ctx.check_cancel()
        with Image.open(s) as im:
            pages.append(_prepare(im.copy(), "pdf", o))
        ctx.update(progress=(i + 1) / (len(srcs) + 1), message=f"Página {i + 1}/{len(srcs)}")
    pages[0].save(dst, format="PDF", save_all=True, append_images=pages[1:], resolution=150.0)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def convert_file(src: str, o: ConvertOptions, ctx: JobContext, log) -> str:
    fmt = F.find_out_format(o.category, o.fmt_id)
    if not os.path.isfile(src):
        raise RuntimeError("El archivo ya no existe.")
    if not F.can_convert(src, o.category):
        raise RuntimeError(f"No se puede convertir .{F.ext_of(src)} a {fmt.label}.")
    dst = output_path(src, o, fmt)
    if o.category == "image":
        ctx.update(progress=None, message=f"Convirtiendo a {fmt.label}...")
        try:
            convert_image(src, dst, fmt.id, o)
        except Exception:
            _safe_remove(dst)
            raise
    elif o.category == "audio":
        if not has_stream(src, "a"):
            raise RuntimeError("El archivo no tiene pista de audio.")
        run_ffmpeg(src, dst, audio_args(fmt, o), o, ctx, log)
    else:
        if not has_stream(src, "v"):
            raise RuntimeError("El archivo no tiene pista de video.")
        run_ffmpeg(src, dst, video_args(fmt.id, o), o, ctx, log)
    return dst


def merge_images_pdf(srcs: list[str], o: ConvertOptions, ctx: JobContext) -> str:
    first = srcs[0]
    folder = o.dest_dir or os.path.dirname(first)
    stem = os.path.splitext(os.path.basename(first))[0]
    dst = unique_path(os.path.join(folder, f"{stem} (+{len(srcs) - 1}).pdf" if len(srcs) > 1 else f"{stem}.pdf"))
    images_to_pdf(srcs, dst, o, ctx)
    return dst
