import os
from threading import Event
from typing import Callable

from sqlmodel import Session, select

from backend.db import engine
from backend.models_db import MediaFile
from backend.queue import register_runner
from backend.settings import settings
from core.library_service import register_media_file
from core.subtitle_service import (
    burn_subtitle_to_video,
    soft_embed_subtitle,
    srt_to_vtt,
    transcribe_to_srt,
)
from utils.logging import get_logger

logger = get_logger("subtitle_runner")


@register_runner("subtitle")
def run(task_id: str, payload: dict, progress_cb: Callable[[float, str], None], cancel_event: Event) -> dict:
    media_id = payload["media_file_id"]
    model = payload.get("model", "small")
    language = payload.get("language")
    translate_to_en = payload.get("translate_to_en", False)
    embed_soft = payload.get("embed_soft", False)  # opt-in: only mux when user asks
    burn_in = payload.get("burn_in", False)

    with Session(engine) as s:
        src = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
    if src is None or not os.path.exists(src.path):
        raise FileNotFoundError(media_id)

    base = os.path.splitext(src.filename)[0]
    lang_tag = "en" if translate_to_en else (language or "auto")
    srt_dir = settings.subtitles_dir
    os.makedirs(srt_dir, exist_ok=True)
    out_srt = os.path.join(srt_dir, f"{base}.{lang_tag}.srt")

    srt_path, detected_lang = transcribe_to_srt(
        src.path, out_srt,
        model_name=model,
        language=language,
        translate_to_en=translate_to_en,
        progress_cb=progress_cb,
        cancel_event=cancel_event,
    )
    if not srt_path:
        return {}

    # Always emit a sibling .vtt for browser <track> playback
    try:
        srt_to_vtt(srt_path)
    except Exception as e:
        logger.warning("VTT generation failed: %s", e)

    srt_id = register_media_file(srt_path, kind="subtitle", source_url=src.source_url, parent_id=src.id)

    primary_id = srt_id

    if embed_soft:
        progress_cb(0.96, "Embedding subtitle track into video…")
        embedded = os.path.join(settings.converted_dir, f"{base}__softsub.mp4")
        embed_lang = detected_lang or lang_tag or "und"
        soft_embed_subtitle(src.path, srt_path, embedded, language=embed_lang, title=f"Whisper {model}")
        embedded_id = register_media_file(embedded, kind="video", source_url=src.source_url, parent_id=src.id)
        primary_id = embedded_id

    if burn_in:
        progress_cb(0.98, "Burning subtitle into video (hard)…")
        burned = os.path.join(settings.converted_dir, f"{base}__burned.mp4")
        burn_subtitle_to_video(src.path, srt_path, burned)
        primary_id = register_media_file(burned, kind="video", source_url=src.source_url, parent_id=src.id)

    return {"media_file_id": primary_id}
