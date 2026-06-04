import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.admin import setup_admin
from backend.db import init_db
from backend.queue import queue
from backend.settings import settings
from utils.logging import get_logger

# Routers + runners
from backend.routers import analyze, downloads, tasks, ws as ws_router, library, convert, subtitle, voice, settings as settings_router
from backend import runners  # noqa: F401 — registers task runners
import downloaders  # noqa: F401 — registers downloaders

logger = get_logger("backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("DB initialized at %s", settings.db_path)
    await queue.start()
    yield
    await queue.stop()
    logger.info("Shutdown")


app = FastAPI(title="Video Downloader & AI Toolkit", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "video-downloader-api"}


app.include_router(analyze.router)
app.include_router(downloads.router)
app.include_router(tasks.router)
app.include_router(library.router)
app.include_router(convert.router)
app.include_router(subtitle.router)
app.include_router(voice.router)
app.include_router(settings_router.router)
app.include_router(ws_router.router)

setup_admin(app)


# --- SPA mount (production single-binary mode) ---
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    assets_dir = os.path.join(_static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # Don't intercept API or WS routes
        if full_path.startswith("api/") or full_path.startswith("ws/") or full_path.startswith("admin"):
            raise HTTPException(404)
        # Specific top-level files (favicon, vite.svg, etc.)
        candidate = os.path.join(_static_dir, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        # Fallback to index.html for client-side routing
        return FileResponse(os.path.join(_static_dir, "index.html"))
