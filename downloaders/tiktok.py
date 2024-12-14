from downloaders.downloader import Downloader
from models import DownloadOptions


class TiktokDownloader(Downloader):

    def __init__(self, options: DownloadOptions, cookies=None, part_size=None):
        super().__init__(options, cookies, part_size)
