from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import event

from backend.settings import settings
import backend.models_db  # noqa: F401 — register tables


engine = create_engine(
    f"sqlite:///{settings.db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db():
    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate():
    """Lightweight in-place schema migrations for SQLite."""
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(mediafile)").fetchall()}
        if "archived_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE mediafile ADD COLUMN archived_at DATETIME")


def get_session():
    with Session(engine) as session:
        yield session
