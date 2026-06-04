"""Generic yt-dlp fallback for Vimeo, Facebook, Twitter/X, Reddit, Bilibili, Instagram, etc."""
import os
import uuid
from threading import Event
from typing import Callable, Optional

import yt_dlp

from downloaders.registry import register
from models import DownloadOptions
from utils.logging import get_logger
from utils.path_utils import format_video_title

logger = get_logger(__name__)

ProgressCallback = Callable[[float, str], None]


@register("generic")
class GenericYtDlpDownloader:
    def __init__(self, options: DownloadOptions, cookies=None, part_size=None):
        self.options = options
        self.cookies = cookies
        self._progress_cb: Optional[ProgressCallback] = None
        self._cancel_event: Optional[Event] = None

    def _hook(self, d):
        if self._cancel_event and self._cancel_event.is_set():
            raise yt_dlp.utils.DownloadError("cancelled")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total and self._progress_cb:
                pct = min(downloaded / total, 1.0)
                self._progress_cb(pct, f"Downloading {d.get('_percent_str', '').strip()}")
        elif d.get("status") == "finished" and self._progress_cb:
            self._progress_cb(1.0, "Finalizing…")

    def download(
        self,
        output_path: Optional[str] = None,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[Event] = None,
    ) -> Optional[str]:
        self._progress_cb = progress_cb
        self._cancel_event = cancel_event
        url = self.options.input_url
        tmp_name = f"{output_path}/generic_{uuid.uuid4()}.%(ext)s"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bv*+ba/b",
            "outtmpl": tmp_name,
            "merge_output_format": "mp4",
            "continue": True,
            "force_overwrites": True,
            "fragment_retries": 10,
            "progress_hooks": [self._hook],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title") or "generic"
            self.options.video_title = title
            logger.info("Generic source extracted: %s", title)
            ydl.download([url])
            ext = info.get("ext", "mp4")

        downloaded_glob = tmp_name.replace("%(ext)s", ext)
        if not os.path.exists(downloaded_glob):
            # yt-dlp may have merged to mp4
            downloaded_glob = tmp_name.replace("%(ext)s", "mp4")
        dest = f"{output_path}/{format_video_title(title)}.{ext}"
        if os.path.exists(downloaded_glob):
            os.rename(downloaded_glob, dest)
            logger.info("Downloaded → %s", dest)
            return dest
        return None
