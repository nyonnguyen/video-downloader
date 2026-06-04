from downloaders.base import Downloader
from downloaders.registry import register
from models import DownloadOptions


@register("tiktok")
class TiktokDownloader(Downloader):
    def __init__(self, options: DownloadOptions, cookies=None, part_size=None):
        super().__init__(options, cookies=cookies, part_size=part_size)
