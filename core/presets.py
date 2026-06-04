"""FFmpeg conversion presets."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Preset:
    id: str
    label: str
    container: str               # output extension
    description: str = ""
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    extra_args: list[str] = None  # type: ignore

    def __post_init__(self):
        if self.extra_args is None:
            self.extra_args = []


PRESETS: dict[str, Preset] = {
    "mp4-h264-720p": Preset(
        id="mp4-h264-720p",
        label="MP4 / H.264 / 720p",
        container="mp4",
        vcodec="libx264",
        acodec="aac",
        description="Web-friendly MP4 at 720p, good size/quality balance",
        extra_args=["-vf", "scale=-2:720", "-crf", "23", "-preset", "medium", "-movflags", "+faststart"],
    ),
    "mp4-h264-1080p": Preset(
        id="mp4-h264-1080p",
        label="MP4 / H.264 / 1080p",
        container="mp4",
        vcodec="libx264",
        acodec="aac",
        description="High-quality 1080p MP4",
        extra_args=["-vf", "scale=-2:1080", "-crf", "20", "-preset", "medium", "-movflags", "+faststart"],
    ),
    "webm-vp9": Preset(
        id="webm-vp9",
        label="WebM / VP9",
        container="webm",
        vcodec="libvpx-vp9",
        acodec="libopus",
        description="Open-codec WebM for web",
        extra_args=["-b:v", "0", "-crf", "32"],
    ),
    "mp3-192k": Preset(
        id="mp3-192k",
        label="MP3 audio (192 kbps)",
        container="mp3",
        vcodec=None,
        acodec="libmp3lame",
        description="Extract audio as MP3 192 kbps",
        extra_args=["-vn", "-b:a", "192k"],
    ),
    "wav": Preset(
        id="wav",
        label="WAV audio (uncompressed)",
        container="wav",
        vcodec=None,
        acodec="pcm_s16le",
        description="Extract audio as lossless WAV",
        extra_args=["-vn"],
    ),
    "vertical-9-16": Preset(
        id="vertical-9-16",
        label="Vertical 9:16 (TikTok/Shorts)",
        container="mp4",
        vcodec="libx264",
        acodec="aac",
        description="Crop/pad to 1080×1920 for vertical platforms",
        extra_args=[
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            "-crf", "22", "-preset", "medium",
        ],
    ),
}


def list_presets() -> list[Preset]:
    return list(PRESETS.values())
