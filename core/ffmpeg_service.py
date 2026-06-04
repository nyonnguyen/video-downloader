"""FFmpeg subprocess wrapper with progress streaming."""
import os
import re
import shutil
import subprocess
from threading import Event
from typing import Callable, Optional

from core.presets import PRESETS, Preset
from utils.logging import get_logger

logger = get_logger("ffmpeg")

ProgressCallback = Callable[[float, str], None]


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def _parse_duration_sec(probe_dur: Optional[str]) -> float:
    try:
        return float(probe_dur) if probe_dur else 0.0
    except (TypeError, ValueError):
        return 0.0


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _ffprobe_duration(path: str) -> float:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return 0.0
    # Use ffmpeg itself to get duration to avoid requiring ffprobe
    try:
        r = subprocess.run(
            [ffmpeg, "-i", path], capture_output=True, text=True, timeout=20,
        )
        for line in (r.stderr or "").splitlines():
            m = _DURATION_RE.search(line)
            if m:
                h, mi, s = m.groups()
                return int(h) * 3600 + int(mi) * 60 + float(s)
    except Exception:
        pass
    return 0.0


def convert(
    src_path: str,
    dst_path: str,
    preset_id: str,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[Event] = None,
) -> str:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH (try: brew install ffmpeg)")
    preset: Preset = PRESETS.get(preset_id)  # type: ignore
    if preset is None:
        raise ValueError(f"unknown preset: {preset_id}")

    total_sec = _ffprobe_duration(src_path) or 1.0

    args = [ffmpeg, "-y", "-i", src_path]
    if preset.vcodec:
        args += ["-c:v", preset.vcodec]
    elif preset.acodec is not None:
        # audio-only preset; do not include video stream
        pass
    if preset.acodec:
        args += ["-c:a", preset.acodec]
    args += list(preset.extra_args or [])
    args += ["-progress", "pipe:1", "-nostats", dst_path]

    logger.info("ffmpeg %s", " ".join(args[1:]))
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout is not None

    out_time_us = 0
    last_progress = 0.0
    try:
        for line in proc.stdout:
            line = line.strip()
            if cancel_event and cancel_event.is_set():
                proc.terminate()
                break
            if line.startswith("out_time_us="):
                try:
                    out_time_us = int(line.split("=", 1)[1])
                except ValueError:
                    out_time_us = 0
                current_sec = out_time_us / 1_000_000
                pct = min(current_sec / total_sec, 1.0) if total_sec > 0 else 0.0
                if pct - last_progress >= 0.01 and progress_cb:
                    last_progress = pct
                    progress_cb(pct, f"Encoding {current_sec:.1f}s / {total_sec:.0f}s")
            elif line == "progress=end" and progress_cb:
                progress_cb(1.0, "Finalizing…")
        rc = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()

    if rc != 0:
        err = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"ffmpeg exited {rc}: {err[-500:]}")
    if not os.path.exists(dst_path):
        raise RuntimeError("ffmpeg produced no output file")
    return dst_path
