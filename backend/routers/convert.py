import json
import uuid

from fastapi import APIRouter
from sqlmodel import Session

from backend.db import engine
from backend.models_db import Task
from backend.queue import queue
from backend.schemas import ConvertPreset, CreateConvertRequest, TaskIdResponse
from core.presets import list_presets


router = APIRouter(prefix="/api", tags=["convert"])


@router.get("/convert/presets", response_model=list[ConvertPreset])
def get_presets():
    return [
        ConvertPreset(
            id=p.id, label=p.label, container=p.container,
            vcodec=p.vcodec, acodec=p.acodec, description=p.description,
        )
        for p in list_presets()
    ]


@router.post("/convert", response_model=TaskIdResponse)
async def create_convert(req: CreateConvertRequest):
    task_id = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(Task(
            id=task_id,
            type="convert",
            status="pending",
            payload_json=json.dumps(req.model_dump()),
            message="Queued",
        ))
        s.commit()
    await queue.enqueue(task_id)
    return TaskIdResponse(task_id=task_id)
