"""Catálogo de formatos y sitios soportados (top 15 de cada categoría)."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re

# ---------------------------------------------------------------------------
# Sitios de descarga (yt-dlp soporta >1800; estos son los 15 más usados)
# ---------------------------------------------------------------------------
SITES: list[tuple[str, str]] = [
    ("YouTube", r"(youtube\.com|youtu\.be)"),
    ("YouTube Music", r"music\.youtube\.com"),
    ("TikTok", r"tiktok\.com"),
    ("Instagram", r"instagram\.com"),
    ("Facebook", r"(facebook\.com|fb\.watch)"),
    ("X / Twitter", r"(twitter\.com|x\.com)"),
    ("Vimeo", r"vimeo\.com"),
    ("SoundCloud", r"soundcloud\.com"),
    ("Twitch", r"twitch\.tv"),
    ("Reddit", r"(reddit\.com|redd\.it)"),
    ("Dailymotion", r"(dailymotion\.com|dai\.ly)"),
    ("Bandcamp", r"bandcamp\.com"),
    ("Bilibili", r"(bilibili\.com|b23\.tv)"),
    ("Pinterest", r"(pinterest\.[a-z.]+|pin\.it)"),
    ("Mixcloud", r"mixcloud\.com"),
]
# YouTube Music debe evaluarse antes que YouTube
_SITE_ORDER = [SITES[1], SITES[0], *SITES[2:]]


def detect_site(url: str) -> str | None:
    for name, pattern in _SITE_ORDER:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return None


def looks_like_url(text: str) -> bool:
    return bool(re.match(r"^https?://\S+$", text.strip(), re.IGNORECASE))


# ---------------------------------------------------------------------------
# Formatos de salida de la descarga
# ---------------------------------------------------------------------------
# id -> (etiqueta, códec para FFmpegExtractAudio, ¿sin pérdida?)
DOWNLOAD_AUDIO = {
    "mp3": ("MP3", "mp3", False),
    "m4a": ("M4A (AAC)", "m4a", False),
    "aac": ("AAC", "aac", False),
    "opus": ("OPUS", "opus", False),
    "ogg": ("OGG (Vorbis)", "vorbis", False),
    "flac": ("FLAC (sin pérdida)", "flac", True),
    "wav": ("WAV (sin pérdida)", "wav", True),
    "alac": ("ALAC (sin pérdida)", "alac", True),
    "original": ("Original (sin convertir)", None, True),
}
DOWNLOAD_VIDEO = {
    "mp4": "MP4 (H.264, máxima compatibilidad)",
    "mkv": "MKV (mejor calidad disponible)",
    "webm": "WEBM (VP9/AV1)",
    "mov": "MOV (Apple)",
    "avi": "AVI",
}
AUDIO_BITRATES = ["320", "256", "192", "160", "128", "96"]
VIDEO_HEIGHTS = ["Mejor disponible", "2160", "1440", "1080", "720", "480", "360"]
# Formatos donde yt-dlp puede incrustar la portada
THUMB_EMBED_OK = {"mp3", "m4a", "opus", "ogg", "flac", "alac", "mp4", "mkv", "mov"}
SUBS_EMBED_OK = {"mp4", "mkv", "webm", "mov"}


# ---------------------------------------------------------------------------
# Formatos del convertidor de archivos
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OutFormat:
    id: str
    label: str
    ext: str
    category: str  # video | audio | image
    lossless: bool = False
    note: str = ""


def _f(cat, id, label, ext=None, lossless=False, note=""):
    return OutFormat(id, label, ext or id, cat, lossless, note)


VIDEO_OUT = [
    _f("video", "mp4", "MP4 (H.264)"),
    _f("video", "mkv", "MKV (H.264)"),
    _f("video", "avi", "AVI (MPEG-4)"),
    _f("video", "mov", "MOV (H.264)"),
    _f("video", "webm", "WEBM (VP9)"),
    _f("video", "wmv", "WMV (Windows Media)"),
    _f("video", "flv", "FLV (Flash)"),
    _f("video", "m4v", "M4V (Apple)"),
    _f("video", "mpg", "MPG (MPEG-2)"),
    _f("video", "3gp", "3GP (móvil)"),
    _f("video", "ts", "TS (MPEG-TS)"),
    _f("video", "mts", "MTS (AVCHD)"),
    _f("video", "ogv", "OGV (Theora)"),
    _f("video", "vob", "VOB (DVD)"),
    _f("video", "gif", "GIF animado"),
]
AUDIO_OUT = [
    _f("audio", "mp3", "MP3"),
    _f("audio", "wav", "WAV", lossless=True),
    _f("audio", "aac", "AAC"),
    _f("audio", "flac", "FLAC", lossless=True),
    _f("audio", "ogg", "OGG (Vorbis)"),
    _f("audio", "m4a", "M4A (AAC)"),
    _f("audio", "wma", "WMA"),
    _f("audio", "opus", "OPUS"),
    _f("audio", "aiff", "AIFF", lossless=True),
    _f("audio", "alac", "ALAC (Apple Lossless)", ext="m4a", lossless=True),
    _f("audio", "ac3", "AC3 (Dolby Digital)"),
    _f("audio", "amr", "AMR (voz)", note="Mono 8 kHz"),
    _f("audio", "mp2", "MP2"),
    _f("audio", "mka", "MKA (Matroska Audio)"),
    _f("audio", "caf", "CAF (Core Audio)", lossless=True),
]
IMAGE_OUT = [
    _f("image", "jpg", "JPG"),
    _f("image", "png", "PNG", lossless=True),
    _f("image", "webp", "WEBP"),
    _f("image", "gif", "GIF"),
    _f("image", "bmp", "BMP", lossless=True),
    _f("image", "tiff", "TIFF", lossless=True),
    _f("image", "ico", "ICO (icono Windows)"),
    _f("image", "heic", "HEIC (iPhone)"),
    _f("image", "avif", "AVIF"),
    _f("image", "pdf", "PDF"),
    _f("image", "tga", "TGA", lossless=True),
    _f("image", "jp2", "JPEG 2000"),
    _f("image", "ppm", "PPM", lossless=True),
    _f("image", "pcx", "PCX", lossless=True),
    _f("image", "icns", "ICNS (icono macOS)"),
]
OUT_FORMATS = {"video": VIDEO_OUT, "audio": AUDIO_OUT, "image": IMAGE_OUT}
CATEGORY_LABELS = {"video": "Video", "audio": "Audio", "image": "Imagen"}

# Extensiones de entrada reconocidas
VIDEO_IN = {
    "mp4", "mkv", "avi", "mov", "webm", "wmv", "flv", "m4v", "mpg", "mpeg", "3gp", "3g2",
    "ts", "mts", "m2ts", "ogv", "vob", "asf", "f4v", "divx", "mxf", "rm", "rmvb",
}
AUDIO_IN = {
    "mp3", "wav", "aac", "flac", "ogg", "oga", "m4a", "wma", "opus", "aiff", "aif", "ac3",
    "amr", "mp2", "mka", "caf", "ape", "wv", "dts", "au", "m4b", "weba",
}
IMAGE_IN = {
    "jpg", "jpeg", "jfif", "png", "webp", "gif", "bmp", "tif", "tiff", "ico", "heic", "heif",
    "avif", "tga", "jp2", "j2k", "ppm", "pgm", "pbm", "pcx", "icns", "psd", "dds", "dib",
}
# Imágenes animadas que FFmpeg también puede tratar como video
ANIMATED_IMAGE = {"gif", "webp", "apng"}


def ext_of(path: str) -> str:
    return os.path.splitext(path)[1].lower().lstrip(".")


def input_category(path: str) -> str | None:
    e = ext_of(path)
    if e in VIDEO_IN:
        return "video"
    if e in AUDIO_IN:
        return "audio"
    if e in IMAGE_IN:
        return "image"
    return None


def can_convert(path: str, out_category: str) -> bool:
    cat = input_category(path)
    if out_category == "video":
        return cat == "video" or ext_of(path) in ANIMATED_IMAGE
    if out_category == "audio":
        return cat in ("video", "audio")
    if out_category == "image":
        return cat == "image"
    return False


def all_input_patterns() -> list[tuple[str, str]]:
    def pat(exts):
        return " ".join(f"*.{e}" for e in sorted(exts))
    return [
        ("Todos los soportados", pat(VIDEO_IN | AUDIO_IN | IMAGE_IN)),
        ("Video", pat(VIDEO_IN)),
        ("Audio", pat(AUDIO_IN)),
        ("Imagen", pat(IMAGE_IN)),
        ("Todos los archivos", "*.*"),
    ]


def find_out_format(category: str, fmt_id: str) -> OutFormat:
    for f in OUT_FORMATS[category]:
        if f.id == fmt_id:
            return f
    raise KeyError(fmt_id)
