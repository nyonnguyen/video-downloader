import os
import uuid
from urllib.parse import urlparse, parse_qs

import requests

from models import DownloadOptions
from utils.path_utils import create_directory


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
        self.download_url_audio = options.download_url_audio
        self.params = options.params
        self.params_audio = options.params_audio
        self.part_size = part_size or PART_SIZE
        self.headers = options.headers or self.get_headers()
        self.headers_audio = options.headers_audio
        self.video_title = options.video_title or self.parse_video_id()
        self.is_audio = options.is_audio
        self.temp_name = str(uuid.uuid4())

    def parse_video_id(self):
        return get_video_id_with_source(self.download_url)

    # Define parameters and headers
    # url = 'https://v3-prime-xg-web-pc.ixigua.com/video/tos/cn/tos-cn-ve-4/oICGXDIRgBAO5LEerVLGjfwnceBwmAAKGCUjCc/'

    # params = {
    #     'a': '1768',
    #     'ch': '0',
    #     'cr': '0',
    #     'dr': '0',
    #     'er': '0',
    #     'cd': '0|0|0|0',
    #     'cv': '1',
    #     'br': '3273',
    #     'bt': '3273',
    #     'cs': '0',
    #     'ds': '3',
    #     'ft': 'lhz8bXg_U0mf.pd.jN4974BMg4iXYPujoVJEONHmMvPD-Ipz',
    #     'mime_type': 'video_mp4',
    #     'qs': '0',
    #     'rc': 'NTM4ZGloOmlpaTc7Ojk2ZUBpM2Vycmo5cnJ1dTczNGU0M0AwNDY1NDUxNjUxNC8vLjNfYSNwYWo0MmRjb19gLS1kMC9zcw==',
    #     'btag': 'c0000e00038000',
    #     'dy_q': dy_q,            # Set dynamically
    #     'expire': expire,        # Set dynamically
    #     'feature_id': '2e1813f3872a2105acee44623dff2864',
    #     'l': '202411122118094D8A26191B0C503835B0',
    #     'ply_type': '4',
    #     'policy': '4',
    #     'signature': 'b57b62b9c1553b5a335ec44a4ae20504',
    #     'tk': 'webid',
    #     '__vid': 'v0213bg10004crbrrofog65g7omodbs0',
    #     'webid': '0173c8f974a1c07577a40e1ddb6347b1804450ad458bea7bd35bf3d7a8ab5901e7ee0b3ee5955a1ad4f91e215f65a962aba4e825ff505bdc241e802f8120625e52ede340d61fab5a66c29aee2dbcebe4405410996e808f13b7516f0f5ca494eeff19799dcbc0c6c7a412d52432a36ef3-d0419fa00973166add4276c3cc771e50',
    #     'fid': '805ebfd09e10a06d12f8923207046b5e',
    #     'wid': 'cb898730d22a8f255cdf6a306e55b6d0'
    # }

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

    def download_video(self, url) -> bool:
        print(f"Downloading video parts...")
        # Get the first part to determine file size
        response = requests.get(url, headers=self.headers, params=self.params)

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
            with open(f'{self.temp_name}.mp4', 'wb') as f:
                for i in range(total_parts):
                    start = i * self.part_size
                    end = min(start + self.part_size - 1, file_size - 1)

                    self.headers['range'] = f'bytes={start}-{end}'
                    part_response = requests.get(url, headers=self.headers, params=self.params)

                    if part_response.status_code in [206, 200]:
                        f.write(part_response.content)
                        print(f"Downloaded part {i+1}/{total_parts}")
                    else:
                        print(f"Failed to download part {i+1}")
                        break
            return True
        else:
            print("Request failed with status code:", response.status_code)
            return False

    def download_audio(self, url) -> bool:
        print(f"Downloading audio parts...")
        # Get the first part to determine file size
        response = requests.get(url, headers=self.headers_audio, params=self.params_audio)

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
            with open(f'{self.temp_name}_audio.mp4', 'wb') as f:
                for i in range(total_parts):
                    start = i * self.part_size
                    end = min(start + self.part_size - 1, file_size - 1)

                    self.headers_audio['range'] = f'bytes={start}-{end}'
                    part_response = requests.get(url, headers=self.headers_audio, params=self.params_audio)

                    if part_response.status_code in [206, 200]:
                        f.write(part_response.content)
                        print(f"Downloaded part {i+1}/{total_parts}")
                    else:
                        print(f"Failed to download part {i+1}")
                        break
            return True
        else:
            print("Request failed with status code:", response.status_code)
            return False

    def name_downloaded_video(self):
        create_directory()
        # Check if video file exists
        video_file = f'{self.temp_name}.mp4'
        if os.path.exists(video_file):
            if self.is_audio:
                audio_file = f'{self.temp_name}_audio.mp4'
                if os.path.exists(audio_file):
                    # use ffmpeg to merge audio and video files
                    print("Merging audio and video files...")
                    # merge_video_audio(video_file, audio_file, f'output/{self.video_title}.mp4')
                    os.system(f'ffmpeg -i {video_file} -i {audio_file} -c:v copy -c:a aac "output/{self.video_title}.mp4"')
                    os.remove(video_file)
                    os.remove(audio_file)
                else:
                    print("Audio file not found")
            else:
                print("Not found audio file")
                os.rename(video_file, f'output/{self.video_title}.mp4')
        else:
            print("Video file not found")


    def download(self) -> bool:
        self.download_video(self.download_url)
        if self.download_url_audio:
            self.download_audio(self.download_url_audio)

        self.name_downloaded_video()
        print("Download completed")
        return True


# def merge_video_audio(video_file, audio_file, output_file):
#     try:
#         (
#             ffmpeg
#             .input(video_file)
#             .input(audio_file)
#             .output(output_file, c_v='copy', c_a='aac')
#             .run()
#         )
#         print(f"Successfully created {output_file}")
#     except ffmpeg.Error as e:
#         print(f"Error: {e.stderr.decode('utf8')}")