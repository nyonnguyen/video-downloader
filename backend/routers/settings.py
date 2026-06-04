from fastapi import APIRouter

from backend.schemas import SettingsResponse
from backend.settings import settings
from core.ffmpeg_service import find_ffmpeg


router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
def get_settings():
    ffmpeg_path = find_ffmpeg()
    return SettingsResponse(
        downloads_dir=settings.downloads_dir,
        browser=settings.browser,
        timeout=settings.timeout,
        whisper_default_model=settings.whisper_default_model,
        ffmpeg_available=ffmpeg_path is not None,
        ffmpeg_path=ffmpeg_path,
    )
