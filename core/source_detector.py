import os
from urllib.parse import urlparse

from config import ConfigReader

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
_config = ConfigReader(_CONFIG_PATH)


def detect_source(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    for app in _config.get("apps"):
        name = app.get("name", "").lower()
        if name and (name in netloc or name in url.lower()):
            return name
    return "generic"


def get_app_config(source: str):
    for app in _config.get("apps"):
        if app.get("name") == source:
            return app
    return {"name": "generic", "base_url": "", "resolution": "BEST"}
