import json
import uuid
from typing import Optional

from fastapi import APIRouter
from sqlmodel import Session

from backend.db import engine
from backend.models_db import Task
from backend.queue import queue
from backend.schemas import CreateVoiceRequest, TaskIdResponse, VoiceInfoResponse
from core.voice_service import list_voices


router = APIRouter(prefix="/api", tags=["voice"])

_voices_cache: Optional[list] = None


@router.get("/voice/voices", response_model=list[VoiceInfoResponse])
def get_voices():
    global _voices_cache
    if _voices_cache is None:
        _voices_cache = [
            VoiceInfoResponse(
                short_name=v.short_name,
                locale=v.locale,
                gender=v.gender,
                display_name=v.display_name,
            )
            for v in list_voices()
        ]
    return _voices_cache


@router.post("/voice", response_model=TaskIdResponse)
async def create_voice(req: CreateVoiceRequest):
    task_id = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(Task(
            id=task_id,
            type="voice",
            status="pending",
            payload_json=json.dumps(req.model_dump()),
            message="Queued",
        ))
        s.commit()
    await queue.enqueue(task_id)
    return TaskIdResponse(task_id=task_id)
