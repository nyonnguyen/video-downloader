from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from backend.db import engine
from backend.models_db import Download, Task
from backend.queue import get_log_lines, queue
from backend.schemas import TaskResponse


router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(status: Optional[str] = None, limit: int = 100):
    with Session(engine) as s:
        stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
        if status:
            stmt = select(Task).where(Task.status == status).order_by(Task.created_at.desc()).limit(limit)
        return s.exec(stmt).all()


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            raise HTTPException(404, "task not found")
        return t


@router.get("/tasks/{task_id}/log")
def get_task_log(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            raise HTTPException(404, "task not found")
    return {"task_id": task_id, "lines": get_log_lines(task_id)}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            raise HTTPException(404, "task not found")
        if t.status == "running":
            # Will be finalized as cancelled by the worker.
            queue.request_cancel(task_id)
        elif t.status == "pending":
            # Worker hasn't picked it up yet — flip it directly so the queue skips it.
            t.status = "cancelled"
            t.message = "Cancelled"
            s.add(t)
            s.commit()
        else:
            raise HTTPException(400, f"cannot cancel a {t.status} task")
    return {"ok": True}


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            raise HTTPException(404, "task not found")
        if t.status == "running":
            queue.request_cancel(task_id, pause=True)
        elif t.status == "pending":
            t.status = "paused"
            t.message = "Paused"
            s.add(t)
            s.commit()
        else:
            raise HTTPException(400, f"cannot pause a {t.status} task")
    return {"ok": True}


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            raise HTTPException(404, "task not found")
        if t.status != "paused":
            raise HTTPException(400, "task is not paused")
        t.status = "pending"
        t.progress = 0.0
        t.message = "Resumed"
        t.error = None
        t.started_at = None
        t.finished_at = None
        s.add(t)
        s.commit()
    await queue.enqueue(task_id)
    return {"ok": True}


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            raise HTTPException(404, "task not found")
        if t.status not in ("error", "cancelled", "paused"):
            raise HTTPException(400, "task is not in a retryable state")
        t.status = "pending"
        t.progress = 0.0
        t.message = "Re-queued"
        t.error = None
        t.started_at = None
        t.finished_at = None
        s.add(t)
        s.commit()
    await queue.enqueue(task_id)
    return {"ok": True}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    with Session(engine) as s:
        t = s.exec(select(Task).where(Task.id == task_id)).first()
        if not t:
            raise HTTPException(404, "task not found")
        if t.status == "running":
            raise HTTPException(400, "cancel before delete")
        # Remove dependent Download row first — FK(task_id) prevents deleting the Task otherwise.
        for dl in s.exec(select(Download).where(Download.task_id == task_id)).all():
            s.delete(dl)
        s.delete(t)
        s.commit()
    return {"ok": True}
