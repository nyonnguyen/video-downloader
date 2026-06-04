import time
import uuid
from threading import Event
from typing import Callable, Optional
from urllib.parse import urlparse, parse_qs

import requests

from models import DownloadOptions
from utils.logging import get_logger
from utils.path_utils import format_video_title

logger = get_logger(__name__)

ProgressCallback = Callable[[float, str], None]


def get_video_id_with_source(url: str) -> str:
    url = url.replace(" ", "")
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    path = parsed_url.path.strip('/')
    query_params = parse_qs(parsed_url.query)
    if query_params:
        query_string = "_".join(f"{key}={value[0]}" for key, value in query_params.items())
        return f"{domain}_{query_string}"
    return f"{domain}_{path}"


PART_SIZE = 5 * 1024 * 1024  # 5 MB
PART_RETRIES = 3
RETRY_BACKOFF_S = 1.5


class Downloader:
    def __init__(
        self,
        options: DownloadOptions,
        cookies=None,
        part_size: Optional[int] = None,
    ):
        self.options = options
        self.base_url = options.app_config.get('base_url') if options.app_config else None
        self.download_url = options.download_url
        self.params = options.params
        self.part_size = part_size or PART_SIZE
        self.headers = options.headers or self.get_headers()
        self.video_title = options.video_title or self.parse_video_id()
        self.temp_name = str(uuid.uuid4())
        self.cookies = cookies

    def parse_video_id(self):
        return get_video_id_with_source(self.options.input_url)

    def get_headers(self):
        return {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
            'origin': f'{self.base_url}',
            'priority': 'u=1, i',
            'range': f'bytes=0-{self.part_size}',
            'referer': f'{self.base_url}/',
            'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        }

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        if self.cookies:
            for cookie in self.cookies:
                session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path"),
                    secure=cookie.get("secure"),
                    rest={"HttpOnly": cookie.get("httpOnly"), "SameSite": cookie.get("sameSite")},
                )
        session.headers = self.headers
        session.params = self.params
        return session

    def _fetch_part_with_retry(self, session: requests.Session, start: int, end: int):
        self.headers['range'] = f'bytes={start}-{end}'
        last_err: Optional[Exception] = None
        for attempt in range(PART_RETRIES):
            try:
                resp = session.get(self.download_url, timeout=60)
                if resp.status_code in (200, 206):
                    return resp
                last_err = RuntimeError(f"HTTP {resp.status_code}")
            except requests.RequestException as e:
                last_err = e
            time.sleep(RETRY_BACKOFF_S * (attempt + 1))
        raise RuntimeError(f"Failed part {start}-{end}: {last_err}")

    def download(
        self,
        output_path: Optional[str] = None,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[Event] = None,
    ) -> Optional[str]:
        session = self._build_session()
        logger.info("Fetching first byte range to discover file size...")
        response = session.get(self.download_url, timeout=60)
        if response.status_code not in (200, 206):
            logger.error("Initial request failed: HTTP %s", response.status_code)
            return None

        if 'Content-Range' in response.headers:
            file_size = int(response.headers['Content-Range'].split('/')[-1])
        elif 'Content-Length' in response.headers:
            file_size = int(response.headers['Content-Length'])
        else:
            logger.error("No Content-Range/Content-Length header; cannot determine size")
            return None

        total_parts = (file_size + self.part_size - 1) // self.part_size
        file_name = format_video_title(self.video_title)
        out_file = f'{output_path}/{file_name}.mp4'
        logger.info("Downloading %s parts → %s", total_parts, out_file)

        with open(out_file, 'wb') as f:
            for i in range(total_parts):
                if cancel_event and cancel_event.is_set():
                    logger.info("Download cancelled at part %s/%s", i, total_parts)
                    return None
                start = i * self.part_size
                end = min(start + self.part_size - 1, file_size - 1)
                part_resp = self._fetch_part_with_retry(session, start, end)
                f.write(part_resp.content)
                pct = (i + 1) / total_parts
                logger.info("Part %s/%s (%.1f%%)", i + 1, total_parts, pct * 100)
                if progress_cb:
                    progress_cb(pct, f"Part {i + 1}/{total_parts}")
        return out_file

    def silent_download(self, output_path: Optional[str] = None) -> Optional[str]:
        try:
            file_name = format_video_title(self.video_title)
            out_file = f'{output_path}/{file_name}.mp4'
            with open(out_file, 'wb') as f:
                response = requests.get(self.download_url, headers=self.headers, params=self.params)
                if response.status_code in (200, 206):
                    f.write(response.content)
                    return out_file
                logger.error("Silent download failed: %s", response.status_code)
                return None
        except Exception as e:
            logger.exception("silent_download error: %s", e)
            return None
