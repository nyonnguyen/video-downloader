# Video Downloader & AI Toolkit

Localhost web app for downloading videos from multiple sources, converting with FFmpeg, and generating subtitles with Whisper.

## Features

- **Download**: YouTube (yt-dlp), TikTok, Douyin, iXiGua (Playwright sniff), generic yt-dlp fallback for Vimeo / FB / Twitter / Reddit / Bilibili / Instagram / …
- **Queue**: real-time progress via WebSocket
- **Library**: SQLite-backed media catalog with thumbnails + in-browser playback (HTTP Range)
- **Convert**: FFmpeg presets (H.264 720p/1080p, WebM VP9, MP3, WAV, 9:16 vertical)
- **AI Subtitle**: faster-whisper STT, translate-to-English, optional burn-in

## Setup

Requires Python 3.9+, Node 18+, FFmpeg (`brew install ffmpeg`).

```bash
# Python
./venv/bin/python -m pip install --index-url https://pypi.org/simple/ -r requirements.txt
./venv/bin/playwright install chromium

# Frontend
(cd frontend && npm install)
```

## Run

### Development (two servers, hot-reload)

```bash
./scripts/dev.sh
# → http://localhost:5180  (Vite UI, proxies /api + /ws → :8765)
```

### Production (single server)

```bash
./scripts/build.sh                                   # builds frontend → backend/static
./venv/bin/python -m uvicorn backend.main:app --port 8765
# → http://localhost:8765
```

### CLI (still works)

```bash
./venv/bin/python main.py <url> [quality]
# e.g. ./venv/bin/python main.py https://www.ixigua.com/7424360313794855439 P1080
```

## Layout

```
backend/   FastAPI app, queue, runners, DB
core/      shared services (download, ffmpeg, whisper, library)
downloaders/  per-source extractors registered via decorator
frontend/  Vite + React + Tailwind UI
data/      runtime: app.db, downloads/, converted/, subtitles/, models/
scripts/   dev.sh, build.sh
```

## Ports

- Backend (FastAPI): `8765`
- Frontend dev (Vite): `5180`
- API docs: `http://localhost:8765/docs`
