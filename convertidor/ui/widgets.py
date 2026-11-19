"""Componentes reutilizables de la interfaz."""
from __future__ import annotations

import os
import customtkinter as ctk

from ..jobs import CANCELLED, DONE, ERROR, PENDING, RUNNING, Job
from ..paths import open_folder

# Paleta (claro, oscuro)
ACCENT = ("#2563eb", "#3b82f6")
ACCENT_HOVER = ("#1d4ed8", "#2563eb")
MUTED = ("#6b7280", "#9ca3af")
CARD = ("#f3f4f6", "#1f2937")
CARD_BORDER = ("#e5e7eb", "#374151")
OK = ("#16a34a", "#4ade80")
WARN = ("#d97706", "#fbbf24")
BAD = ("#dc2626", "#f87171")
TEXT = ("#111827", "#f9fafb")

STATUS_STYLE = {
    PENDING: ("En cola", MUTED),
    RUNNING: ("En curso", ACCENT),
    DONE: ("Listo", OK),
    ERROR: ("Error", BAD),
    CANCELLED: ("Cancelado", WARN),
}


def font(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


def shorten(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


class Section(ctk.CTkFrame):
    """Tarjeta con título."""

    def __init__(self, master, title: str, **kw):
        super().__init__(master, fg_color=CARD, border_color=CARD_BORDER, border_width=1,
                         corner_radius=10, **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=font(13, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self.body.grid_columnconfigure(1, weight=1)


def labeled(parent, row: int, text: str, widget) -> None:
    ctk.CTkLabel(parent, text=text, font=font(12), text_color=MUTED, anchor="w").grid(
        row=row, column=0, sticky="w", padx=(0, 10), pady=4)
    widget.grid(row=row, column=1, sticky="ew", pady=4)


class JobRow(ctk.CTkFrame):
    def __init__(self, master, job: Job, on_cancel, on_remove):
        super().__init__(master, fg_color=CARD, border_color=CARD_BORDER, border_width=1, corner_radius=8)
        self.job = job
        self._on_remove = on_remove
        self.output = ""
        self.status = PENDING
        self._indeterminate = False
        self.grid_columnconfigure(0, weight=1)

        self.title_lbl = ctk.CTkLabel(self, text=shorten(job.title, 58), font=font(13, "bold"), anchor="w")
        self.title_lbl.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=(8, 0))
        self.badge = ctk.CTkLabel(self, text="En cola", font=font(11, "bold"), text_color=MUTED, width=70)
        self.badge.grid(row=0, column=1, padx=4, pady=(8, 0))
        self.btn = ctk.CTkButton(self, text="✕", width=30, height=26, fg_color="transparent",
                                 hover_color=CARD_BORDER, text_color=TEXT, font=font(13),
                                 command=lambda: on_cancel(self))
        self.btn.grid(row=0, column=2, rowspan=2, padx=(0, 8), pady=(8, 0))

        self.sub_lbl = ctk.CTkLabel(self, text=shorten(job.subtitle, 70), font=font(11),
                                    text_color=MUTED, anchor="w")
        self.sub_lbl.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12)
        self.bar = ctk.CTkProgressBar(self, height=6, progress_color=ACCENT)
        self.bar.set(0)
        self.bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 2))
        self.msg_lbl = ctk.CTkLabel(self, text="En cola", font=font(11), text_color=MUTED, anchor="w")
        self.msg_lbl.grid(row=3, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 8))

    # -- actualización desde eventos (siempre en el hilo de Tk) --
    def apply(self, fields: dict) -> None:
        if "title" in fields:
            self.title_lbl.configure(text=shorten(fields["title"], 58))
        if "subtitle" in fields:
            self.sub_lbl.configure(text=shorten(fields["subtitle"], 70))
        if "progress" in fields:
            self._set_progress(fields["progress"])
        if "message" in fields:
            self.msg_lbl.configure(text=shorten(fields["message"], 110))
        if "output" in fields and fields["output"]:
            self.output = fields["output"]
        if "status" in fields:
            self._set_status(fields["status"])

    def _set_progress(self, value) -> None:
        if value is None:
            if not self._indeterminate:
                self._indeterminate = True
                self.bar.configure(mode="indeterminate")
                self.bar.start()
        else:
            if self._indeterminate:
                self._indeterminate = False
                self.bar.stop()
                self.bar.configure(mode="determinate")
            self.bar.set(max(0.0, min(1.0, float(value))))

    def _set_status(self, status: str) -> None:
        self.status = status
        text, color = STATUS_STYLE.get(status, (status, MUTED))
        self.badge.configure(text=text, text_color=color)
        if status in (DONE, ERROR, CANCELLED):
            self._set_progress(1.0 if status == DONE else 0.0)
            self.bar.configure(progress_color=OK if status == DONE else BAD if status == ERROR else WARN)
            if status == DONE and self.output:
                self.btn.configure(text="📂", command=lambda: open_folder(self.output))
            else:
                self.btn.configure(text="🗑", command=self.destroy_row)
            if status == ERROR:
                self.msg_lbl.configure(text_color=BAD)

    def destroy_row(self) -> None:
        self._on_remove(self)

    @property
    def finished(self) -> bool:
        return self.status in (DONE, ERROR, CANCELLED)


class JobList(ctk.CTkFrame):
    def __init__(self, master, title: str):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        head.grid_columnconfigure(0, weight=1)
        self.title_lbl = ctk.CTkLabel(head, text=title, font=font(15, "bold"), anchor="w")
        self.title_lbl.grid(row=0, column=0, sticky="w")
        self._title = title
        ctk.CTkButton(head, text="Cancelar todo", width=110, height=28, fg_color="transparent",
                      border_width=1, border_color=CARD_BORDER, text_color=TEXT, hover_color=CARD,
                      command=self.cancel_all).grid(row=0, column=1, padx=4)
        ctk.CTkButton(head, text="Limpiar terminados", width=140, height=28, fg_color="transparent",
                      border_width=1, border_color=CARD_BORDER, text_color=TEXT, hover_color=CARD,
                      command=self.clear_finished).grid(row=0, column=2)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.empty = ctk.CTkLabel(self.scroll, text="Aún no hay tareas.\nLo que agregues aparecerá aquí.",
                                  font=font(12), text_color=MUTED, justify="center")
        self.empty.grid(row=0, column=0, pady=60)
        self.rows: list[JobRow] = []

    def add(self, job: Job) -> JobRow:
        self.empty.grid_forget()
        row = JobRow(self.scroll, job, on_cancel=self._cancel_row, on_remove=self.remove_row)
        self.rows.insert(0, row)
        self._relayout()
        return row

    def _relayout(self) -> None:
        for i, r in enumerate(self.rows):
            r.grid(row=i, column=0, sticky="ew", pady=(0, 6), padx=(0, 4))
        if not self.rows:
            self.empty.grid(row=0, column=0, pady=60)
        self.refresh_title()

    def refresh_title(self) -> None:
        active = sum(1 for r in self.rows if not r.finished)
        self.title_lbl.configure(text=f"{self._title}  ·  {active} activas" if active else self._title)

    def _cancel_row(self, row: JobRow) -> None:
        row.job.cancel_event.set()
        if row.status == PENDING:
            row.apply({"status": CANCELLED, "message": "Cancelado"})
        else:
            row.apply({"message": "Cancelando..."})

    def remove_row(self, row: JobRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
            row.destroy()
            self._relayout()

    def cancel_all(self) -> None:
        for r in self.rows:
            if not r.finished:
                self._cancel_row(r)

    def clear_finished(self) -> None:
        for r in [r for r in self.rows if r.finished]:
            self.rows.remove(r)
            r.destroy()
        self._relayout()

    def active_count(self) -> int:
        return sum(1 for r in self.rows if not r.finished)


def file_badge(ext: str) -> str:
    return ext.upper()[:4] if ext else "?"


def basename(path: str) -> str:
    return os.path.basename(path)
