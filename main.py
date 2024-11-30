import os
import sys

from config import ConfigReader
from download_manager import DownloadManager
from models import RESOLUTION, DownloadOptions, YouTubeQuality

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, 'config.json')

config = ConfigReader(config_path)
browser = config.get('browser')
timeout = config.get('timeout')
output_path = config.get('output_path')



def find_app_config(download_url):
    for app_config in config.get('apps'):
        if app_config.get('name') in download_url:
            return app_config
    return None


if __name__ == '__main__':
    arguments = sys.argv[1:]
    url = arguments[0]  # url = 'https://www.ixigua.com/7424360313794855439'
    print(url)

    app_config = find_app_config(url)
    resolution = app_config.get('resolution')

    options = DownloadOptions(app_config, url, browser=browser, timeout=timeout)

    # download_manager = DownloadManager(options)
    download_manager = DownloadManager(options)
    if 'youtube' not in url:
        # For non-YouTube videos
        resolution_value = getattr(RESOLUTION, resolution, RESOLUTION.AUTO)
    else:
        # For YouTube videos
        resolution_value = getattr(YouTubeQuality, resolution, YouTubeQuality.BEST)

    options.resolution = resolution_value
    download_manager = DownloadManager(options)
    download_manager.get_download_info()
    downloader = download_manager.get_downloader()
    downloader.download(output_path)
