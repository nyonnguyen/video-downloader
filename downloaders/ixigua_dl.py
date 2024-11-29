from downloaders.downloader import Downloader
from models import DownloadOptions


class XiGuaDownloader(Downloader):

    def __init__(self, options: DownloadOptions, part_size=None):
        super().__init__(options, part_size)
