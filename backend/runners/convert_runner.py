import os
from threading import Event
from typing import Callable

from sqlmodel import Session, select

from backend.db import engine
from backend.models_db import MediaFile
from backend.queue import register_runner
from backend.settings import settings
from core.ffmpeg_service import convert
from core.library_service import register_media_file
from core.presets import PRESETS
from utils.logging import get_logger

logger = get_logger("convert_runner")


@register_runner("convert")
def run(task_id: str, payload: dict, progress_cb: Callable[[float, str], None], cancel_event: Event) -> dict:
    media_id = payload["media_file_id"]
    preset_id = payload["preset_id"]

    preset = PRESETS.get(preset_id)
    if preset is None:
        raise ValueError(f"unknown preset_id: {preset_id}")

    with Session(engine) as s:
        src = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
    if src is None:
        raise FileNotFoundError(f"media_file {media_id} not in DB")
    if not os.path.exists(src.path):
        raise FileNotFoundError(src.path)

    base = os.path.splitext(src.filename)[0]
    dst_path = os.path.join(settings.converted_dir, f"{base}__{preset.id}.{preset.container}")

    convert(src.path, dst_path, preset_id, progress_cb=progress_cb, cancel_event=cancel_event)

    new_id = register_media_file(
        dst_path,
        kind="audio" if preset.container in ("mp3", "wav", "m4a", "flac") else "video",
        source_url=src.source_url,
        parent_id=src.id,
    )
    return {"media_file_id": new_id}
