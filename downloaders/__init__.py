from .registry import DOWNLOADER_REGISTRY, register  # noqa: F401

# Importing modules triggers @register decorators
from . import yt_dl  # noqa: F401
from . import ixigua_dl  # noqa: F401
from . import douyin_dl  # noqa: F401
from . import tiktok  # noqa: F401
from . import generic_yt_dlp  # noqa: F401
