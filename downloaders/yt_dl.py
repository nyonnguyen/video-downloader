import os
import uuid
from threading import Event
from typing import Callable, Optional

import yt_dlp

from downloaders.registry import register
from models import DownloadOptions, YouTubeQuality
from utils.logging import get_logger
from utils.path_utils import format_video_title

logger = get_logger(__name__)

ProgressCallback = Callable[[float, str], None]
LogCallback = Callable[[str, str], None]


class _YdlLogger:
    """Routes yt-dlp's internal log messages into a per-task log callback."""

    def __init__(self, cb: Optional[LogCallback]):
        self._cb = cb

    def _emit(self, level: str, msg: str):
        if not self._cb:
            return
        # Strip ANSI escape sequences yt-dlp sometimes injects.
        text = msg.replace("\r", "").strip()
        if not text:
            return
        try:
            self._cb(f"yt-dlp: {text}", level)
        except Exception:
            pass

    def debug(self, msg):
        # yt-dlp uses debug() for normal info; filter the noisy ones.
        if msg.startswith("[debug] "):
            return
        self._emit("info", msg)

    def info(self, msg):
        self._emit("info", msg)

    def warning(self, msg):
        self._emit("warn", msg)

    def error(self, msg):
        self._emit("error", msg)


@register("youtube")
class YouTubeDownloader:
    def __init__(self, options: DownloadOptions, cookies=None, part_size=None):
        self.options = options
        self.cookies = cookies
        self._progress_cb: Optional[ProgressCallback] = None
        self._cancel_event: Optional[Event] = None
        self._log_cb: Optional[LogCallback] = None

    def _hook(self, d):
        if self._cancel_event and self._cancel_event.is_set():
            raise yt_dlp.utils.DownloadError("cancelled")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total and self._progress_cb:
                pct = min(downloaded / total, 1.0)
                speed = d.get("speed")
                speed_str = f" @ {speed/1024/1024:.1f} MB/s" if speed else ""
                self._progress_cb(pct, f"Downloading{speed_str}")
        elif d.get("status") == "finished" and self._progress_cb:
            self._progress_cb(1.0, "Merging…")

    def _resolve_format(self):
        res = self.options.resolution
        if isinstance(res, YouTubeQuality):
            return res
        if isinstance(res, str):
            return getattr(YouTubeQuality, res, YouTubeQuality.BEST)
        return YouTubeQuality.BEST

    def download_yt_video(self, output_path: str) -> Optional[str]:
        quality = self._resolve_format()
        file_ext = "mp3" if "AUDIO" in quality.name else "mp4"
        tmp_name = f"{output_path}/video_{uuid.uuid4()}_{quality.name.lower()}.{file_ext}"
        ydl_opts = {
            "quiet": False,
            "no_warnings": False,
            "verbose": False,
            "logger": _YdlLogger(self._log_cb),
            "format": quality.value,
            "outtmpl": tmp_name,
            "merge_output_format": file_ext,
            "continue": True,
            "force_overwrites": True,
            "fragment_retries": 10,
            "retries": 10,
            "extractor_retries": 3,
            # `watch?v=X&list=RD...` is a Mix radio — without this yt-dlp resolves the
            # URL as a playlist and the title/file end up belonging to a different track.
            "noplaylist": True,
            # YouTube rotates which player_clients return real URLs vs. stubs that
            # yield "downloaded file is empty". Try the widest set known to work.
            # YouTube's "n" / signature challenge needs a JS solver shipped as
            # an "EJS" remote component — without it the only "formats" that
            # come back are storyboard images, which yields the misleading
            # "Requested format is not available" error.
            "remote_components": ["ejs:github"],
            "extractor_args": {
                "youtube": {
                    "player_client": [
                        "tv", "tv_embedded", "mweb", "ios", "web_safari",
                        "web_embedded", "default",
                    ],
                },
            },
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Safari/605.1.15"
                ),
            },
            "progress_hooks": [self._hook],
        }
        _maybe_attach_cookies(ydl_opts, self._log_cb)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.options.download_url, download=False)
            self.options.video_title = info.get("title")
            logger.info("YouTube video: %s", self.options.video_title)
            ydl.download([self.options.download_url])

        video_title = format_video_title(self.options.video_title)
        dest = f"{output_path}/{video_title}.{file_ext}"
        if os.path.exists(tmp_name):
            os.rename(tmp_name, dest)
        logger.info("Downloaded → %s", dest)
        return dest

    def download_yt_playlist(self, output_path: str, limit: int = 999) -> str:
        play_list_path = f"{output_path}/yt-playlist-{uuid.uuid4()}"
        os.makedirs(play_list_path, exist_ok=True)
        quality = self._resolve_format()
        ydl_opts = {
            "format": quality.value,
            "outtmpl": f"{play_list_path}/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s",
            "noplaylist": False,
            "playlist_items": f"1-{limit}",
            "download_archive": f"{play_list_path}/downloaded.txt",
            "quiet": False,
            "no_warnings": False,
            "logger": _YdlLogger(self._log_cb),
            "fragment_retries": 10,
            "retries": 10,
            "extractor_retries": 3,
            # YouTube's "n" / signature challenge needs a JS solver shipped as
            # an "EJS" remote component — without it the only "formats" that
            # come back are storyboard images, which yields the misleading
            # "Requested format is not available" error.
            "remote_components": ["ejs:github"],
            "extractor_args": {
                "youtube": {
                    "player_client": [
                        "tv", "tv_embedded", "mweb", "ios", "web_safari",
                        "web_embedded", "default",
                    ],
                },
            },
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Safari/605.1.15"
                ),
            },
            "progress_hooks": [self._hook],
        }
        _maybe_attach_cookies(ydl_opts, self._log_cb)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([self.options.download_url])
        return play_list_path

    def download(
        self,
        output_path: Optional[str] = None,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[Event] = None,
        log_cb: Optional[LogCallback] = None,
        limit: int = 999,
    ) -> Optional[str]:
        self._progress_cb = progress_cb
        self._cancel_event = cancel_event
        self._log_cb = log_cb
        self.options.download_url = self.options.input_url
        if "playlist?" in self.options.download_url:
            return self.download_yt_playlist(output_path, limit)
        return self.download_yt_video(output_path)


# Paths where each browser keeps its cookie store. We probe these to skip
# browsers the user isn't running.
_BROWSER_PROBES = {
    "firefox": [
        "~/Library/Application Support/Firefox/Profiles",
        "~/.mozilla/firefox",
        "~/AppData/Roaming/Mozilla/Firefox/Profiles",
    ],
    "safari": [
        "~/Library/Cookies/Cookies.binarycookies",
        "~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies",
    ],
    "chrome": [
        "~/Library/Application Support/Google/Chrome/Default/Cookies",
        "~/.config/google-chrome/Default/Cookies",
        "~/AppData/Local/Google/Chrome/User Data/Default/Network/Cookies",
    ],
    "brave": [
        "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies",
        "~/.config/BraveSoftware/Brave-Browser/Default/Cookies",
        "~/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/Network/Cookies",
    ],
    "edge": [
        "~/Library/Application Support/Microsoft Edge/Default/Cookies",
        "~/.config/microsoft-edge/Default/Cookies",
        "~/AppData/Local/Microsoft/Edge/User Data/Default/Network/Cookies",
    ],
}


def _detect_browser_for_cookies() -> Optional[str]:
    """Return the first browser whose cookie store is readable from a detached
    backend process. On macOS, Chromium-family browsers encrypt cookies with a
    Keychain key that requires UI authorization to unlock — we'd extract 0
    cookies. Firefox/Safari store cookies in plain SQLite/binarycookies, so
    prefer those first."""
    for name in ("firefox", "safari", "chrome", "brave", "edge"):
        for probe in _BROWSER_PROBES[name]:
            path = os.path.expanduser(probe)
            if os.path.exists(path):
                # Firefox dir must actually contain a cookies.sqlite somewhere.
                if name == "firefox":
                    for root, _dirs, files in os.walk(path):
                        if "cookies.sqlite" in files:
                            return "firefox"
                    continue
                return name
    return None


def _maybe_attach_cookies(ydl_opts: dict, log_cb: Optional[LogCallback]):
    """Wire cookies into yt-dlp so YouTube's GVS-PO-token gate is satisfied.

    Resolution order:
      1. YT_DLP_COOKIES_FROM_BROWSER env var (explicit)
      2. YT_DLP_COOKIES_FILE env var (explicit)
      3. data/cookies.txt next to the project (drop-in spot)
      4. First installed browser detected on disk
    """
    browser = os.environ.get("YT_DLP_COOKIES_FROM_BROWSER")
    if browser:
        ydl_opts["cookiesfrombrowser"] = (browser,)
        if log_cb:
            log_cb(f"Using cookies from browser (env): {browser}", "info")
        return

    cookie_file = os.environ.get("YT_DLP_COOKIES_FILE")
    if cookie_file and os.path.isfile(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
        if log_cb:
            log_cb(f"Using cookie file (env): {cookie_file}", "info")
        return

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    drop_in = os.path.join(project_root, "data", "cookies.txt")
    if os.path.isfile(drop_in):
        ydl_opts["cookiefile"] = drop_in
        if log_cb:
            log_cb(f"Using cookie file: {drop_in}", "info")
        return

    detected = _detect_browser_for_cookies()
    if detected:
        ydl_opts["cookiesfrombrowser"] = (detected,)
        if log_cb:
            log_cb(f"Auto-detected browser cookies: {detected}", "info")
        return

    if log_cb:
        log_cb(
            "No cookies configured — YouTube will likely reject anonymous "
            "downloads (set YT_DLP_COOKIES_FROM_BROWSER=chrome or drop a "
            "cookies.txt in data/ to fix).",
            "warn",
        )
