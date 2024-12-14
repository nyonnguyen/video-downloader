import os
import uuid
import yt_dlp
from utils.path_utils import format_video_title
from models import DownloadOptions, YouTubeQuality


class YouTubeDownloader(object):

    def __init__(self, options: DownloadOptions):
        self.options = options
        self.yt_list = []

    def download_yt_video(self, output_path):
        file_ext = 'mp4'

        # read audio_only from options
        if 'AUDIO' in self.options.resolution.name:
            file_ext = 'mp3'
        video_name = f"{output_path}/video_{str(uuid.uuid4())}_{self.options.resolution.name.lower()}.{file_ext}"
        ydl_opts = {
            'quiet': False,  # Show download progress
            'format': self.options.resolution.value,  # Use the selected quality
            'outtmpl': video_name,  # Output file based on quality
            'merge_output_format': f'{file_ext}',  # Merge video and audio if needed
            'continue': True,
            'force_overwrites': True,
            'fragment_retries': 10,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract video information
            info = ydl.extract_info(self.options.download_url, download=False)

            # Get and print video title
            self.options.video_title = info.get('title')
            print(f"Video Title: {self.options.video_title}")

            # Proceed with download
            ydl.download([self.options.download_url])

        video_title = format_video_title(self.options.video_title)
        file_destination = f"{output_path}/{video_title}.{file_ext}"
        os.rename(video_name, file_destination)
        print(f"Downloaded video: {file_destination}")


    def download(self, output_path=None):
        self.options.download_url = self.options.input_url
        self.download_yt_video(output_path)
