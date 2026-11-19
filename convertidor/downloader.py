"""Motor de descargas basado en yt-dlp.

yt-dlp se importa recién en la primera descarga, después de que el
actualizador (updater.py) haya tenido la oportunidad de instalar la última versión.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from . import formats as F
from . import updater
from .jobs import Cancelled, JobContext
from .paths import FFMPEG, js_runtimes


@dataclass
class DownloadRequest:
    url: str
    dest: str
    kind: str = "audio"          # audio | video
    audio_format: str = "mp3"
    audio_bitrate: str = "192"
    video_format: str = "mp4"
    video_height: str = "1080"   # o "Mejor disponible"
    playlist: bool = False
    thumbnail: bool = True
    metadata: bool = True
    subtitles: bool = False
    cookies_browser: str = ""     # "", "firefox", "edge", "chrome", "brave"...


FRIENDLY_ERRORS = [
    ("Unsupported URL", "Sitio o enlace no soportado."),
    ("is not a valid URL", "El enlace no es válido."),
    ("Private video", "El video es privado."),
    ("Video unavailable", "El video no está disponible (borrado o bloqueado en tu región)."),
    ("Sign in to confirm your age", "Video con restricción de edad: activa 'Cookies del navegador'."),
    ("Sign in to confirm you", "YouTube pide iniciar sesión: activa 'Cookies del navegador'."),
    ("login required", "Este contenido requiere iniciar sesión: activa 'Cookies del navegador'."),
    ("rate-limit", "El sitio está limitando las descargas. Intenta más tarde o usa cookies."),
    ("HTTP Error 403", "Acceso denegado (403). Actualiza yt-dlp o usa cookies."),
    ("HTTP Error 404", "No encontrado (404)."),
    ("Requested format is not available", "Ese formato/calidad no está disponible para este video."),
    ("getaddrinfo failed", "Sin conexión a internet."),
    ("Failed to resolve", "Sin conexión a internet."),
    ("timed out", "Tiempo de espera agotado. Revisa tu conexión."),
    ("Could not copy", "No se pudieron leer las cookies del navegador. Ciérralo e intenta de nuevo, o usa Firefox."),
    ("ffmpeg not found", "No se encontró FFmpeg."),
    ("live event will begin", "La transmisión en vivo aún no empieza."),
]


def friendly(msg: str) -> str:
    clean = msg.replace("ERROR: ", "").strip()
    for needle, text in FRIENDLY_ERRORS:
        if needle.lower() in clean.lower():
            return text
    return clean[:300]


class _Logger:
    def __init__(self, log):
        self.log = log

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.log(f"[yt-dlp] WARNING: {msg}")

    def error(self, msg):
        self.log(f"[yt-dlp] {msg}")


def build_options(req: DownloadRequest) -> dict:
    name = "%(title).150B.%(ext)s"
    if req.playlist:
        name = "%(playlist_title,playlist_id|Lista)s/%(playlist_index&{} - |)s" + name
    opts: dict = {
        "outtmpl": os.path.join(req.dest, name),
        "windowsfilenames": True,
        "noplaylist": not req.playlist,
        "ignoreerrors": "only_download" if req.playlist else False,
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "overwrites": False,
        "concurrent_fragment_downloads": 4,
        "retries": 5,
        "fragment_retries": 5,
        "postprocessors": [],
    }
    if FFMPEG:
        opts["ffmpeg_location"] = os.path.dirname(FFMPEG)
    runtimes = js_runtimes()
    if runtimes:
        opts["js_runtimes"] = runtimes
    if req.cookies_browser:
        opts["cookiesfrombrowser"] = (req.cookies_browser,)

    pps = opts["postprocessors"]
    if req.kind == "audio":
        _label, codec, lossless = F.DOWNLOAD_AUDIO[req.audio_format]
        opts["format"] = "bestaudio/best"
        if codec:
            pp = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
            if not lossless:
                pp["preferredquality"] = req.audio_bitrate
            pps.append(pp)
        target = req.audio_format
    else:
        fmt = req.video_format
        h = None if not req.video_height.isdigit() else int(req.video_height)
        res = [f"res:{h}"] if h else ["res"]
        if fmt in ("mp4", "mov", "avi"):
            opts["format_sort"] = res + ["vcodec:h264", "acodec:m4a"]
        elif fmt == "webm":
            opts["format_sort"] = res + ["vcodec:vp9", "acodec:opus"]
        else:
            opts["format_sort"] = res
        hf = f"[height<={h}]" if h else ""
        opts["format"] = f"bv*{hf}+ba/b{hf}/bv*+ba/b"
        opts["merge_output_format"] = fmt
        pps.append({"key": "FFmpegVideoRemuxer", "preferedformat": fmt})
        target = fmt
        if req.subtitles and fmt in F.SUBS_EMBED_OK:
            opts["writesubtitles"] = True
            opts["subtitleslangs"] = ["es.*", "en.*"]
            pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

    if req.metadata:
        pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})
    if req.thumbnail and target in F.THUMB_EMBED_OK:
        opts["writethumbnail"] = True
        pps.insert(0, {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    return opts


def _wait_for_updater(ctx: JobContext) -> None:
    if updater.YTDLP_READY.is_set():
        return
    ctx.update(progress=None, message="Esperando la actualización de yt-dlp...")
    for _ in range(600):  # hasta 5 min; pip suele tardar < 30 s
        if updater.YTDLP_READY.wait(0.5):
            return
        ctx.check_cancel()


def run_download(req: DownloadRequest, ctx: JobContext, log) -> str:
    _wait_for_updater(ctx)
    import yt_dlp
    from yt_dlp.utils import DownloadCancelled

    os.makedirs(req.dest, exist_ok=True)
    state = {"file": "", "title": ""}

    def _set_title(info: dict) -> None:
        title = info.get("title") or ""
        idx, total = info.get("playlist_index"), info.get("n_entries") or info.get("playlist_count")
        if req.playlist and idx and total:
            ctx.update(subtitle=f"{info.get('playlist_title') or 'Lista'} · {idx}/{total}")
        if title and title != state["title"]:
            state["title"] = title
            ctx.update(title=title)

    def progress_hook(d: dict) -> None:
        if ctx.cancelled:
            raise DownloadCancelled()
        info = d.get("info_dict") or {}
        _set_title(info)
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            prog = (done / total) if total else None
            speed, eta = d.get("speed"), d.get("eta")
            parts = ["Descargando"]
            if total:
                parts.append(f"{done / 1048576:.1f}/{total / 1048576:.1f} MB")
            if speed:
                parts.append(f"{speed / 1048576:.1f} MB/s")
            if eta:
                parts.append(f"quedan {int(eta) // 60}:{int(eta) % 60:02d}")
            ctx.update(progress=min(prog, 1.0) if prog is not None else None, message=" · ".join(parts))
        elif d["status"] == "finished":
            state["file"] = d.get("filename") or state["file"]
            ctx.update(progress=None, message="Procesando con FFmpeg...")

    names = {
        "ExtractAudio": "Convirtiendo audio", "VideoRemuxer": "Ajustando contenedor",
        "Merger": "Uniendo video y audio", "EmbedThumbnail": "Incrustando portada",
        "Metadata": "Escribiendo metadatos", "EmbedSubtitle": "Incrustando subtítulos",
        "ThumbnailsConvertor": "Preparando portada", "MoveFiles": "Guardando archivo",
    }

    def pp_hook(d: dict) -> None:
        if d["status"] == "started":
            key = (d.get("postprocessor") or "").removeprefix("FFmpeg")
            ctx.update(progress=None, message=names.get(key, "Procesando") + "...")
        elif d["status"] == "finished":
            fp = (d.get("info_dict") or {}).get("filepath")
            if fp:
                state["file"] = fp

    opts = build_options(req)
    opts["progress_hooks"] = [progress_hook]
    opts["postprocessor_hooks"] = [pp_hook]
    opts["logger"] = _Logger(log)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            code = ydl.download([req.url])
    except DownloadCancelled:
        raise Cancelled()
    except yt_dlp.utils.DownloadError as exc:
        if ctx.cancelled:
            raise Cancelled()
        raise RuntimeError(friendly(str(exc))) from None
    if code and not state["file"]:
        raise RuntimeError("La descarga falló. Revisa el registro para más detalles.")
    if req.playlist:
        return os.path.dirname(state["file"]) if state["file"] else req.dest
    return state["file"] or req.dest


def ytdlp_version() -> str:
    return updater.ytdlp_installed()
