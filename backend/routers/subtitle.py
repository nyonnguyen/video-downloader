import json
import uuid

from fastapi import APIRouter
from sqlmodel import Session

from backend.db import engine
from backend.models_db import Task
from backend.queue import queue
from backend.schemas import CreateSubtitleRequest, TaskIdResponse, WhisperModelInfo
from core.subtitle_service import WHISPER_MODELS, is_model_installed


router = APIRouter(prefix="/api", tags=["subtitle"])


@router.get("/subtitle/models", response_model=list[WhisperModelInfo])
def get_models():
    return [
        WhisperModelInfo(name=name, size_mb=size, installed=is_model_installed(name))
        for name, size in WHISPER_MODELS.items()
    ]


@router.post("/subtitle", response_model=TaskIdResponse)
async def create_subtitle(req: CreateSubtitleRequest):
    task_id = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(Task(
            id=task_id,
            type="subtitle",
            status="pending",
            payload_json=json.dumps(req.model_dump()),
            message="Queued",
        ))
        s.commit()
    await queue.enqueue(task_id)
    return TaskIdResponse(task_id=task_id)
