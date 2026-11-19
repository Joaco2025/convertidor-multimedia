"""Instalador tipo asistente: Bienvenida → Ubicación → Componentes → Listo.

    instalador.exe                    instalación normal
    instalador.exe --update --dir X   actualizar (lo lanza la app)
    instalador.exe --uninstall        desinstalar (lo usa "Agregar o quitar programas")
"""
from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import traceback
from tkinter import filedialog, messagebox

import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deps  # noqa: E402

ACCENT = ("#2563eb", "#2563eb")
MUTED = ("#6b7280", "#9ca3af")
OK = ("#16a34a", "#4ade80")
BAD = ("#dc2626", "#f87171")
WARN = ("#d97706", "#fbbf24")
CARD = ("#f3f4f6", "#1f2937")
BORDER = ("#e5e7eb", "#374151")

COMPONENTS = [
    ("python", "Python 3.10 o superior", "Ejecuta la app", "~26 MB"),
    ("ffmpeg", "FFmpeg", "Convierte audio, video e imágenes animadas", "~87 MB"),
    ("js", "Motor JavaScript (Deno o Node)", "Lo necesita yt-dlp para YouTube", "~41 MB"),
    ("app", deps.APP_NAME, "Última versión desde GitHub", "< 1 MB"),
    ("libs", "Librerías de Python", "yt-dlp, CustomTkinter, Pillow, HEIF…", "~45 MB"),
]
STEPS = ["Bienvenida", "Ubicación", "Componentes", "Listo"]


def F(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


class Wizard(ctk.CTk):
    def __init__(self, update_dir: str | None = None):
        super().__init__()
        ctk.set_appearance_mode("System")
        self.title(f"Instalar {deps.APP_NAME}")
        self.geometry("780x580")
        self.resizable(False, False)
        icon = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "icon.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except Exception:  # noqa: BLE001
                pass

        self.events: queue.Queue = queue.Queue()
        self.ctx = deps.Ctx(log=lambda m: self.events.put(("log", m)),
                            progress=lambda f, t: self.events.put(("progress", (f, t))))
        self.busy = False
        self.update_mode = bool(update_dir)
        self.root_dir = update_dir or deps.registered_dir() or deps.DEFAULT_DIR
        self.found: dict = {}
        self.page = 0

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=28, pady=(26, 8))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self._navbar()

        self.pages = [self._page_welcome(), self._page_location(), self._page_components(), self._page_done()]
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(80, self._poll)
        self.show(2 if self.update_mode else 0)

    # ------------------------------------------------------------------ layout
    def _sidebar(self):
        side = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=ACCENT)
        side.grid(row=0, column=0, rowspan=2, sticky="nsw")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="⬇", font=F(54, "bold"), text_color="white").pack(pady=(34, 0))
        ctk.CTkLabel(side, text=deps.APP_NAME, font=F(17, "bold"), text_color="white",
                     wraplength=180).pack(pady=(4, 26))
        self.step_lbls = []
        for name in STEPS:
            lbl = ctk.CTkLabel(side, text=name, font=F(13), text_color="#bfdbfe", anchor="w")
            lbl.pack(fill="x", padx=30, pady=5)
            self.step_lbls.append(lbl)
        ctk.CTkLabel(side, text="Código abierto en GitHub", font=F(10), text_color="#bfdbfe").pack(
            side="bottom", pady=14)

    def _navbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=1, sticky="ew", padx=28, pady=(0, 18))
        self.btn_cancel = ctk.CTkButton(bar, text="Cancelar", width=100, fg_color="transparent", border_width=1,
                                        border_color=BORDER, text_color=("gray10", "gray90"), hover_color=CARD,
                                        command=self._cancel)
        self.btn_cancel.pack(side="left")
        self.btn_next = ctk.CTkButton(bar, text="Siguiente  ›", width=150, height=36, font=F(13, "bold"),
                                      command=self._next)
        self.btn_next.pack(side="right")
        self.btn_back = ctk.CTkButton(bar, text="‹  Atrás", width=100, height=36, fg_color="transparent",
                                      border_width=1, border_color=BORDER, text_color=("gray10", "gray90"),
                                      hover_color=CARD, command=self._back)
        self.btn_back.pack(side="right", padx=8)

    def _title(self, parent, title, subtitle):
        ctk.CTkLabel(parent, text=title, font=F(22, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(parent, text=subtitle, font=F(13), text_color=MUTED, anchor="w", justify="left",
                     wraplength=500).pack(fill="x", pady=(4, 16))

    def _page_welcome(self):
        p = ctk.CTkFrame(self.content, fg_color="transparent")
        self._title(p, f"Bienvenido a {deps.APP_NAME}",
                    "Este asistente instalará la app en tu computadora. Te llevará sólo unos pasos.")
        feats = ("⬇  Descarga audio y video de YouTube, TikTok, Instagram y 1800+ sitios",
                 "⚙  Convierte entre 45 formatos de video, audio e imagen",
                 "⟳  Se mantiene al día: yt-dlp y la app se actualizan solos",
                 "🔒  Se instala sólo para tu usuario, sin permisos de administrador")
        for f in feats:
            ctk.CTkLabel(p, text=f, font=F(13), anchor="w").pack(fill="x", pady=4)
        ctk.CTkLabel(p, text="El instalador revisará qué componentes ya tienes y descargará sólo los que falten.\n"
                             "Haz clic en Siguiente para continuar.",
                     font=F(12), text_color=MUTED, anchor="w", justify="left").pack(fill="x", pady=(22, 0))
        return p

    def _page_location(self):
        p = ctk.CTkFrame(self.content, fg_color="transparent")
        self._title(p, "Ubicación de la instalación", "Elige dónde instalar la app y qué accesos directos crear.")
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")
        self.dir_var = ctk.StringVar(value=self.root_dir)
        ctk.CTkEntry(row, textvariable=self.dir_var, height=34).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Examinar...", width=100, height=34, command=self._browse).pack(side="left", padx=(8, 0))
        self.chk_desktop = ctk.CTkCheckBox(p, text="Crear acceso directo en el Escritorio")
        self.chk_desktop.select()
        self.chk_desktop.pack(anchor="w", pady=(18, 6))
        self.chk_start = ctk.CTkCheckBox(p, text="Agregar al menú Inicio")
        self.chk_start.select()
        self.chk_start.pack(anchor="w", pady=6)
        ctk.CTkLabel(p, text="Espacio necesario: ~250 MB como máximo (depende de lo que ya tengas instalado).",
                     font=F(12), text_color=MUTED, anchor="w").pack(fill="x", pady=(18, 0))
        return p

    def _page_components(self):
        p = ctk.CTkFrame(self.content, fg_color="transparent")
        self._title(p, "Componentes", "Revisando lo que necesita la app...")
        self.comp_sub = p.winfo_children()[-1]
        self.rows = {}
        box = ctk.CTkFrame(p, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=10)
        box.pack(fill="x")
        box.grid_columnconfigure(1, weight=1)
        for i, (key, name, desc, size) in enumerate(COMPONENTS):
            icon = ctk.CTkLabel(box, text="…", width=28, font=F(16, "bold"), text_color=MUTED)
            icon.grid(row=i, column=0, padx=(14, 6), pady=7, sticky="n")
            txt = ctk.CTkFrame(box, fg_color="transparent")
            txt.grid(row=i, column=1, sticky="ew", pady=3)
            ctk.CTkLabel(txt, text=name, font=F(13, "bold"), anchor="w").pack(fill="x")
            detail = ctk.CTkLabel(txt, text=desc, font=F(11), text_color=MUTED, anchor="w", justify="left",
                                  wraplength=360)
            detail.pack(fill="x")
            status = ctk.CTkLabel(box, text="", font=F(11, "bold"), text_color=MUTED, width=110, anchor="e")
            status.grid(row=i, column=2, padx=(6, 14))
            self.rows[key] = {"icon": icon, "detail": detail, "status": status, "desc": desc, "size": size}
        self.bar = ctk.CTkProgressBar(p, height=8)
        self.bar.set(0)
        self.bar.pack(fill="x", pady=(14, 4))
        line = ctk.CTkFrame(p, fg_color="transparent")
        line.pack(fill="x")
        self.prog_lbl = ctk.CTkLabel(line, text="", font=F(11), text_color=MUTED, anchor="w")
        self.prog_lbl.pack(side="left", fill="x", expand=True)
        self.btn_log = ctk.CTkButton(line, text="Ver detalles", width=90, height=22, font=F(11),
                                     fg_color="transparent", text_color=MUTED, hover_color=CARD,
                                     command=self._toggle_log)
        self.btn_log.pack(side="right")
        self.log_box = ctk.CTkTextbox(p, height=90, font=ctk.CTkFont(family="Consolas", size=10))
        self.log_box.configure(state="disabled")
        return p

    def _page_done(self):
        p = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(p, text="✓", font=F(60, "bold"), text_color=OK).pack(pady=(10, 0))
        self.done_title = ctk.CTkLabel(p, text="¡Instalación completada!", font=F(22, "bold"))
        self.done_title.pack()
        self.done_sub = ctk.CTkLabel(p, text="", font=F(13), text_color=MUTED, wraplength=480, justify="center")
        self.done_sub.pack(pady=(6, 24))
        self.chk_launch = ctk.CTkCheckBox(p, text=f"Abrir {deps.APP_NAME} ahora")
        self.chk_launch.select()
        self.chk_launch.pack()
        return p

    # ------------------------------------------------------------------ navegación
    def show(self, idx: int):
        for pg in self.pages:
            pg.grid_forget()
        self.page = idx
        self.pages[idx].grid(row=0, column=0, sticky="nsew")
        for i, lbl in enumerate(self.step_lbls):
            lbl.configure(text=("●  " if i == idx else "✓  " if i < idx else "○  ") + STEPS[i],
                          text_color="white" if i <= idx else "#bfdbfe", font=F(13, "bold" if i == idx else "normal"))
        self.btn_back.configure(state="normal" if 0 < idx < 3 and not self.update_mode else "disabled")
        if idx == 3:
            self.btn_back.pack_forget()
            self.btn_cancel.pack_forget()
            self.btn_next.configure(text="Finalizar", state="normal")
        elif idx == 2:
            self.btn_next.configure(text="Comprobando...", state="disabled")
            self._detect()
        else:
            self.btn_next.configure(text="Siguiente  ›", state="normal")

    def _next(self):
        if self.busy:
            return
        if self.page == 1:
            self.root_dir = deps.safe_install_dir(self.dir_var.get().strip() or deps.DEFAULT_DIR)
            self.dir_var.set(self.root_dir)
        if self.page == 2:
            if self.found.get("missing"):
                self._install()
            else:
                self._finalize()
            return
        if self.page == 3:
            if self.chk_launch.get():
                try:
                    deps.launch_app(self.root_dir)
                except OSError as exc:
                    messagebox.showerror(deps.APP_NAME, f"No se pudo abrir la app: {exc}")
            self.destroy()
            return
        self.show(self.page + 1)

    def _back(self):
        if not self.busy and self.page > 0:
            self.show(self.page - 1)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=os.path.dirname(self.dir_var.get()) or "C:\\")
        if d:
            self.dir_var.set(os.path.normpath(d))

    def _cancel(self):
        if self.page == 3:
            self.destroy()
            return
        if self.busy:
            if messagebox.askyesno(deps.APP_NAME, "¿Cancelar la instalación en curso?"):
                self.ctx.cancelled = True
            return
        if messagebox.askyesno(deps.APP_NAME, "¿Salir del instalador?"):
            self.destroy()

    def _toggle_log(self):
        if self.log_box.winfo_ismapped():
            self.log_box.pack_forget()
            self.btn_log.configure(text="Ver detalles")
        else:
            self.log_box.pack(fill="x", pady=(4, 0))
            self.btn_log.configure(text="Ocultar")

    # ------------------------------------------------------------------ trabajo en hilos
    def _thread(self, fn):
        self.busy = True
        self.ctx.cancelled = False
        self.btn_back.configure(state="disabled")

        def run():
            try:
                fn()
            except deps.Aborted as exc:
                self.events.put(("aborted", str(exc)))
            except Exception as exc:  # noqa: BLE001
                self.events.put(("log", traceback.format_exc()))
                self.events.put(("fatal", str(exc)))
            finally:
                self.events.put(("idle", None))
        threading.Thread(target=run, daemon=True).start()

    def _row(self, key, icon, color, status, detail=None):
        self.events.put(("row", (key, icon, color, status, detail)))

    def _detect(self):
        root = self.root_dir
        for key, *_ in COMPONENTS:
            self._row(key, "…", MUTED, "Comprobando", None)
        self.events.put(("progress", (None, "Comprobando componentes...")))

        def work():
            st: dict = {"missing": []}
            py = deps.find_python(root)
            st["python"] = py
            where = ("entorno de la app" if py and "venv" in py[1].lower()
                     else "Microsoft Store" if py and "windowsapps" in py[1].lower() else "sistema")
            self._report("python", py, f"Python {py[0]} · {where}" if py else None)
            ff = deps.find_ffmpeg(root)
            self._report("ffmpeg", ff, ff)
            js = deps.find_js(root)
            self._report("js", js, js)
            inst, latest = deps.installed_app(root), deps.latest_app()
            st["latest"] = latest
            app_update = False
            if inst and (not latest or inst.get("sha") == latest["sha"]):
                self._report("app", True, f"Instalada · versión {inst.get('sha', '')[:7]} ({inst.get('date', '')})")
            elif inst:
                app_update = True
                self._row("app", "⟳", WARN, "Actualizar",
                          f"Nueva versión: {inst.get('sha', '')[:7]} → {latest['sha'][:7]} · {latest['message']}")
            else:
                extra = f" · {latest['sha'][:7]} ({latest['date']})" if latest else ""
                self._report("app", False, None, f"Se descargará la última versión{extra}")
            libs = deps.libs_ok(root) if inst else None
            if libs and not app_update:
                self._report("libs", True, libs)
            elif libs:
                self._row("libs", "⟳", WARN, "Actualizar", "Se revisarán junto con la nueva versión")
            else:
                self._report("libs", False, None)
            st["missing"] = [k for k, ok in (("python", py), ("ffmpeg", ff), ("js", js),
                                             ("app", inst and not app_update), ("libs", libs and not app_update))
                             if not ok]
            self.events.put(("detected", st))
        self._thread(work)

    def _report(self, key, ok, detail, missing_text=None):
        size = self.rows[key]["size"]
        if ok:
            self._row(key, "✓", OK, "Instalado", detail)
        else:
            self._row(key, "⬇", WARN, f"Falta · {size}", missing_text or "No encontrado: se instalará")

    def _install(self):
        root = self.root_dir
        missing = list(self.found["missing"])
        self._last_installed = missing
        self.btn_next.configure(text="Instalando...", state="disabled")

        def work():
            os.makedirs(root, exist_ok=True)
            steps = {
                "python": lambda: deps.install_python(root, self.ctx),
                "ffmpeg": lambda: deps.install_ffmpeg(root, self.ctx),
                "js": lambda: deps.install_deno(root, self.ctx),
                "app": lambda: deps.install_app(root, self.ctx, self.found.get("latest")),
                "libs": lambda: deps.install_libs(root, self._python(root), self.ctx),
            }
            for key, *_ in COMPONENTS:
                if key not in missing:
                    continue
                self.ctx.check()
                self._row(key, "⟳", ACCENT, "Instalando...", None)
                try:
                    steps[key]()
                except deps.Aborted:
                    raise
                except Exception as exc:  # noqa: BLE001
                    self.events.put(("log", traceback.format_exc()))
                    self._row(key, "✗", BAD, "Error", str(exc)[:200])
                    self.events.put(("failed", key))
                    return
                self._row(key, "✓", OK, "Listo", None)
            self.events.put(("installed", None))
        self._thread(work)

    def _python(self, root):
        py = deps.find_python(root)
        if not py:
            raise RuntimeError("No se encontró Python después de instalarlo. Reinicia el instalador.")
        return py[1]

    def _finalize(self):
        root = self.root_dir
        self.btn_next.configure(text="Terminando...", state="disabled")
        desktop = bool(self.chk_desktop.get()) if not self.update_mode else False
        start = bool(self.chk_start.get()) if not self.update_mode else False

        def work():
            self.events.put(("progress", (None, "Creando accesos directos...")))
            deps.copy_self(root)
            if desktop or start:
                deps.create_shortcuts(root, desktop, start, self.ctx)
            deps.register(root)
            self.events.put(("finalized", None))
        self._thread(work)

    # ------------------------------------------------------------------ eventos
    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                self._handle(kind, data)
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _handle(self, kind, data):
        if kind == "log":
            self.log_box.configure(state="normal")
            self.log_box.insert("end", str(data).rstrip() + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        elif kind == "progress":
            frac, text = data
            if frac is None:
                if self.bar.cget("mode") != "indeterminate":
                    self.bar.configure(mode="indeterminate")
                    self.bar.start()
            else:
                if self.bar.cget("mode") != "determinate":
                    self.bar.stop()
                    self.bar.configure(mode="determinate")
                self.bar.set(frac)
            self.prog_lbl.configure(text=text)
        elif kind == "row":
            key, icon, color, status, detail = data
            r = self.rows[key]
            r["icon"].configure(text=icon, text_color=color)
            r["status"].configure(text=status, text_color=color)
            r["detail"].configure(text=detail if detail else r["desc"], text_color=BAD if color == BAD else MUTED)
        elif kind == "detected":
            self.found = data
            self._stop_bar()
            if data["missing"] and data["missing"] == getattr(self, "_last_installed", None):
                # Se instaló pero sigue sin detectarse: no repetir en bucle
                names = [n for k, n, *_ in COMPONENTS if k in data["missing"]]
                self.comp_sub.configure(text="No se pudo verificar: " + ", ".join(names) +
                                             ". Revisa los detalles o reinicia el instalador.")
                self.btn_next.configure(text="Reintentar", state="normal")
                self._last_installed = None
                if not self.log_box.winfo_ismapped():
                    self._toggle_log()
                return
            if data["missing"]:
                names = [n for k, n, *_ in COMPONENTS if k in data["missing"]]
                self.comp_sub.configure(text="Falta: " + ", ".join(names) + ". Se descargará e instalará.")
                self.prog_lbl.configure(text="Listo para instalar.")
                self.btn_next.configure(text="Instalar", state="normal")
                if self.update_mode:
                    self.after(400, self._next)
            else:
                self.comp_sub.configure(text="Todo está instalado y al día.")
                self.prog_lbl.configure(text="")
                self.btn_next.configure(text="Siguiente  ›", state="normal")
                if self.update_mode:
                    self.after(400, self._next)
        elif kind == "installed":
            self.events.put(("progress", (1.0, "Componentes instalados. Verificando...")))
            self._stop_bar(1.0)
            self.after(300, lambda: self.show(2))  # vuelve a detectar: así hasta que no falte nada
        elif kind == "finalized":
            self._stop_bar(1.0)
            self.done_title.configure(text="¡Actualización completada!" if self.update_mode
                                      else "¡Instalación completada!")
            self.done_sub.configure(text=f"{deps.APP_NAME} quedó instalado en\n{self.root_dir}\n\n"
                                         "Puedes desinstalarlo desde Configuración › Aplicaciones.")
            self.show(3)
        elif kind == "failed":
            self._stop_bar(0)
            self.comp_sub.configure(text="Hubo un problema. Revisa los detalles y vuelve a intentarlo.")
            self.prog_lbl.configure(text="")
            self.btn_next.configure(text="Reintentar", state="normal")
            if not self.log_box.winfo_ismapped():
                self._toggle_log()
        elif kind == "aborted":
            self._stop_bar(0)
            self.prog_lbl.configure(text="Cancelado.")
            self.btn_next.configure(text="Reintentar", state="normal")
        elif kind == "fatal":
            self._stop_bar(0)
            messagebox.showerror(deps.APP_NAME, f"Error inesperado:\n{data}")
            self.btn_next.configure(text="Reintentar", state="normal")
        elif kind == "idle":
            self.busy = False
            if self.page in (1, 2) and not self.update_mode:
                self.btn_back.configure(state="normal")

    def _stop_bar(self, value=0.0):
        self.bar.stop()
        self.bar.configure(mode="determinate")
        self.bar.set(value)


def do_uninstall() -> None:
    root_dir = deps.registered_dir() or os.path.dirname(os.path.abspath(sys.executable))
    tk = ctk.CTk()
    tk.withdraw()
    if not deps.is_our_install(root_dir):
        messagebox.showerror(deps.APP_NAME, f"No se encontró una instalación en:\n{root_dir}")
        return
    if messagebox.askyesno(deps.APP_NAME, f"¿Desinstalar {deps.APP_NAME}?\n\nSe eliminará:\n{root_dir}\n\n"
                                          "Tus archivos descargados y convertidos no se tocan."):
        deps.uninstall(root_dir)
        messagebox.showinfo(deps.APP_NAME, "La app se desinstaló correctamente.")
    tk.destroy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--dir")
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    if args.uninstall:
        do_uninstall()
        return
    Wizard(update_dir=args.dir if args.update else None).mainloop()


if __name__ == "__main__":
    main()
