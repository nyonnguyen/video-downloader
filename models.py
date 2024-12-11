from enum import Enum


class RESOLUTION:
    AUTO = "auto"
    P360 = "360p"
    P480 = "480p"
    P720 = "720p"
    P1080 = "1080p"


class YouTubeQuality(Enum):
    BEST = "bestvideo+bestaudio/b"  # Best quality available (fallback to combine)
    HIGH_1080P = "bv*[height<=1080]+ba/b"  # Best video <= 1080p with audio
    MEDIUM_720P = "bv*[height<=720]+ba/b"  # Best video <= 720p with audio
    LOW_480P = "bv*[height<=480]+ba/b"  # Best video <= 480p with audio
    AUDIO_ONLY = "bestaudio"  # Audio only
    HIGH_4K = "bv*[height<=2160]+ba/b"  # Best video <= 4K (2160p) with audio
    HIGH_8K = "bv*[height<=4320]+ba/b"  # Best video <= 8K (4320p) with audio
    SUPER_4K = "bv*[height=2160]+ba"  # Strictly 4K video with audio
    SUPER_8K = "bv*[height=4320]+ba"  # Strictly 8K video with audio
    AUDIO_MP3 = "bestaudio[ext=mp3]"  # Audio only in MP3 format
    AUDIO_M4A = "bestaudio[ext=m4a]"  # Audio only in M4A format
    AUDIO_OPUS = "bestaudio[ext=opus]"  # Audio only in OPUS format
    AUDIO_WEBM = "bestaudio[ext=webm]"  # Audio only in WebM format
    AUDIO_BEST_CODEC = "bestaudio[acodec=opus]"  # Best audio with OPUS codec
    AUDIO_STRICT_MP3 = "ba[ext=mp3]/bestaudio[ext=mp3]"  # Strictly MP3 audio


class DownloadOptions:
    def __init__(self, app_config, input_url, browser='firefox', timeout=30):
        self.app_config = app_config
        self.input_url = input_url
        self.browser = browser
        self.timeout = timeout
        self.params = None
        self.headers = None
        self.download_url = None
        self.video_title = None
        self.resolution = None