# Importing modules triggers @register_runner decorators
from backend.runners import download_runner  # noqa: F401
from backend.runners import convert_runner  # noqa: F401
from backend.runners import subtitle_runner  # noqa: F401
from backend.runners import voice_runner  # noqa: F401
