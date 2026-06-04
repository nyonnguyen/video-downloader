import json
import uuid

from fastapi import APIRouter
from sqlmodel import Session

from backend.db import engine
from backend.models_db import Task
from backend.queue import queue
from backend.schemas import CreateDownloadRequest, TaskIdResponse


router = APIRouter(prefix="/api", tags=["downloads"])


@router.post("/downloads", response_model=TaskIdResponse)
async def create_download(req: CreateDownloadRequest):
    task_id = str(uuid.uuid4())
    payload = req.model_dump(exclude_none=True)
    with Session(engine) as s:
        s.add(Task(
            id=task_id,
            type="download",
            status="pending",
            payload_json=json.dumps(payload),
            message="Queued",
        ))
        s.commit()
    await queue.enqueue(task_id)
    return TaskIdResponse(task_id=task_id)
