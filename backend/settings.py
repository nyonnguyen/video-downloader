import os

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    project_root: str = PROJECT_ROOT
    data_dir: str = os.path.join(PROJECT_ROOT, "data")
    downloads_dir: str = os.path.join(PROJECT_ROOT, "data", "downloads")
    converted_dir: str = os.path.join(PROJECT_ROOT, "data", "converted")
    subtitles_dir: str = os.path.join(PROJECT_ROOT, "data", "subtitles")
    models_dir: str = os.path.join(PROJECT_ROOT, "data", "models")
    db_path: str = os.path.join(PROJECT_ROOT, "data", "app.db")

    browser: str = "chromium"
    timeout: int = 60
    queue_concurrency: int = 2
    whisper_default_model: str = "small"

    cors_origins: list[str] = ["http://localhost:5180", "http://127.0.0.1:5180"]


settings = AppSettings()

# Ensure data directories exist
for path in (
    settings.data_dir,
    settings.downloads_dir,
    settings.converted_dir,
    settings.subtitles_dir,
    settings.models_dir,
):
    os.makedirs(path, exist_ok=True)
