from datetime import datetime
from threading import Event
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

import downloaders  # triggers registry registration
from core.source_detector import detect_source, get_app_config
from downloaders.registry import get_downloader_class
from models import DownloadOptions, RESOLUTION, YouTubeQuality
from utils.logging import get_logger
from webdriver_helper import WebDriverHelper

logger = get_logger(__name__)

ProgressCallback = Callable[[float, str], None]


def json_headers(headers) -> dict:
    return {key: value for key, value in headers.items()}


class DownloadManager:
    def __init__(self, options: DownloadOptions):
        self.options = options
        self.cookies = None
        self.source = detect_source(options.input_url)

    def _needs_browser_sniff(self) -> bool:
        return self.source in {"ixigua", "douyin", "tiktok"}

    def get_download_info(self):
        if not self._needs_browser_sniff():
            return
        browser = WebDriverHelper(browser=self.options.browser)
        browser.launch_browser()
        page = browser.get_page(self.options.input_url)

        title_locator = self.options.app_config.get("title_locator")
        video_locator = self.options.app_config.get("video_locator")
        for attempt in range(2):
            try:
                logger.info("Waiting for video element...")
                if title_locator:
                    title = page.wait_for_selector(title_locator).text_content()
                    self.options.video_title = f"{title}_{self.options.resolution}"
                page.wait_for_selector(video_locator)
                break
            except Exception as e:
                logger.warning("Loading attempt %s failed: %s", attempt + 1, e)
                page.goto(self.options.input_url)
        else:
            logger.error("Failed to find video element")

        if self.source == "ixigua":
            _set_local_storage(page, self.options.resolution)
            page.reload()

        desired_request = browser.get_request_info(self.options.app_config.get("fetching_pattern"))
        video_url = desired_request.url
        self.options.headers = json_headers(desired_request.headers)
        parsed_url = urlparse(video_url)
        self.options.params = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}
        self.options.download_url = video_url
        self.cookies = page.context.cookies()
        browser.close_browser()

    def get_downloader(self):
        cls = get_downloader_class(self.source)
        if cls is None:
            raise ValueError(f"No downloader registered for source: {self.source}")
        if self.source == "tiktok":
            return cls(self.options, cookies=self.cookies)
        return cls(self.options)


def run_download(
    options: DownloadOptions,
    output_path: str,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[Event] = None,
    log_cb: Optional[Callable[[str, str], None]] = None,
) -> Optional[str]:
    """Single entrypoint used by both CLI and FastAPI runners."""
    mgr = DownloadManager(options)
    mgr.get_download_info()
    downloader = mgr.get_downloader()
    # Pass log_cb only to downloaders that accept it — keeps older ones working.
    try:
        return downloader.download(
            output_path=output_path,
            progress_cb=progress_cb,
            cancel_event=cancel_event,
            log_cb=log_cb,
        )
    except TypeError:
        return downloader.download(
            output_path=output_path,
            progress_cb=progress_cb,
            cancel_event=cancel_event,
        )


def resolve_resolution(source: str, raw: str):
    if source == "youtube" or source == "generic":
        return getattr(YouTubeQuality, raw, YouTubeQuality.BEST)
    return getattr(RESOLUTION, raw, RESOLUTION.AUTO)


def build_options(url: str, browser: str, timeout: int, quality_override: Optional[str] = None) -> DownloadOptions:
    source = detect_source(url)
    app_config = get_app_config(source)
    options = DownloadOptions(app_config, url, browser=browser, timeout=timeout)
    raw = quality_override or app_config.get("resolution", "AUTO")
    options.resolution = resolve_resolution(source, raw)
    return options


def _set_local_storage(page, resolution):
    date = datetime.now().strftime("%Y/%m/%d")
    key = "xgplayer_pc_localSettings-all"
    value = '{"definition":"%s","definitionSetDate":"%s"}' % (resolution, date)
    page.evaluate(f"window.localStorage.setItem('{key}', '{value}');")
