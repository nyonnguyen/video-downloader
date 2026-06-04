from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Task(SQLModel, table=True):
    id: str = Field(primary_key=True)
    type: str
    status: str = "pending"  # pending | running | done | error | cancelled
    payload_json: str = "{}"
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    log: str = ""
    media_file_id: Optional[str] = Field(default=None, foreign_key="mediafile.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Download(SQLModel, table=True):
    id: str = Field(primary_key=True)
    task_id: str = Field(foreign_key="task.id")
    url: str
    source: str
    requested_quality: Optional[str] = None
    title: Optional[str] = None
    media_file_id: Optional[str] = Field(default=None, foreign_key="mediafile.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MediaFile(SQLModel, table=True):
    id: str = Field(primary_key=True)
    path: str
    filename: str
    size_bytes: int = 0
    duration_sec: Optional[float] = None
    container: str = ""
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail_path: Optional[str] = None
    parent_id: Optional[str] = Field(default=None, foreign_key="mediafile.id")
    kind: str = "video"  # video | audio | subtitle
    source_url: Optional[str] = None
    archived_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
