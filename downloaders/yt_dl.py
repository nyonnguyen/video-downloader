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

    def download_yt_playlist(self, output_path, limit):
        play_list_path = f"{output_path}/yt-playlist-{str(uuid.uuid4())}"
        os.mkdir(play_list_path)
        ydl_opts = {
            'format': self.options.resolution.value,  # Download by set resolution
            'outtmpl': f'{play_list_path}/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s',
            # Name files with playlist order and title
            'noplaylist': False,  # Ensure it's treating the URL as a playlist
            'playlist_items': f'1-{limit}',  # Optional: Download specific range of videos
            'download_archive': f'{play_list_path}/downloaded.txt',  # Avoid re-downloading videos
            'quiet': False,  # Show progress in the terminal
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([self.options.download_url])

    def download(self, output_path=None, limit=999):
        self.options.download_url = self.options.input_url
        if 'playlist?' in self.options.download_url:
            self.download_yt_playlist(output_path, limit)
        else:
            self.download_yt_video(output_path)
