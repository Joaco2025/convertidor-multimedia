"""Ventana principal."""
from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import urllib.request
from logging.handlers import RotatingFileHandler

import customtkinter as ctk

from .. import formats as F
from ..downloader import ytdlp_version
from ..jobs import CANCELLED, DONE, ERROR, Job, JobQueue
from ..paths import (APP_NAME, APP_VERSION, FFMPEG, FFPROBE, config_dir, is_frozen, js_runtimes,
                     open_folder)
from ..settings import Settings
from .convert_tab import ConvertTab
from .download_tab import DownloadTab
from .widgets import BAD, MUTED, OK, WARN, JobList, Section, font, labeled

try:  # Arrastrar y soltar (opcional)
    from tkinterdnd2 import DND_FILES, DND_TEXT, TkinterDnD

    class _Base(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.TkdndVersion = TkinterDnD._require(self)

    HAS_DND = True
except Exception:  # noqa: BLE001
    _Base = ctk.CTk
    HAS_DND = False


class App(_Base):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        ctk.set_appearance_mode(self.settings["theme"])
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} · Chito version")
        self.geometry("1180x760")
        self.minsize(1000, 640)
        self._set_icon()

        self._setup_logging()
        self.events: "queue.Queue" = queue.Queue()
        self.rows: dict[int, object] = {}
        self.dl_queue = JobQueue(self.events, self.settings["dl_parallel"], self.log)
        self.cv_queue = JobQueue(self.events, self.settings["cv_parallel"], self.log)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self.tabs = ctk.CTkTabview(self, anchor="nw", corner_radius=10)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 14))
        for name in ("⬇  Descargar", "⚙  Convertir", "☰  Ajustes", "📝 Registro"):
            self.tabs.add(name)
            self.tabs.tab(name).grid_columnconfigure(0, weight=1)
            self.tabs.tab(name).grid_rowconfigure(0, weight=1)
        self.download_tab = DownloadTab(self.tabs.tab("⬇  Descargar"), self)
        self.download_tab.grid(row=0, column=0, sticky="nsew")
        self.convert_tab = ConvertTab(self.tabs.tab("⚙  Convertir"), self)
        self.convert_tab.grid(row=0, column=0, sticky="nsew")
        self._build_settings(self.tabs.tab("☰  Ajustes"))
        self._build_log(self.tabs.tab("📝 Registro"))

        if HAS_DND:
            self.drop_target_register(DND_FILES, DND_TEXT)
            self.dnd_bind("<<Drop>>", self._on_drop)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._poll)
        self.log(f"{APP_NAME} {APP_VERSION} · yt-dlp {ytdlp_version()} · FFmpeg: {FFMPEG or 'NO ENCONTRADO'}")

    # ------------------------------------------------------------------
    def _set_icon(self) -> None:
        from ..paths import resource_dir
        ico = os.path.join(resource_dir(), "assets", "icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:  # noqa: BLE001
                pass

    def _setup_logging(self) -> None:
        self.log_path = os.path.join(config_dir(), "app.log")
        self.logger = logging.getLogger("convertidor")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            h = RotatingFileHandler(self.log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
            self.logger.addHandler(h)

    def log(self, msg: str) -> None:
        """Seguro desde cualquier hilo."""
        self.logger.info(msg)
        self.events.put(("log", msg))

    def _build_header(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="🎛", font=font(28)).grid(row=0, column=0, rowspan=2, padx=(0, 10))
        ctk.CTkLabel(head, text=APP_NAME, font=font(22, "bold"), anchor="w").grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(head, text="Descarga de 1800+ sitios y convierte entre 45 formatos de video, audio e imagen",
                     font=font(12), text_color=MUTED, anchor="w").grid(row=1, column=1, sticky="w")
        ok = bool(FFMPEG)
        ctk.CTkLabel(head, text="● FFmpeg listo" if ok else "● FFmpeg no encontrado",
                     text_color=OK if ok else BAD, font=font(12, "bold")).grid(row=0, column=2, rowspan=2, padx=12)
        self.theme_btn = ctk.CTkSegmentedButton(head, values=["Sistema", "Claro", "Oscuro"],
                                                command=self._on_theme)
        self.theme_btn.set({"System": "Sistema", "Light": "Claro", "Dark": "Oscuro"}[self.settings["theme"]])
        self.theme_btn.grid(row=0, column=3, rowspan=2)

    def _on_theme(self, value: str) -> None:
        mode = {"Sistema": "System", "Claro": "Light", "Oscuro": "Dark"}[value]
        ctk.set_appearance_mode(mode)
        self.settings["theme"] = mode
        self.settings.save()

    # -- Ajustes --------------------------------------------------------
    def _build_settings(self, tab) -> None:
        frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure((0, 1), weight=1, uniform="c")

        sec = Section(frame, "Rendimiento")
        sec.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))
        dl = ctk.CTkOptionMenu(sec.body, values=["1", "2", "3", "4"],
                               command=lambda v: self._set_parallel("dl_parallel", self.dl_queue, v))
        dl.set(str(self.settings["dl_parallel"]))
        labeled(sec.body, 0, "Descargas simultáneas", dl)
        cv = ctk.CTkOptionMenu(sec.body, values=["1", "2", "3", "4"],
                               command=lambda v: self._set_parallel("cv_parallel", self.cv_queue, v))
        cv.set(str(self.settings["cv_parallel"]))
        labeled(sec.body, 1, "Conversiones simultáneas", cv)
        ctk.CTkLabel(sec.body, text="FFmpeg ya usa todos los núcleos; más de 1-2 conversiones a la vez\n"
                                    "rara vez acelera el total.", font=font(11), text_color=MUTED,
                     justify="left").grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        sec = Section(frame, "Motores")
        sec.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))
        b = sec.body
        rt = ", ".join(js_runtimes()) or "ninguno (YouTube puede fallar: instala Deno o Node.js)"
        rows = [("FFmpeg", FFMPEG or "No encontrado"), ("FFprobe", FFPROBE or "No encontrado"),
                ("yt-dlp", ytdlp_version()), ("JavaScript", rt),
                ("Arrastrar y soltar", "Sí" if HAS_DND else "No (instala tkinterdnd2)")]
        for i, (k, v) in enumerate(rows):
            labeled(b, i, k, ctk.CTkLabel(b, text=v, font=font(11), anchor="w", wraplength=330, justify="left"))
        self.upd_lbl = ctk.CTkLabel(b, text="", font=font(11), text_color=MUTED, anchor="w", wraplength=380)
        ctk.CTkButton(b, text="Buscar actualización de yt-dlp", command=self._check_update).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(8, 2))
        self.upd_lbl.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w")

        sec = Section(frame, "Sitios de descarga más usados (top 15)")
        sec.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))
        ctk.CTkLabel(sec.body, text="\n".join(f"• {n}" for n, _ in F.SITES) +
                     "\n…y más de 1800 sitios compatibles con yt-dlp.",
                     justify="left", anchor="w", font=font(12)).grid(row=0, column=0, sticky="w")

        sec = Section(frame, "Formatos de conversión (top 15 por tipo)")
        sec.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))
        for i, (cat, items) in enumerate(F.OUT_FORMATS.items()):
            ctk.CTkLabel(sec.body, text=F.CATEGORY_LABELS[cat], font=font(12, "bold"), anchor="w").grid(
                row=i * 2, column=0, columnspan=2, sticky="w", pady=(6 if i else 0, 0))
            ctk.CTkLabel(sec.body, text=", ".join(f.id.upper() for f in items), font=font(12), anchor="w",
                         wraplength=420, justify="left").grid(row=i * 2 + 1, column=0, columnspan=2, sticky="w")

        sec = Section(frame, "Archivos de la app")
        sec.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ctk.CTkButton(sec.body, text="Abrir carpeta de configuración y registro",
                      command=lambda: open_folder(config_dir())).grid(row=0, column=0, sticky="w")

    def _set_parallel(self, key: str, q: JobQueue, value: str) -> None:
        self.settings[key] = int(value)
        self.settings.save()
        q.set_workers(int(value))

    def _check_update(self) -> None:
        self.upd_lbl.configure(text="Consultando PyPI...", text_color=MUTED)

        def work():
            try:
                with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=10) as r:
                    latest = json.load(r)["info"]["version"]
            except Exception as exc:  # noqa: BLE001
                self.events.put(("update", (f"No se pudo consultar: {exc}", BAD, False)))
                return
            current = ytdlp_version()
            if latest == current:
                self.events.put(("update", (f"yt-dlp está al día ({current}).", OK, False)))
            elif is_frozen():
                self.events.put(("update", (f"Hay una versión nueva ({latest}, tienes {current}). "
                                            "Vuelve a compilar el .exe con build.bat para actualizar.", WARN, False)))
            else:
                self.events.put(("update", (f"Actualizando a {latest}...", WARN, False)))
                proc = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"],
                                      capture_output=True, text=True)
                if proc.returncode == 0:
                    self.events.put(("update", (f"Actualizado a {latest}. Reinicia la app.", OK, True)))
                else:
                    self.log(proc.stderr)
                    self.events.put(("update", ("Falló la actualización (ver Registro).", BAD, False)))

        threading.Thread(target=work, daemon=True).start()

    # -- Registro -------------------------------------------------------
    def _build_log(self, tab) -> None:
        self.log_box = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Consolas", size=11), wrap="word")
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    def _append_log(self, msg: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg.rstrip() + "\n")
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 2000:
            self.log_box.delete("1.0", f"{lines - 2000}.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # -- Trabajos -------------------------------------------------------
    def submit(self, job: Job, joblist: JobList) -> None:
        row = joblist.add(job)
        self.rows[job.id] = (row, joblist)
        (self.dl_queue if job.kind == "download" else self.cv_queue).submit(job)

    def _poll(self) -> None:
        changed_lists = set()
        try:
            for _ in range(300):
                key, payload = self.events.get_nowait()
                if key == "log":
                    self._append_log(payload)
                elif key == "update":
                    text, color, _restart = payload
                    self.upd_lbl.configure(text=text, text_color=color)
                elif key in self.rows:
                    row, jl = self.rows[key]
                    if row.winfo_exists():
                        if row.finished and "status" not in payload:
                            continue  # ignora eventos tardíos tras cancelar
                        row.apply(payload)
                        if "status" in payload:
                            changed_lists.add(jl)
                            if payload["status"] in (DONE, ERROR, CANCELLED):
                                self._on_job_finished(jl)
        except queue.Empty:
            pass
        for jl in changed_lists:
            jl.refresh_title()
        self.after(80, self._poll)

    def _on_job_finished(self, jl: JobList) -> None:
        active = self.download_tab.jobs.active_count() + self.convert_tab.jobs.active_count()
        self.title(f"{APP_NAME} · Chito version" + (f"  ({active} en curso)" if active else ""))
        if not active:
            self.bell()

    def _on_drop(self, event) -> None:
        items = self.tk.splitlist(event.data)
        urls = [i for i in items if F.looks_like_url(i)]
        paths = [i for i in items if os.path.exists(i)]
        if not urls and not paths and F.looks_like_url(str(event.data).strip()):
            urls = [str(event.data).strip()]
        if urls:
            self.download_tab.add_urls("\n".join(urls))
            self.tabs.set("⬇  Descargar")
        if paths:
            self.convert_tab.add_files(paths)
            self.tabs.set("⚙  Convertir")

    def _on_close(self) -> None:
        active = self.download_tab.jobs.active_count() + self.convert_tab.jobs.active_count()
        if active:
            from tkinter import messagebox
            if not messagebox.askyesno(APP_NAME, f"Hay {active} tarea(s) en curso. ¿Cancelarlas y salir?"):
                return
            self.download_tab.jobs.cancel_all()
            self.convert_tab.jobs.cancel_all()
        self.settings.save()
        self.destroy()
