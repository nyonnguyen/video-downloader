import os
import uuid
import yt_dlp
from utils.path_utils import format_video_title
from models import DownloadOptions


class YouTubeDownloader(object):

    def __init__(self, options: DownloadOptions):
        self.options = options

    def download_youtube_video(self, output_path):
        video_name = f"{output_path}/video_{str(uuid.uuid4())}_{self.options.resolution.name.lower()}.mp4"
        ydl_opts = {
            'quiet': False,  # Show download progress
            'format': self.options.resolution.value,  # Use the selected quality
            'outtmpl': video_name,  # Output file based on quality
            'merge_output_format': 'mp4',  # Merge video and audio if needed
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
        os.rename(video_name, f"{output_path}/{video_title}.mp4")

    def download(self, output_path=None):
        self.options.download_url = self.options.input_url
        self.download_youtube_video(output_path)
