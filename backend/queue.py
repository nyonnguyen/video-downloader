import asyncio
import json
import time
from collections import deque
from datetime import datetime
from threading import Event
from typing import Optional

from sqlmodel import Session, select

from backend.db import engine
from backend.models_db import Task
from backend.ws import manager
from utils.logging import get_logger

logger = get_logger("queue")

# Filled in by runners module to avoid circular imports
RUNNERS: dict[str, "callable"] = {}

# In-memory log buffer per task — capped to avoid unbounded growth.
LOG_BUFFER_LIMIT = 500
_LOG_BUFFERS: dict[str, deque] = {}


def register_runner(task_type: str):
    def deco(fn):
        RUNNERS[task_type] = fn
        return fn
    return deco


def get_log_lines(task_id: str) -> list[str]:
    """Return buffered log lines for a task. Falls back to persisted Task.log."""
    buf = _LOG_BUFFERS.get(task_id)
    if buf is not None:
        return list(buf)
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if t and t.log:
            return t.log.splitlines()
    return []


def _append_log(task_id: str, line: str):
    buf = _LOG_BUFFERS.setdefault(task_id, deque(maxlen=LOG_BUFFER_LIMIT))
    buf.append(line)


class TaskQueue:
    def __init__(self, concurrency: int = 2):
        self._q: asyncio.Queue[str] = asyncio.Queue()
        self._cancel_events: dict[str, Event] = {}
        # Mark whether a cancel was issued by a user "pause" — finalizer
        # converts cancelled → paused so the row can be resumed later.
        self._pause_flags: set[str] = set()
        self._workers: list[asyncio.Task] = []
        self._concurrency = concurrency
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def enqueue(self, task_id: str):
        await self._q.put(task_id)

    def request_cancel(self, task_id: str, pause: bool = False):
        if pause:
            self._pause_flags.add(task_id)
        ev = self._cancel_events.get(task_id)
        if ev:
            ev.set()

    def is_running(self, task_id: str) -> bool:
        return task_id in self._cancel_events

    async def start(self):
        self._loop = asyncio.get_running_loop()
        # Recover from previous process: any "running" rows are orphans —
        # their cancel events died with the worker. Reset to pending.
        recovered = _reset_orphaned_tasks()
        for tid in recovered:
            await self._q.put(tid)
        # Re-enqueue tasks that were sitting in pending when the process died.
        for tid in _list_pending_task_ids():
            if tid not in recovered:
                await self._q.put(tid)

        for i in range(self._concurrency):
            t = asyncio.create_task(self._worker(i))
            self._workers.append(t)
        logger.info(
            "Queue started with %s workers (recovered %s, pending %s)",
            self._concurrency,
            len(recovered),
            self._q.qsize() - len(recovered),
        )

    async def stop(self):
        for t in self._workers:
            t.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    # ---- broadcasting helpers ----

    def log(self, task_id: str, message: str, level: str = "info"):
        """Append a log line, persist, and broadcast to listeners."""
        ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        line = f"[{ts}] {level.upper()} {message}"
        _append_log(task_id, line)
        _persist_log(task_id, line)
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({
                "type": "log",
                "task_id": task_id,
                "level": level,
                "message": message,
                "line": line,
                "ts": time.time(),
            }),
            self._loop,
        )

    def _progress_callback(self, task_id: str):
        last_emit = [0.0]
        last_message = [""]

        def cb(progress: float, message: str):
            now = time.time()
            # Always log when the message text changes so the user sees
            # phase transitions ("Downloading" -> "Merging…") in the modal.
            if message and message != last_message[0]:
                last_message[0] = message
                self.log(task_id, f"{message} ({progress*100:.1f}%)")
            # Throttle progress DB writes / WS to ~5 Hz.
            if now - last_emit[0] < 0.2 and progress < 1.0:
                return
            last_emit[0] = now
            _update_task(task_id, progress=progress, message=message)
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "progress",
                    "task_id": task_id,
                    "status": "running",
                    "progress": progress,
                    "message": message,
                    "ts": now,
                }),
                self._loop,
            )
        return cb

    async def _worker(self, idx: int):
        while True:
            try:
                task_id = await self._q.get()
            except asyncio.CancelledError:
                return
            try:
                task = _get_task(task_id)
                if task is None:
                    continue
                # Task may have been deleted/paused while waiting in the queue.
                if task.status not in ("pending",):
                    self.log(task_id, f"skipped (status={task.status})")
                    continue
                runner = RUNNERS.get(task.type)
                if runner is None:
                    msg = f"No runner for type {task.type}"
                    self.log(task_id, msg, level="error")
                    _finish_task(task_id, status="error", error=msg)
                    await manager.broadcast({"type": "error", "task_id": task_id, "error": msg})
                    continue

                cancel_ev = Event()
                self._cancel_events[task_id] = cancel_ev
                _mark_started(task_id)
                self.log(task_id, f"Worker #{idx} picked up task ({task.type})")
                await manager.broadcast({"type": "progress", "task_id": task_id, "status": "running", "progress": 0.0, "message": "Starting", "ts": time.time()})

                payload = json.loads(task.payload_json or "{}")
                progress_cb = self._progress_callback(task_id)
                log_cb = lambda msg, level="info", _tid=task_id: self.log(_tid, msg, level=level)
                run_exc: Optional[BaseException] = None
                result: Optional[dict] = None
                try:
                    result = await asyncio.to_thread(runner, task_id, payload, progress_cb, cancel_ev, log_cb)
                except TypeError:
                    # Older runners signed for (task_id, payload, progress_cb, cancel_event) only.
                    try:
                        result = await asyncio.to_thread(runner, task_id, payload, progress_cb, cancel_ev)
                    except Exception as e:
                        run_exc = e
                except Exception as e:
                    run_exc = e

                if cancel_ev.is_set():
                    # A cancel was requested. Some runners cooperate quietly (return None),
                    # others raise (e.g. yt-dlp DownloadError("cancelled")) — both land here.
                    paused = task_id in self._pause_flags
                    final = "paused" if paused else "cancelled"
                    self.log(task_id, f"Task {final}")
                    _finish_task(task_id, status=final)
                    await manager.broadcast({"type": "error", "task_id": task_id, "status": final, "error": final})
                elif run_exc is not None:
                    logger.exception("Task %s failed: %s", task_id, run_exc)
                    self.log(task_id, f"Failed: {run_exc}", level="error")
                    _finish_task(task_id, status="error", error=str(run_exc))
                    await manager.broadcast({"type": "error", "task_id": task_id, "error": str(run_exc)})
                else:
                    self.log(task_id, "Task completed")
                    _finish_task(task_id, status="done", media_file_id=(result or {}).get("media_file_id"))
                    await manager.broadcast({
                        "type": "done",
                        "task_id": task_id,
                        "media_file_id": (result or {}).get("media_file_id"),
                    })
                self._cancel_events.pop(task_id, None)
                self._pause_flags.discard(task_id)
            except Exception:
                logger.exception("Worker %s crash", idx)


queue = TaskQueue()


# ---- DB helpers (run synchronously inside event loop; SQLite is fast enough) ----

def _get_task(task_id: str) -> Optional[Task]:
    with Session(engine) as s:
        return s.exec(select(Task).where(Task.id == task_id)).first()


def _list_pending_task_ids() -> list[str]:
    with Session(engine) as s:
        return [t.id for t in s.exec(select(Task).where(Task.status == "pending").order_by(Task.created_at)).all()]


def _reset_orphaned_tasks() -> list[str]:
    """Reset any 'running' rows left by a crashed previous process. Returns recovered ids."""
    recovered: list[str] = []
    with Session(engine) as s:
        rows = s.exec(select(Task).where(Task.status == "running")).all()
        for t in rows:
            t.status = "pending"
            t.progress = 0.0
            t.message = "Recovered from restart"
            t.started_at = None
            log_line = f"[{datetime.utcnow().isoformat(timespec='seconds')}Z] INFO Recovered from restart, re-queued"
            t.log = (t.log + "\n" + log_line) if t.log else log_line
            s.add(t)
            recovered.append(t.id)
        s.commit()
    return recovered


def _mark_started(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if t:
            t.status = "running"
            t.started_at = datetime.utcnow()
            s.add(t)
            s.commit()


def _update_task(task_id: str, progress: float, message: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if t:
            t.progress = progress
            t.message = message
            s.add(t)
            s.commit()


def _persist_log(task_id: str, line: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            return
        existing = t.log or ""
        merged = (existing + "\n" + line) if existing else line
        # Keep only the last LOG_BUFFER_LIMIT lines on disk too.
        lines = merged.splitlines()
        if len(lines) > LOG_BUFFER_LIMIT:
            lines = lines[-LOG_BUFFER_LIMIT:]
        t.log = "\n".join(lines)
        s.add(t)
        s.commit()


def _finish_task(task_id: str, status: str, error: Optional[str] = None, media_file_id: Optional[str] = None):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if t:
            t.status = status
            t.error = error
            t.finished_at = datetime.utcnow()
            t.progress = 1.0 if status == "done" else t.progress
            if media_file_id:
                t.media_file_id = media_file_id
            s.add(t)
            s.commit()
