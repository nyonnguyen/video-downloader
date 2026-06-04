"""ffprobe-backed media metadata + thumbnail extraction."""
import json
import os
import shutil
import subprocess
import uuid
from typing import Optional

from sqlmodel import Session

from backend.db import engine
from backend.models_db import MediaFile
from backend.settings import settings
from utils.logging import get_logger

logger = get_logger("library")


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def find_ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")


def probe(path: str) -> dict:
    """Return ffprobe JSON for the file, or {} if ffprobe missing / file unreadable."""
    ffprobe = find_ffprobe()
    if not ffprobe or not os.path.exists(path):
        return {}
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout or "{}")
    except Exception:
        logger.exception("ffprobe failed for %s", path)
        return {}


def make_thumbnail(video_path: str, out_path: str, timestamp: str = "00:00:03") -> Optional[str]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg or not os.path.exists(video_path):
        return None
    try:
        subprocess.run(
            [ffmpeg, "-y", "-ss", timestamp, "-i", video_path, "-frames:v", "1", "-q:v", "3", out_path],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return out_path if os.path.exists(out_path) else None
    except Exception:
        logger.exception("thumbnail failed for %s", video_path)
        return None


def _extract_stream(info: dict, kind: str) -> dict:
    for s in info.get("streams", []) or []:
        if s.get("codec_type") == kind:
            return s
    return {}


def register_media_file(
    path: str,
    kind: str = "video",
    source_url: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> str:
    """Probe a file, insert MediaFile row, generate thumbnail. Returns media_file_id."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    info = probe(path)
    fmt = info.get("format", {}) if info else {}
    vstream = _extract_stream(info, "video")
    astream = _extract_stream(info, "audio")

    media_id = str(uuid.uuid4())
    container = (fmt.get("format_name", "") or os.path.splitext(path)[1].lstrip(".")).split(",")[0]
    duration = float(fmt.get("duration")) if fmt.get("duration") else None
    size = int(fmt.get("size") or os.path.getsize(path))

    thumb_path = None
    if kind == "video" and find_ffmpeg():
        thumb_dir = os.path.join(settings.data_dir, "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = make_thumbnail(path, os.path.join(thumb_dir, f"{media_id}.jpg"))

    mf = MediaFile(
        id=media_id,
        path=path,
        filename=os.path.basename(path),
        size_bytes=size,
        duration_sec=duration,
        container=container,
        vcodec=vstream.get("codec_name"),
        acodec=astream.get("codec_name"),
        width=vstream.get("width"),
        height=vstream.get("height"),
        thumbnail_path=thumb_path,
        parent_id=parent_id,
        kind=kind,
        source_url=source_url,
    )
    with Session(engine) as s:
        s.add(mf)
        s.commit()
    logger.info("Registered MediaFile %s (%s)", media_id, path)
    return media_id
