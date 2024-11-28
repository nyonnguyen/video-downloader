import re
import time
from urllib.parse import urlparse, parse_qs

from selenium.common import TimeoutException
from selenium.webdriver.common.by import By

from downloaders.douyin_dl import DouyinDownloader
from downloaders.ixigua_dl import XiGuaDownloader
from downloaders.yt_dl import YouTubeDownloader
from models import DownloadOptions
from video_element import VideoElement
from webdriver_helper import WebDriverHelper, locator_parser


def json_headers(headers) -> dict:
    headers_dict = {key: value for key, value in headers.items()}
    return headers_dict


class DownloadManager:
    def __init__(self, download_options: DownloadOptions):
        self.options = download_options

    def get_download_info(self):
        if 'youtube' in self.options.app_config.get('name'):
            return
        driver = WebDriverHelper(browser=self.options.browser)
        driver.load_video_page(self.options.input_url, resolution=self.options.resolution)

        by, title_locator = locator_parser(self.options.app_config.get('title_locator'))
        self.options.video_title = f"{driver.get_video_title(by, title_locator)}_{self.options.resolution}"

        by, video_locator = locator_parser(self.options.app_config.get('video_locator'))
        video_element = driver.wait_until_element_found(by, video_locator, timeout=self.options.timeout)
        video = VideoElement(driver.driver, video_element)
        print("Found video element")

        try:
            video.wait_until_ready(timeout=120)
        except TimeoutException or TimeoutError:
            print("Video is not ready. Reloading the page...")
            driver.reload_page()
            video_element = driver.wait_until_element_found(By.TAG_NAME, 'video')
            video = VideoElement(driver.driver, video_element)
            print("Found video element again")
            video.wait_until_ready(timeout=120)

        for _ in range(5):
            print("Checking video buffer...")
            print(f"Found {len(driver.get_requests())} requests")
            video_url = None
            audio_url = None
            for request in driver.get_requests():
                if request.response and self.options.app_config.get('fetching_pattern') in request.url:
                    video_url = request.url
                    self.options.headers = json_headers(request.headers)
                    break
            if self.options.is_audio and video_url:
                for request in driver.get_requests():
                    if request.response and self.options.app_config.get('fetching_audio_pattern') in request.url:
                        audio_url = request.url
                        self.options.headers_audio = json_headers(request.headers)
            if video_url:
                break
            else:
                print("Not match video fetching pattern")
                driver.driver.refresh()
                time.sleep(3)
                continue
        else:
            print("No video URL found")
            driver.quit()
            exit(1)

        parsed_url = urlparse(video_url)
        self.options.params = {key: value[0] for key, value in parse_qs(parsed_url.query).items()}
        self.options.download_url = re.search(rf"{self.options.app_config.get('video_url_pattern')}", video_url).group(1)
        print(self.options.download_url)

        if self.options.is_audio:
            parsed_url = urlparse(audio_url)
            self.options.params_audio = {key: value[0] for key, value in parse_qs(parsed_url.query).items()}
            self.options.download_url_audio = re.search(rf"{self.options.app_config.get('audio_url_pattern')}", audio_url).group(1)
            print(self.options.download_url_audio)

        driver.quit()

    def get_downloader(self):
        app_name = self.options.app_config.get('name')
        if 'ixigua' in app_name:
            return XiGuaDownloader(self.options)
        elif 'douyin' in app_name:
            return DouyinDownloader(self.options)
        elif 'youtube' in app_name:
            return YouTubeDownloader(self.options)
        return None
