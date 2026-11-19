"""Cola de trabajos en segundo plano.

Los hilos de trabajo NUNCA tocan la interfaz: publican eventos en una
queue.Queue que la ventana principal consume desde el hilo de Tk.
"""
from __future__ import annotations

import itertools
import queue
import threading
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

PENDING, RUNNING, DONE, ERROR, CANCELLED = "pending", "running", "done", "error", "cancelled"


class Cancelled(Exception):
    """Se lanza dentro de un trabajo cuando el usuario lo cancela."""


@dataclass
class Job:
    kind: str                      # "download" | "convert"
    title: str
    work: Callable[["JobContext"], Optional[str]]  # devuelve la ruta de salida
    subtitle: str = ""
    id: int = field(default_factory=itertools.count(1).__next__)
    status: str = PENDING
    cancel_event: threading.Event = field(default_factory=threading.Event)


class JobContext:
    def __init__(self, job: Job, events: "queue.Queue") -> None:
        self.job = job
        self._events = events

    @property
    def cancelled(self) -> bool:
        return self.job.cancel_event.is_set()

    def check_cancel(self) -> None:
        if self.cancelled:
            raise Cancelled()

    def update(self, **fields) -> None:
        """Campos admitidos: progress (0-1 o None=indeterminado), message, title, subtitle, output."""
        self._events.put((self.job.id, fields))


class JobQueue:
    def __init__(self, events: "queue.Queue", workers: int = 1, log: Callable[[str], None] | None = None):
        self._q: "queue.Queue[Job]" = queue.Queue()
        self._events = events
        self._log = log or (lambda _m: None)
        self._workers: list[threading.Thread] = []
        self._target = 0
        self._lock = threading.Lock()
        self.set_workers(workers)

    def set_workers(self, n: int) -> None:
        with self._lock:
            self._target = max(1, int(n))
            while len(self._workers) < self._target:
                t = threading.Thread(target=self._loop, daemon=True)
                self._workers.append(t)
                t.start()

    def submit(self, job: Job) -> Job:
        self._events.put((job.id, {"status": PENDING, "message": "En cola"}))
        self._q.put(job)
        return job

    def _loop(self) -> None:
        me = threading.current_thread()
        while True:
            job = self._q.get()
            try:
                self._run(job)
            finally:
                self._q.task_done()
            with self._lock:  # reduce hilos si el usuario bajó el paralelismo
                if len(self._workers) > self._target:
                    self._workers.remove(me)
                    return

    def _run(self, job: Job) -> None:
        if job.cancel_event.is_set():
            self._events.put((job.id, {"status": CANCELLED, "message": "Cancelado"}))
            return
        ctx = JobContext(job, self._events)
        job.status = RUNNING
        ctx.update(status=RUNNING, message="Iniciando...", progress=None)
        try:
            out = job.work(ctx)
            if job.cancel_event.is_set():
                raise Cancelled()
            job.status = DONE
            ctx.update(status=DONE, progress=1.0, message="Completado", output=out or "")
        except Cancelled:
            job.status = CANCELLED
            ctx.update(status=CANCELLED, message="Cancelado")
        except Exception as exc:  # noqa: BLE001 - mostramos cualquier error al usuario
            job.status = ERROR
            self._log(f"[{job.title}] {traceback.format_exc()}")
            ctx.update(status=ERROR, message=str(exc) or exc.__class__.__name__)
