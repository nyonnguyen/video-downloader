from threading import Event
from typing import Callable, Optional

from sqlmodel import Session, select

from backend.db import engine
from backend.models_db import Download
from backend.queue import register_runner
from backend.settings import settings
from core.download_manager import build_options, run_download
from core.library_service import register_media_file
from core.source_detector import detect_source
from utils.logging import get_logger

logger = get_logger("download_runner")


@register_runner("download")
def run(
    task_id: str,
    payload: dict,
    progress_cb: Callable[[float, str], None],
    cancel_event: Event,
    log_cb: Optional[Callable[[str, str], None]] = None,
) -> dict:
    url: str = payload["url"]
    quality = payload.get("quality")
    source = detect_source(url)
    if log_cb:
        log_cb(f"Detected source={source}, quality={quality or 'default'}", "info")
        log_cb(f"URL: {url}", "info")

    options = build_options(
        url=url,
        browser=settings.browser,
        timeout=settings.timeout,
        quality_override=quality,
    )

    # Persist a Download row up-front
    with Session(engine) as s:
        existing = s.exec(select(Download).where(Download.task_id == task_id)).first()
        if not existing:
            s.add(Download(
                id=task_id,  # reuse task_id for simplicity
                task_id=task_id,
                url=url,
                source=source,
                requested_quality=quality,
            ))
            s.commit()

    output_file = run_download(
        options=options,
        output_path=settings.downloads_dir,
        progress_cb=progress_cb,
        cancel_event=cancel_event,
        log_cb=log_cb,
    )

    if not output_file:
        if cancel_event.is_set():
            return {}
        raise RuntimeError("download produced no file")

    media_id = register_media_file(output_file, kind="video", source_url=url)

    with Session(engine) as s:
        dl = s.exec(select(Download).where(Download.task_id == task_id)).first()
        if dl:
            dl.title = options.video_title
            dl.media_file_id = media_id
            s.add(dl)
            s.commit()

    return {"media_file_id": media_id}
