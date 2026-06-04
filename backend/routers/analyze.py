import asyncio

import yt_dlp
from fastapi import APIRouter, HTTPException

from backend.schemas import AnalyzeRequest, AnalyzeResponse
from core.source_detector import detect_source, get_app_config
from utils.logging import get_logger

logger = get_logger("analyze")
router = APIRouter(prefix="/api", tags=["analyze"])


YT_DLP_SOURCES = {"youtube", "generic"}


def _probe_with_yt_dlp(url: str) -> dict:
    # `process=False` skips format selection — we only need metadata.
    # `noplaylist=True` so a `watch?v=X&list=RD...` Mix URL probes the single video,
    # not the Mix playlist (which would return the wrong title/thumbnail).
    with yt_dlp.YoutubeDL({
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }) as ydl:
        return ydl.extract_info(url, download=False, process=False) or {}


def _quality_options(source: str, info: dict) -> tuple[list[str], str]:
    if source == "youtube" or source == "generic":
        # Static quality choices that map to YouTubeQuality enum names
        choices = ["BEST", "HIGH_1080P", "MEDIUM_720P", "LOW_480P", "HIGH_4K", "AUDIO_ONLY", "AUDIO_MP3"]
        return choices, "HIGH_1080P"
    # ixigua/douyin/tiktok use string resolution
    choices = ["AUTO", "P360", "P480", "P720", "P1080"]
    suggested = get_app_config(source).get("resolution", "AUTO")
    return choices, suggested


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "url must be http(s)://...")

    source = detect_source(req.url)
    qualities, suggested = _quality_options(source, {})

    # For yt-dlp-backed sources we can probe quickly for title/duration/thumbnail
    title = None
    duration = None
    thumbnail = None
    if source in YT_DLP_SOURCES:
        try:
            info = await asyncio.to_thread(_probe_with_yt_dlp, req.url)
            title = info.get("title")
            duration = info.get("duration")
            thumbnail = info.get("thumbnail")
        except Exception as e:
            logger.warning("yt-dlp probe failed: %s", e)

    return AnalyzeResponse(
        source=source,
        title=title,
        thumbnail=thumbnail,
        duration=duration,
        available_qualities=qualities,
        suggested_quality=suggested,
    )
