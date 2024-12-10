import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from downloaders.douyin_dl import DouyinDownloader
from downloaders.ixigua_dl import XiGuaDownloader
from downloaders.yt_dl import YouTubeDownloader
from models import DownloadOptions
from webdriver_helper import WebDriverHelper


def json_headers(headers) -> dict:
    headers_dict = {key: value for key, value in headers.items()}
    return headers_dict


class DownloadManager:
    def __init__(self, download_options: DownloadOptions):
        self.options = download_options

    def get_download_info(self):
        if 'youtube' in self.options.app_config.get('name'):
            return
        browser = WebDriverHelper(browser=self.options.browser)
        browser.launch_browser()
        page = browser.get_page(self.options.input_url)

        title_locator = self.options.app_config.get('title_locator')
        video_locator = self.options.app_config.get('video_locator')
        for attempt in range(5):
            try:
                print("Waiting for video ...")
                self.options.video_title = f"{page.wait_for_selector(title_locator).text_content()}_{self.options.resolution}"
                print(f"Video Title: {self.options.video_title}")
                page.wait_for_selector(video_locator)
                print("Found video element")
                break  # Exit the loop if successful
            except Exception as e:
                print(f"Loading error ... {e}")
                print("Retrying...")
                page.goto(self.options.input_url)
        else:
            print("Failed to find video element after 5 attempts")

        if 'ixigua' in self.options.app_config.get('name'):
            set_local_storage(page, self.options.resolution)
            page.reload()

        print("Parsing video info...")

        desired_request = browser.get_request_info(self.options.app_config.get('fetching_pattern'))
        video_url = desired_request.url
        self.options.headers = json_headers(desired_request.headers)

        parsed_url = urlparse(video_url)
        self.options.params = {key: value[0] for key, value in parse_qs(parsed_url.query).items()}
        self.options.download_url = video_url
        print(self.options.download_url)

        browser.close_browser()

    def get_downloader(self):
        app_name = self.options.app_config.get('name')
        if 'ixigua' in app_name:
            return XiGuaDownloader(self.options)
        elif 'douyin' in app_name:
            return DouyinDownloader(self.options)
        elif 'youtube' in app_name:
            return YouTubeDownloader(self.options)
        return None


def set_local_storage(page, resolution):
    # Get the current date in the desired format
    date = datetime.now().strftime("%Y/%m/%d")

    # Define the key and value for localStorage
    key = "xgplayer_pc_localSettings-all"
    resolution_value = '{"definition":"%s","definitionSetDate":"%s"}' % (resolution, date)

    # Set the localStorage item using page.evaluate()
    page.evaluate(f"""
        window.localStorage.setItem('{key}', '{resolution_value}');
    """)