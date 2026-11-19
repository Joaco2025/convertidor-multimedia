"""Pestaña del convertidor de archivos."""
from __future__ import annotations

import os
from tkinter import filedialog

import customtkinter as ctk

from .. import formats as F
from ..converter import ConvertOptions, convert_file, merge_images_pdf, parse_time
from ..jobs import Job
from ..paths import open_folder
from .widgets import (ACCENT, ACCENT_HOVER, BAD, CARD_BORDER, MUTED, OK, WARN, JobList, Section,
                      font, labeled, shorten)

CAT_BUTTONS = {"🎬 Video": "video", "🎵 Audio": "audio", "🖼 Imagen": "image"}
CAT_BY_ID = {v: k for k, v in CAT_BUTTONS.items()}
IMAGE_SIZES = ["Original", "4096", "2048", "1920", "1280", "1024", "800", "512", "256"]


class ConvertTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.files: list[str] = []
        s = app.settings
        self.grid_columnconfigure(0, weight=0, minsize=440)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent", width=430)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)

        # --- Archivos ---
        sec = Section(left, "1. Archivos")
        sec.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        b = sec.body
        self.file_box = ctk.CTkScrollableFrame(b, height=130, fg_color=("white", "#111827"),
                                               border_width=1, border_color=CARD_BORDER)
        self.file_box.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.file_box.grid_columnconfigure(1, weight=1)
        btns = ctk.CTkFrame(b, fg_color="transparent")
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ctk.CTkButton(btns, text="＋ Archivos", width=100, height=28, command=self.pick_files).pack(side="left")
        ctk.CTkButton(btns, text="＋ Carpeta", width=90, height=28, command=self.pick_folder).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Limpiar", width=70, height=28, fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=self.clear_files).pack(side="left")
        self.files_info = ctk.CTkLabel(b, text="", font=font(11), text_color=MUTED, anchor="w",
                                       wraplength=390, justify="left")
        self.files_info.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        # --- Formato ---
        sec = Section(left, "2. Convertir a")
        sec.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        b = sec.body
        self.cat = ctk.CTkSegmentedButton(b, values=list(CAT_BUTTONS), command=self._on_category)
        self.cat.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.fmt = ctk.CTkOptionMenu(b, values=["-"], command=lambda _v: self._on_format())
        labeled(b, 1, "Formato", self.fmt)
        self.fmt_note = ctk.CTkLabel(b, text="", font=font(11), text_color=MUTED, anchor="w")
        self.fmt_note.grid(row=2, column=0, columnspan=2, sticky="w")

        # --- Opciones (cambian según categoría) ---
        self.opt_sec = Section(left, "3. Opciones")
        self.opt_sec.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ob = self.opt_sec.body

        self.video_opts = ctk.CTkFrame(ob, fg_color="transparent")
        self.video_opts.grid_columnconfigure(1, weight=1)
        self.v_quality = ctk.CTkSegmentedButton(self.video_opts, values=["Alta", "Media", "Baja"])
        labeled(self.video_opts, 0, "Calidad", self.v_quality)
        self.v_height = ctk.CTkOptionMenu(self.video_opts, values=["Original", "2160p", "1440p", "1080p",
                                                                   "720p", "480p", "360p"])
        labeled(self.video_opts, 1, "Resolución", self.v_height)
        self.v_copy = ctk.CTkCheckBox(self.video_opts, text="Copiar sin recodificar (instantáneo, mismo códec)",
                                      command=self._on_format)
        self.v_copy.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)

        self.audio_opts = ctk.CTkFrame(ob, fg_color="transparent")
        self.audio_opts.grid_columnconfigure(1, weight=1)
        self.a_bitrate = ctk.CTkOptionMenu(self.audio_opts, values=[f"{b} kbps" for b in F.AUDIO_BITRATES])
        labeled(self.audio_opts, 0, "Bitrate", self.a_bitrate)
        self.a_channels = ctk.CTkSegmentedButton(self.audio_opts, values=["Original", "Estéreo", "Mono"])
        labeled(self.audio_opts, 1, "Canales", self.a_channels)

        self.trim = ctk.CTkFrame(ob, fg_color="transparent")
        self.trim.grid_columnconfigure((1, 3), weight=1)
        ctk.CTkLabel(self.trim, text="Recortar", font=font(12), text_color=MUTED).grid(row=0, column=0, padx=(0, 10))
        self.t_start = ctk.CTkEntry(self.trim, placeholder_text="inicio 0:00", width=90)
        self.t_start.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(self.trim, text="→").grid(row=0, column=2, padx=6)
        self.t_end = ctk.CTkEntry(self.trim, placeholder_text="fin (vacío = completo)", width=90)
        self.t_end.grid(row=0, column=3, sticky="ew")

        self.image_opts = ctk.CTkFrame(ob, fg_color="transparent")
        self.image_opts.grid_columnconfigure(1, weight=1)
        qrow = ctk.CTkFrame(self.image_opts, fg_color="transparent")
        qrow.grid_columnconfigure(0, weight=1)
        self.i_quality = ctk.CTkSlider(qrow, from_=10, to=100, number_of_steps=18,
                                       command=lambda v: self.i_quality_lbl.configure(text=f"{int(v)}%"))
        self.i_quality.grid(row=0, column=0, sticky="ew")
        self.i_quality_lbl = ctk.CTkLabel(qrow, text="90%", width=40)
        self.i_quality_lbl.grid(row=0, column=1)
        labeled(self.image_opts, 0, "Calidad", qrow)
        self.i_max = ctk.CTkOptionMenu(self.image_opts, values=[v if v == "Original" else f"{v} px"
                                                                for v in IMAGE_SIZES])
        labeled(self.image_opts, 1, "Tamaño máx.", self.i_max)
        self.i_merge = ctk.CTkCheckBox(self.image_opts, text="Unir todas las imágenes en un solo PDF",
                                       command=self._refresh_files)
        self.i_merge.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)

        # --- Destino ---
        sec = Section(left, "4. Guardar en")
        sec.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        b = sec.body
        self.same = ctk.CTkCheckBox(b, text="La misma carpeta que cada archivo original", command=self._on_same)
        self.same.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.out_var = ctk.StringVar(value=s["cv_output_dir"])
        self.out_row = ctk.CTkFrame(b, fg_color="transparent")
        self.out_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.out_row.grid_columnconfigure(0, weight=1)
        self.out_entry = ctk.CTkEntry(self.out_row, textvariable=self.out_var, state="readonly")
        self.out_entry.grid(row=0, column=0, sticky="ew")
        self.out_btn = ctk.CTkButton(self.out_row, text="Cambiar", width=70, command=self.pick_out)
        self.out_btn.grid(row=0, column=1, padx=(6, 0))
        ctk.CTkButton(self.out_row, text="📂", width=34, command=lambda: open_folder(self.out_var.get())).grid(
            row=0, column=2, padx=(6, 0))

        self.go = ctk.CTkButton(left, text="⚙  Convertir", height=44, font=font(15, "bold"),
                                fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.start)
        self.go.grid(row=4, column=0, sticky="ew", pady=(4, 6))
        self.go_info = ctk.CTkLabel(left, text="", font=font(11), text_color=MUTED, wraplength=410)
        self.go_info.grid(row=5, column=0, sticky="w")

        self.jobs = JobList(self, "Conversiones")
        self.jobs.grid(row=0, column=1, sticky="nsew")

        # Estado inicial
        self.v_quality.set(s["cv_video_quality"])
        self.v_height.set(s["cv_video_height"] if s["cv_video_height"] == "Original" else f"{s['cv_video_height']}p")
        self.v_copy.select() if s["cv_video_copy"] else self.v_copy.deselect()
        self.a_bitrate.set(f"{s['cv_audio_bitrate']} kbps")
        self.a_channels.set(s["cv_audio_channels"])
        self.i_quality.set(s["cv_image_quality"])
        self.i_quality_lbl.configure(text=f"{s['cv_image_quality']}%")
        self.i_max.set(s["cv_image_max"] if s["cv_image_max"] == "Original" else f"{s['cv_image_max']} px")
        self.i_merge.select() if s["cv_pdf_merge"] else self.i_merge.deselect()
        self.same.select() if s["cv_same_folder"] else self.same.deselect()
        self._on_same()
        self.cat.set(CAT_BY_ID.get(s["cv_category"], "🎬 Video"))
        self._on_category(self.cat.get())
        self._refresh_files()

    # ------------------------------------------------------------------
    @property
    def category(self) -> str:
        return CAT_BUTTONS[self.cat.get()]

    def _on_category(self, _value) -> None:
        cat = self.category
        self._formats = F.OUT_FORMATS[cat]
        labels = [f.label for f in self._formats]
        self.fmt.configure(values=labels)
        current = self.app.settings["cv_format"].get(cat)
        sel = next((f.label for f in self._formats if f.id == current), labels[0])
        self.fmt.set(sel)
        for w in (self.video_opts, self.audio_opts, self.image_opts, self.trim):
            w.grid_forget()
        if cat == "video":
            self.video_opts.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.trim.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        elif cat == "audio":
            self.audio_opts.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.trim.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        else:
            self.image_opts.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._on_format()

    def _out_format(self) -> F.OutFormat:
        return next(f for f in self._formats if f.label == self.fmt.get())

    def _on_format(self) -> None:
        f = self._out_format()
        cat = self.category
        notes = []
        if f.lossless:
            notes.append("Formato sin pérdida")
        if f.note:
            notes.append(f.note)
        if cat == "audio":
            self.a_bitrate.configure(state="disabled" if f.lossless or f.id == "amr" else "normal")
        if cat == "video":
            copy_ok = f.id in ("mp4", "mkv", "mov", "m4v", "ts", "mts", "flv")
            self.v_copy.configure(state="normal" if copy_ok else "disabled")
            copying = copy_ok and self.v_copy.get()
            for w in (self.v_quality, self.v_height):
                w.configure(state="disabled" if copying else "normal")
            if f.id == "gif":
                notes.append("Sin audio · ancho máx. 800 px")
        if cat == "image":
            self.i_merge.configure(state="normal" if f.id == "pdf" else "disabled")
            self.i_quality.configure(state="normal" if f.id in ("jpg", "webp", "heic", "avif", "jp2") else "disabled")
        self.fmt_note.configure(text=" · ".join(notes))
        if notes:
            self.fmt_note.grid()
        else:
            self.fmt_note.grid_remove()
        self._refresh_files()

    def _on_same(self) -> None:
        state = "disabled" if self.same.get() else "normal"
        self.out_btn.configure(state=state)
        self.out_entry.configure(text_color=MUTED if self.same.get() else ("gray10", "gray90"))

    # -- archivos -------------------------------------------------------
    def add_files(self, paths) -> int:
        added = 0
        known = set(self.files)
        for p in paths:
            p = os.path.normpath(p)
            if os.path.isdir(p):
                for root, _dirs, names in os.walk(p):
                    for n in sorted(names):
                        fp = os.path.join(root, n)
                        if F.input_category(fp) and fp not in known:
                            self.files.append(fp)
                            known.add(fp)
                            added += 1
            elif os.path.isfile(p) and p not in known:
                self.files.append(p)
                known.add(p)
                added += 1
        if added and not self._compatible():
            # Elige automáticamente la categoría que tenga sentido para lo agregado
            cats = {F.input_category(f) for f in self.files}
            guess = "image" if cats == {"image"} else "audio" if cats == {"audio"} else "video"
            self.cat.set(CAT_BY_ID[guess])
            self._on_category(None)
        self._refresh_files()
        return added

    def _compatible(self) -> list[str]:
        cat = self.category
        return [f for f in self.files if F.can_convert(f, cat)]

    def _refresh_files(self) -> None:
        if not hasattr(self, "_formats"):
            return
        for w in self.file_box.winfo_children():
            w.destroy()
        if not self.files:
            ctk.CTkLabel(self.file_box, text="Arrastra archivos aquí o usa ＋ Archivos",
                         font=font(12), text_color=MUTED).grid(row=0, column=0, columnspan=3, pady=40)
        cat = self.category
        for i, path in enumerate(self.files[:300]):
            ok = F.can_convert(path, cat)
            ext = F.ext_of(path)
            ctk.CTkLabel(self.file_box, text=ext.upper()[:4] or "?", width=44, height=20, corner_radius=4,
                         fg_color=ACCENT if ok else ("gray70", "gray30"), text_color="white",
                         font=font(10, "bold")).grid(row=i, column=0, padx=(2, 6), pady=2)
            ctk.CTkLabel(self.file_box, text=shorten(os.path.basename(path), 44), anchor="w", font=font(12),
                         text_color=("gray10", "gray90") if ok else MUTED).grid(row=i, column=1, sticky="ew")
            ctk.CTkButton(self.file_box, text="✕", width=24, height=20, fg_color="transparent",
                          text_color=MUTED, hover_color=CARD_BORDER,
                          command=lambda p=path: self.remove_file(p)).grid(row=i, column=2, padx=2)
        if len(self.files) > 300:
            ctk.CTkLabel(self.file_box, text=f"… y {len(self.files) - 300} más", text_color=MUTED).grid(
                row=301, column=0, columnspan=3)
        comp = len(self._compatible())
        total = len(self.files)
        if not total:
            self.files_info.configure(text="Video, audio e imágenes: " + ", ".join(
                sorted({"MP4", "MKV", "MOV", "AVI", "MP3", "WAV", "FLAC", "JPG", "PNG", "HEIC", "WEBP"})) + "…",
                text_color=MUTED)
            self.go.configure(text="⚙  Convertir", state="disabled")
        else:
            color = OK if comp == total else WARN if comp else BAD
            msg = f"{total} archivo(s) · {comp} compatibles con {F.CATEGORY_LABELS[cat].lower()}"
            self.files_info.configure(text=msg, text_color=color)
            f = self._out_format()
            merge = cat == "image" and f.id == "pdf" and self.i_merge.get() and comp > 1
            label = f"⚙  Unir {comp} imágenes en PDF" if merge else f"⚙  Convertir {comp} a {f.ext.upper()}"
            self.go.configure(text=label, state="normal" if comp else "disabled")

    def remove_file(self, path: str) -> None:
        if path in self.files:
            self.files.remove(path)
        self._refresh_files()

    def clear_files(self) -> None:
        self.files.clear()
        self._refresh_files()

    def pick_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Elegir archivos", filetypes=F.all_input_patterns())
        if paths:
            self.add_files(paths)

    def pick_folder(self) -> None:
        folder = filedialog.askdirectory(title="Agregar carpeta (incluye subcarpetas)")
        if folder:
            self.add_files([folder])

    def pick_out(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.out_var.get(), title="Carpeta de salida")
        if folder:
            self.out_var.set(folder)

    # -- ejecutar -------------------------------------------------------
    def _build_options(self) -> ConvertOptions:
        f = self._out_format()
        return ConvertOptions(
            category=self.category, fmt_id=f.id,
            dest_dir=None if self.same.get() else self.out_var.get(),
            video_quality=self.v_quality.get() or "Media",
            video_height=self.v_height.get().rstrip("p"),
            video_copy=bool(self.v_copy.get()) and self.v_copy.cget("state") == "normal",
            audio_bitrate=self.a_bitrate.get().split()[0],
            audio_channels=self.a_channels.get() or "Original",
            trim_start=self.t_start.get(), trim_end=self.t_end.get(),
            image_quality=int(self.i_quality.get()),
            image_max=self.i_max.get().split()[0],
            pdf_merge=bool(self.i_merge.get()),
        )

    def _save(self, o: ConvertOptions) -> None:
        s = self.app.settings
        s["cv_category"] = o.category
        s["cv_format"][o.category] = o.fmt_id
        s["cv_same_folder"] = bool(self.same.get())
        s["cv_output_dir"] = self.out_var.get()
        s["cv_video_quality"] = o.video_quality
        s["cv_video_height"] = o.video_height
        s["cv_video_copy"] = bool(self.v_copy.get())
        s["cv_audio_bitrate"] = o.audio_bitrate
        s["cv_audio_channels"] = o.audio_channels
        s["cv_image_quality"] = o.image_quality
        s["cv_image_max"] = o.image_max
        s["cv_pdf_merge"] = o.pdf_merge
        s.save()

    def start(self) -> None:
        files = self._compatible()
        if not files:
            return
        o = self._build_options()
        try:
            parse_time(o.trim_start), parse_time(o.trim_end)
        except ValueError as exc:
            self.go_info.configure(text=str(exc), text_color=BAD)
            return
        self.go_info.configure(text="")
        self._save(o)
        fmt = self._out_format()
        if o.category == "image" and fmt.id == "pdf" and o.pdf_merge and len(files) > 1:
            job = Job(kind="convert", title=f"{len(files)} imágenes → PDF", subtitle=os.path.basename(files[0]),
                      work=lambda ctx, fs=list(files): merge_images_pdf(fs, o, ctx))
            self.app.submit(job, self.jobs)
        else:
            for path in files:
                job = Job(kind="convert", title=os.path.basename(path),
                          subtitle=f"{F.ext_of(path).upper()} → {fmt.label}",
                          work=lambda ctx, p=path: convert_file(p, o, ctx, self.app.log))
                self.app.submit(job, self.jobs)
        # Quita de la lista los que ya se enviaron
        self.files = [f for f in self.files if f not in set(files)]
        self._refresh_files()
