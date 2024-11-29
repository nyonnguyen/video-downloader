import uuid
from urllib.parse import urlparse, parse_qs

import requests

from models import DownloadOptions


def get_video_id_with_source(url: str) -> str:
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    path = parsed_url.path.strip('/')
    query_params = parse_qs(parsed_url.query)
    if query_params:
        query_string = "_".join(f"{key}={value[0]}" for key, value in query_params.items())
        return f"{domain}_{query_string}"

    return f"{domain}_{path}"


PART_SIZE = 5 * 1024 * 1024  # 5 MB


class Downloader:


    def __init__(self, options: DownloadOptions, part_size=None):
        self.base_url = options.app_config.get('base_url')
        self.download_url = options.download_url
        self.params = options.params
        self.part_size = part_size or PART_SIZE
        self.headers = options.headers or self.get_headers()
        self.video_title = options.video_title or self.parse_video_id()
        self.temp_name = str(uuid.uuid4())

    def parse_video_id(self):
        return get_video_id_with_source(self.download_url)

    def get_headers(self):
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
            'origin': f'{self.base_url}',
            'priority': 'u=1, i',
            'range': f'bytes=0-{self.part_size}',    # First part
            'referer': f'{self.base_url}/',
            'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        }
        return headers

    def download(self):
        """
        Download the video in parts and write them to a file
        """
        print(f"Downloading video parts...")
        # Get the first part to determine file size
        response = requests.get(self.download_url, headers=self.headers, params=self.params)

        # Check for Content-Range header
        if response.status_code in [206, 200]:
            if 'Content-Range' in response.headers:
                content_range = response.headers['Content-Range']
                file_size = int(content_range.split('/')[-1])  # Extract total file size
            elif 'Content-Length' in response.headers:
                file_size = int(response.headers['Content-Length'])
            else:
                print("Failed to retrieve the file size from header")
                return False

            # Calculate total number of parts
            total_parts = (file_size + self.part_size - 1) // self.part_size  # Ceiling division

            # Start downloading parts and write them to file
            with open(f'{self.video_title}.mp4', 'wb') as f:
                for i in range(total_parts):
                    start = i * self.part_size
                    end = min(start + self.part_size - 1, file_size - 1)

                    self.headers['range'] = f'bytes={start}-{end}'
                    part_response = requests.get(self.download_url, headers=self.headers, params=self.params)

                    if part_response.status_code in [206, 200]:
                        f.write(part_response.content)
                        print(f"Downloaded part {i + 1}/{total_parts}")
                    else:
                        print(f"Failed to download part {i + 1}")
                        break
            return True
        else:
            print("Request failed with status code:", response.status_code)
            return False

    def silent_download(self):
        """
        Download the video without printing to console
        """
        try:
            with open(f'output/{self.video_title}.mp4', 'wb') as f:
                response = requests.get(self.download_url, headers=self.headers, params=self.params)
                if response.status_code in [200, 206]:
                    f.write(response.content)
                else:
                    print(f"Failed to download {self.video_title}")

        except Exception as e:
            print(e)
            return False