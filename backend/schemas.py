from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    url: str


class AnalyzeResponse(BaseModel):
    source: str
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    available_qualities: list[str] = []
    suggested_quality: Optional[str] = None


class CreateDownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = None
    audio_only: bool = False
    playlist_limit: Optional[int] = None
    # Optional metadata supplied by the client (after Analyze) — persisted in the task
    # payload so the UI can show a meaningful placeholder while the download runs.
    title: Optional[str] = None
    thumbnail: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    type: str
    status: str
    progress: float
    message: str
    error: Optional[str] = None
    media_file_id: Optional[str] = None
    payload_json: str = "{}"
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class MediaFileResponse(BaseModel):
    id: str
    path: str
    filename: str
    size_bytes: int
    duration_sec: Optional[float] = None
    container: str
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail_path: Optional[str] = None
    kind: str
    parent_id: Optional[str] = None
    source_url: Optional[str] = None
    archived_at: Optional[datetime] = None
    created_at: datetime


class SubtitleCueDTO(BaseModel):
    index: int
    start_sec: float
    end_sec: float
    text: str


class SubtitleCuesResponse(BaseModel):
    media_file_id: str
    cues: list[SubtitleCueDTO]


class UpdateSubtitleCuesRequest(BaseModel):
    cues: list[SubtitleCueDTO]


class TranslateSubtitleRequest(BaseModel):
    target_language: str
    source_language: Optional[str] = None
    save_as_new: bool = True


class CreateConvertRequest(BaseModel):
    media_file_id: str
    preset_id: str


class ConvertPreset(BaseModel):
    id: str
    label: str
    container: str
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    description: str = ""


class CreateSubtitleRequest(BaseModel):
    media_file_id: str
    model: str = "small"
    language: Optional[str] = None  # None = auto-detect
    translate_to_en: bool = False
    # output_target: srt_only | soft_embed | burn_in. Kept embed_soft/burn_in
    # for backward compatibility with the runner payload.
    output_target: str = "soft_embed"
    embed_soft: bool = True
    burn_in: bool = False


class WhisperModelInfo(BaseModel):
    name: str
    size_mb: int
    installed: bool


class SettingsResponse(BaseModel):
    downloads_dir: str
    browser: str
    timeout: int
    whisper_default_model: str
    ffmpeg_available: bool
    ffmpeg_path: Optional[str] = None


class TaskIdResponse(BaseModel):
    task_id: str


class CreateVoiceRequest(BaseModel):
    media_file_id: str            # video to attach the voice to
    subtitle_file_id: Optional[str] = None  # use existing translated subtitle
    # If no subtitle is supplied, transcribe-then-translate using whisper:
    whisper_model: str = "small"
    source_language: Optional[str] = None
    # Optional override for the SRT target language. When None, the runner
    # infers it from the voice locale (e.g. "vi-VN-..." → "vi").
    target_language: Optional[str] = None
    voice: str = "en-US-AriaNeural"
    rate: str = "+0%"
    mux_into_video: bool = True   # produce a new MP4 with the voice as an extra track
    make_default_track: bool = False


class VoiceInfoResponse(BaseModel):
    short_name: str
    locale: str
    gender: str
    display_name: str
