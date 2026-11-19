"""Pestaña de descargas."""
from __future__ import annotations

from collections import Counter
from tkinter import filedialog

import customtkinter as ctk

from .. import formats as F
from ..downloader import DownloadRequest, run_download
from ..jobs import Job
from ..paths import open_folder
from .widgets import ACCENT, ACCENT_HOVER, BAD, MUTED, OK, JobList, Section, font, labeled

COOKIE_BROWSERS = {"Ninguno": "", "Firefox": "firefox", "Edge": "edge", "Chrome": "chrome",
                   "Brave": "brave", "Opera": "opera"}


class DownloadTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        s = app.settings
        self.grid_columnconfigure(0, weight=0, minsize=440)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent", width=430)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)

        # --- Enlaces ---
        sec = Section(left, "1. Enlaces (uno por línea)")
        sec.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.urls = ctk.CTkTextbox(sec.body, height=110, font=font(12), wrap="none")
        self.urls.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.urls.bind("<KeyRelease>", lambda _e: self._update_detected())
        self.urls.bind("<<Paste>>", lambda _e: self.after(10, self._update_detected))
        btns = ctk.CTkFrame(sec.body, fg_color="transparent")
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ctk.CTkButton(btns, text="📋 Pegar", width=90, height=28, command=self.paste).pack(side="left")
        ctk.CTkButton(btns, text="Limpiar", width=80, height=28, fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=self.clear).pack(side="left", padx=6)
        self.detected = ctk.CTkLabel(btns, text="", font=font(11), text_color=MUTED, anchor="e")
        self.detected.pack(side="right")

        # --- Formato ---
        sec = Section(left, "2. Formato de salida")
        sec.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        b = sec.body
        self.kind = ctk.CTkSegmentedButton(b, values=["🎵 Audio", "🎬 Video"], command=self._on_kind)
        self.kind.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.fmt = ctk.CTkOptionMenu(b, values=["-"], command=lambda _v: self._sync_options())
        labeled(b, 1, "Formato", self.fmt)
        self.quality = ctk.CTkOptionMenu(b, values=["-"])
        self.quality_lbl = ctk.CTkLabel(b, text="Calidad", font=font(12), text_color=MUTED, anchor="w")
        self.quality_lbl.grid(row=2, column=0, sticky="w", padx=(0, 10), pady=4)
        self.quality.grid(row=2, column=1, sticky="ew", pady=4)

        self.chk_playlist = ctk.CTkCheckBox(b, text="Descargar la lista de reproducción completa")
        self.chk_thumb = ctk.CTkCheckBox(b, text="Incrustar portada / miniatura")
        self.chk_meta = ctk.CTkCheckBox(b, text="Guardar metadatos (título, artista, capítulos)")
        self.chk_subs = ctk.CTkCheckBox(b, text="Incrustar subtítulos (español / inglés)")
        for i, w in enumerate((self.chk_playlist, self.chk_thumb, self.chk_meta, self.chk_subs)):
            w.grid(row=3 + i, column=0, columnspan=2, sticky="w", pady=3)

        # --- Destino ---
        sec = Section(left, "3. Destino y acceso")
        sec.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        b = sec.body
        self.dest_var = ctk.StringVar(value=s["download_dir"])
        dest_row = ctk.CTkFrame(b, fg_color="transparent")
        dest_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(dest_row, textvariable=self.dest_var, state="readonly").grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dest_row, text="Cambiar", width=70, command=self.pick_dest).grid(row=0, column=1, padx=(6, 0))
        ctk.CTkButton(dest_row, text="📂", width=34, command=lambda: open_folder(self.dest_var.get())).grid(
            row=0, column=2, padx=(6, 0))
        labeled(b, 0, "Carpeta", dest_row)
        self.cookies = ctk.CTkOptionMenu(b, values=list(COOKIE_BROWSERS))
        labeled(b, 1, "Cookies de", self.cookies)
        ctk.CTkLabel(b, text="Úsalo para videos privados, con restricción de edad o de Instagram/Facebook.\n"
                            "Firefox es el más fiable; Chrome/Edge deben estar cerrados.",
                     font=font(11), text_color=MUTED, justify="left", anchor="w").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.go = ctk.CTkButton(left, text="⬇  Descargar", height=44, font=font(15, "bold"),
                                fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.start)
        self.go.grid(row=3, column=0, sticky="ew", pady=(4, 6))
        sites = ", ".join(n for n, _ in F.SITES)
        ctk.CTkLabel(left, text=f"Compatible con {sites} y más de 1800 sitios.", font=font(11),
                     text_color=MUTED, wraplength=410, justify="left").grid(row=4, column=0, sticky="w")

        self.jobs = JobList(self, "Descargas")
        self.jobs.grid(row=0, column=1, sticky="nsew")

        # Estado inicial desde la configuración
        self.kind.set("🎬 Video" if s["dl_kind"] == "video" else "🎵 Audio")
        self._on_kind(self.kind.get(), init=True)
        for chk, key in ((self.chk_playlist, "dl_playlist"), (self.chk_thumb, "dl_thumbnail"),
                         (self.chk_meta, "dl_metadata"), (self.chk_subs, "dl_subtitles")):
            chk.select() if s[key] else chk.deselect()
        self.cookies.set(s["dl_cookies"] if s["dl_cookies"] in COOKIE_BROWSERS else "Ninguno")

    # ------------------------------------------------------------------
    @property
    def is_video(self) -> bool:
        return "Video" in self.kind.get()

    def _on_kind(self, _value, init=False) -> None:
        s = self.app.settings
        if self.is_video:
            labels = list(F.DOWNLOAD_VIDEO.values())
            self._fmt_ids = list(F.DOWNLOAD_VIDEO)
            current = s["dl_video_format"]
            self.quality_lbl.configure(text="Resolución")
            qvals = [v if not v.isdigit() else f"{v}p" for v in F.VIDEO_HEIGHTS]
            self.quality.configure(values=qvals)
            h = s["dl_video_height"]
            self.quality.set(f"{h}p" if h.isdigit() else F.VIDEO_HEIGHTS[0])
        else:
            labels = [v[0] for v in F.DOWNLOAD_AUDIO.values()]
            self._fmt_ids = list(F.DOWNLOAD_AUDIO)
            current = s["dl_audio_format"]
            self.quality_lbl.configure(text="Bitrate")
            self.quality.configure(values=[f"{b} kbps" for b in F.AUDIO_BITRATES])
            self.quality.set(f"{s['dl_audio_bitrate']} kbps")
        self._fmt_labels = labels
        self.fmt.configure(values=labels)
        idx = self._fmt_ids.index(current) if current in self._fmt_ids else 0
        self.fmt.set(labels[idx])
        self._sync_options()

    def _fmt_id(self) -> str:
        return self._fmt_ids[self._fmt_labels.index(self.fmt.get())]

    def _sync_options(self) -> None:
        fid = self._fmt_id()
        lossless = (not self.is_video) and F.DOWNLOAD_AUDIO[fid][2]
        self.quality.configure(state="disabled" if lossless else "normal")
        self.chk_subs.configure(state="normal" if self.is_video and fid in F.SUBS_EMBED_OK else "disabled")
        self.chk_thumb.configure(state="normal" if fid in F.THUMB_EMBED_OK else "disabled")

    def _lines(self) -> list[str]:
        raw = self.urls.get("1.0", "end").split()
        seen, out = set(), []
        for u in raw:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _update_detected(self) -> None:
        lines = self._lines()
        if not lines:
            self.detected.configure(text="")
            return
        bad = [u for u in lines if not F.looks_like_url(u)]
        sites = Counter(F.detect_site(u) or "Otro sitio" for u in lines if F.looks_like_url(u))
        text = " · ".join(f"{k} ×{v}" if v > 1 else k for k, v in sites.items())
        if bad:
            text += f"  ⚠ {len(bad)} no válido(s)"
        self.detected.configure(text=text, text_color=BAD if bad else OK)

    def paste(self) -> None:
        try:
            text = self.clipboard_get()
        except Exception:  # noqa: BLE001
            return
        self.add_urls(text)

    def add_urls(self, text: str) -> None:
        current = self.urls.get("1.0", "end").strip()
        new = "\n".join(t for t in text.split() if t)
        self.urls.delete("1.0", "end")
        self.urls.insert("1.0", (current + "\n" + new).strip() + "\n")
        self._update_detected()

    def clear(self) -> None:
        self.urls.delete("1.0", "end")
        self._update_detected()

    def pick_dest(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.dest_var.get(), title="Carpeta de descargas")
        if folder:
            self.dest_var.set(folder)
            self._save()

    def _save(self) -> None:
        s = self.app.settings
        s["dl_kind"] = "video" if self.is_video else "audio"
        fid = self._fmt_id()
        q = self.quality.get().split()[0].rstrip("p")
        if self.is_video:
            s["dl_video_format"], s["dl_video_height"] = fid, q
        else:
            s["dl_audio_format"], s["dl_audio_bitrate"] = fid, q
        s["download_dir"] = self.dest_var.get()
        s["dl_playlist"] = bool(self.chk_playlist.get())
        s["dl_thumbnail"] = bool(self.chk_thumb.get())
        s["dl_metadata"] = bool(self.chk_meta.get())
        s["dl_subtitles"] = bool(self.chk_subs.get())
        s["dl_cookies"] = self.cookies.get()
        s.save()

    def start(self) -> None:
        urls = [u for u in self._lines() if F.looks_like_url(u)]
        if not urls:
            self.detected.configure(text="Pega al menos un enlace válido (https://...)", text_color=BAD)
            return
        self._save()
        fid = self._fmt_id()
        q = self.quality.get().split()[0].rstrip("p")
        fmt_label = self.fmt.get()
        for url in urls:
            req = DownloadRequest(
                url=url, dest=self.dest_var.get(), kind="video" if self.is_video else "audio",
                audio_format=fid if not self.is_video else "mp3", audio_bitrate=q if not self.is_video else "192",
                video_format=fid if self.is_video else "mp4",
                video_height=q if self.is_video else "1080",
                playlist=bool(self.chk_playlist.get()),
                thumbnail=bool(self.chk_thumb.get()) and self.chk_thumb.cget("state") == "normal",
                metadata=bool(self.chk_meta.get()),
                subtitles=bool(self.chk_subs.get()) and self.chk_subs.cget("state") == "normal",
                cookies_browser=COOKIE_BROWSERS[self.cookies.get()],
            )
            site = F.detect_site(url) or "Web"
            job = Job(kind="download", title=url, subtitle=f"{site} → {fmt_label}",
                      work=lambda ctx, r=req: run_download(r, ctx, self.app.log))
            self.app.submit(job, self.jobs)
        self.clear()
