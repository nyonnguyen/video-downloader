"""faster-whisper wrapper for STT + SRT generation."""
import os
from threading import Event
from typing import Callable, Optional

from backend.settings import settings
from utils.logging import get_logger

logger = get_logger("subtitle")

ProgressCallback = Callable[[float, str], None]

WHISPER_MODELS: dict[str, int] = {
    "tiny": 75,
    "base": 140,
    "small": 480,
    "medium": 1500,
    "large-v3": 3000,
}


def is_model_installed(name: str) -> bool:
    """Heuristic: faster-whisper caches under data/models/<name>/."""
    base = os.path.join(settings.models_dir, f"models--Systran--faster-whisper-{name}")
    return os.path.exists(base)


def _format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_to_srt(
    src_path: str,
    out_srt_path: str,
    model_name: str = "small",
    language: Optional[str] = None,
    translate_to_en: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[Event] = None,
) -> tuple[str, str]:
    """Returns (srt_path, detected_language)."""
    if not os.path.exists(src_path):
        raise FileNotFoundError(src_path)
    if model_name not in WHISPER_MODELS:
        raise ValueError(f"unknown whisper model: {model_name}")

    from faster_whisper import WhisperModel  # lazy import

    if progress_cb:
        progress_cb(0.0, f"Loading model {model_name}…")
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        download_root=settings.models_dir,
    )

    if progress_cb:
        progress_cb(0.02, "Transcribing…")
    segments, info = model.transcribe(
        src_path,
        language=language,
        task="translate" if translate_to_en else "transcribe",
        vad_filter=True,
        beam_size=5,
    )

    total_dur = info.duration or 0.0
    lines: list[str] = []
    idx = 0
    for seg in segments:
        if cancel_event and cancel_event.is_set():
            break
        idx += 1
        lines.append(f"{idx}\n{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}\n{seg.text.strip()}\n")
        if progress_cb and total_dur > 0:
            progress_cb(min(seg.end / total_dur, 0.99), f"Segment {idx} @ {seg.end:.1f}s")

    if cancel_event and cancel_event.is_set():
        return "", info.language

    os.makedirs(os.path.dirname(out_srt_path), exist_ok=True)
    with open(out_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if progress_cb:
        progress_cb(1.0, "Done")
    return out_srt_path, info.language


def _sec_to_srt_ts(sec: float) -> str:
    return _format_timestamp(max(sec, 0.0))


def write_srt(cues: list[dict], out_path: str) -> str:
    """Write a list of cue dicts ({index, start_sec, end_sec, text}) to an SRT file."""
    sorted_cues = sorted(cues, key=lambda c: float(c.get("start_sec", 0.0)))
    blocks: list[str] = []
    for i, c in enumerate(sorted_cues, start=1):
        text = (c.get("text") or "").strip()
        if not text:
            continue
        start = float(c.get("start_sec", 0.0))
        end = float(c.get("end_sec", start + 1.0))
        if end <= start:
            end = start + 0.5
        blocks.append(
            f"{i}\n{_sec_to_srt_ts(start)} --> {_sec_to_srt_ts(end)}\n{text}\n"
        )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocks))
    return out_path


def translate_cues(
    cues: list[dict],
    target: str,
    source: Optional[str] = None,
    progress_cb: Optional[ProgressCallback] = None,
) -> list[dict]:
    """Translate cue texts in-place (returns new list). Uses deep-translator's
    Google backend; raises a clear error if the package is missing so the
    caller can surface an install hint."""
    try:
        from deep_translator import GoogleTranslator  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "deep-translator is not installed. Install with: pip install deep-translator"
        ) from e

    src = (source or "auto").lower() or "auto"
    tr = GoogleTranslator(source=src, target=target)
    out: list[dict] = []
    total = max(len(cues), 1)
    for i, c in enumerate(cues):
        original = (c.get("text") or "").strip()
        translated = original
        if original:
            try:
                translated = tr.translate(original) or original
            except Exception as ex:
                logger.warning("translate failed at cue %d: %s", i, ex)
        out.append({
            "index": int(c.get("index", i + 1)),
            "start_sec": float(c.get("start_sec", 0.0)),
            "end_sec": float(c.get("end_sec", 0.0)),
            "text": translated,
        })
        if progress_cb:
            progress_cb((i + 1) / total, f"Translated {i + 1}/{total}")
    return out


def srt_to_vtt(srt_path: str, vtt_path: Optional[str] = None) -> str:
    """Convert an SRT file to WebVTT (for HTML5 <track> element)."""
    if vtt_path is None:
        vtt_path = os.path.splitext(srt_path)[0] + ".vtt"
    with open(srt_path, "r", encoding="utf-8") as f:
        srt = f.read()
    # SRT → VTT: prepend WEBVTT header, replace timestamp commas with periods
    body = srt.replace(",", ".") if False else srt  # placeholder; replace only in timestamps below
    # Safer: regex on timestamp lines (HH:MM:SS,mmm --> HH:MM:SS,mmm)
    import re as _re
    body = _re.sub(
        r"(\d{2}:\d{2}:\d{2}),(\d{3})",
        r"\1.\2",
        srt,
    )
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        f.write(body)
    return vtt_path


def soft_embed_subtitle(
    video_path: str,
    srt_path: str,
    out_path: str,
    language: str = "und",
    title: str = "Subtitle",
) -> str:
    """Soft-embed (mux) an SRT as a subtitle track inside an MP4 (mov_text codec).

    The output file plays in players that read embedded subs (VLC, mpv, QuickTime),
    and the original video stream is copied — no re-encoding.
    """
    from core.ffmpeg_service import find_ffmpeg
    import subprocess
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    args = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", srt_path,
        "-map", "0:v?", "-map", "0:a?", "-map", "1:0",
        "-c:v", "copy", "-c:a", "copy",
        "-c:s", "mov_text",
        "-metadata:s:s:0", f"language={language}",
        "-metadata:s:s:0", f"title={title}",
        "-disposition:s:0", "default",
        out_path,
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"soft embed failed: {r.stderr[-400:]}")
    return out_path


def burn_subtitle_to_video(video_path: str, srt_path: str, out_path: str) -> str:
    """Burn an SRT into a video as hard-coded pixels (not toggleable)."""
    from core.ffmpeg_service import find_ffmpeg
    import subprocess
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    safe_srt = srt_path.replace(":", "\\:").replace("'", "\\'")
    args = [
        ffmpeg, "-y", "-i", video_path,
        "-vf", f"subtitles='{safe_srt}'",
        "-c:a", "copy", out_path,
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"burn-in failed: {r.stderr[-400:]}")
    return out_path
