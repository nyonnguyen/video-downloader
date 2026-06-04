"""edge-tts wrapper: list voices, synthesize SRT → audio, mux into video."""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass
from threading import Event
from typing import Callable, Optional

from core.ffmpeg_service import find_ffmpeg
from utils.logging import get_logger

logger = get_logger("voice")

ProgressCallback = Callable[[float, str], None]

_SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n"
    r"((?:.+\n?)+?)(?:\n|$)"
)


@dataclass
class SubtitleCue:
    index: int
    start_sec: float
    end_sec: float
    text: str


@dataclass
class VoiceInfo:
    short_name: str
    locale: str
    gender: str
    display_name: str


def _ts_to_sec(ts: str) -> float:
    ts = ts.replace(",", ".")
    h, m, rest = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def parse_srt(path: str) -> list[SubtitleCue]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    cues: list[SubtitleCue] = []
    for m in _SRT_BLOCK_RE.finditer(text):
        idx = int(m.group(1))
        start = _ts_to_sec(m.group(2))
        end = _ts_to_sec(m.group(3))
        body = m.group(4).strip().replace("\n", " ")
        if body:
            cues.append(SubtitleCue(idx, start, end, body))
    return cues


async def list_voices_async() -> list[VoiceInfo]:
    import edge_tts
    raw = await edge_tts.list_voices()
    out: list[VoiceInfo] = []
    for v in raw:
        out.append(VoiceInfo(
            short_name=v.get("ShortName", ""),
            locale=v.get("Locale", ""),
            gender=v.get("Gender", ""),
            display_name=v.get("FriendlyName") or v.get("ShortName", ""),
        ))
    return out


def list_voices() -> list[VoiceInfo]:
    return asyncio.run(list_voices_async())


async def _synthesize_cue_async(text: str, voice: str, out_path: str, rate: str = "+0%") -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(out_path)


def _atempo_chain(speed: float) -> str:
    """ffmpeg's atempo filter only accepts 0.5..2.0 per pass; chain for higher ratios."""
    if speed <= 0:
        return "atempo=1.0"
    parts: list[float] = []
    remaining = speed
    while remaining > 2.0:
        parts.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        parts.append(0.5)
        remaining /= 0.5
    parts.append(remaining)
    return ",".join(f"atempo={p:.4f}" for p in parts)


def _atempo_mp3(in_path: str, out_path: str, speed: float) -> None:
    """Re-encode an mp3 with an atempo filter to change its duration."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    args = [
        ffmpeg, "-y", "-i", in_path,
        "-filter:a", _atempo_chain(speed),
        "-c:a", "libmp3lame", "-b:a", "48k",
        out_path,
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"atempo failed: {r.stderr[-300:]}")


def _silence_mp3(duration_sec: float, out_path: str) -> None:
    """Generate a mono 24 kHz MP3 silence clip.

    Why MP3 specifically: edge-tts emits 24 kHz mono MP3 cues, and the ffmpeg
    concat demuxer requires every input to share the same codec/format — mixing
    in a WAV gap makes ffmpeg interpret the subsequent MP3 bytes as raw PCM,
    producing garbled audio and a wildly wrong duration.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    args = [
        ffmpeg, "-y", "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=mono:sample_rate=24000",
        "-t", f"{max(duration_sec, 0.01):.3f}",
        "-c:a", "libmp3lame", "-b:a", "48k",
        out_path,
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"silence gen failed: {r.stderr[-300:]}")


def synthesize_srt_to_audio(
    srt_path: str,
    out_audio_path: str,
    voice: str,
    rate: str = "+0%",
    total_duration_sec: Optional[float] = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[Event] = None,
) -> str:
    """Synthesize an audio track aligned to subtitle timings.

    Builds per-cue MP3 fragments with edge-tts, concatenates them with silent
    gaps so that each cue starts roughly at its subtitle timestamp, and pads
    out to total_duration_sec if given. Output container is determined by ext.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found (brew install ffmpeg)")

    cues = parse_srt(srt_path)
    if not cues:
        raise RuntimeError("no cues parsed from SRT")

    work_dir = out_audio_path + ".parts"
    os.makedirs(work_dir, exist_ok=True)

    concat_lines: list[str] = []
    cursor = 0.0
    n = len(cues)
    # Maximum atempo speedup before voice starts to sound unnatural. Anything
    # above this is allowed to overrun the slot rather than be chipmunk'd.
    MAX_SPEEDUP = 1.7
    for i, cue in enumerate(cues):
        if cancel_event and cancel_event.is_set():
            return ""
        # The slot a cue may occupy is "from its own start until the next cue
        # starts" (or until total_duration_sec for the last cue). This is what
        # keeps the whole track from drifting: each cue gets stretched/squashed
        # to fit, instead of pushing every later cue late.
        if i + 1 < n:
            next_start = cues[i + 1].start_sec
        elif total_duration_sec:
            next_start = total_duration_sec
        else:
            next_start = cue.end_sec
        slot = max(next_start - cue.start_sec, 0.3)

        if cue.start_sec > cursor + 0.05:
            gap = os.path.join(work_dir, f"gap_{i:04d}.mp3")
            _silence_mp3(cue.start_sec - cursor, gap)
            concat_lines.append(f"file '{gap}'")
            cursor = cue.start_sec

        clip = os.path.join(work_dir, f"cue_{i:04d}.mp3")
        try:
            asyncio.run(_synthesize_cue_async(cue.text, voice, clip, rate=rate))
        except Exception as e:
            logger.warning("TTS failed for cue %s (%r): %s", i, cue.text[:40], e)
            # Substitute silence so timing isn't lost
            gap = os.path.join(work_dir, f"sub_{i:04d}.mp3")
            _silence_mp3(max(cue.end_sec - cue.start_sec, 0.3), gap)
            concat_lines.append(f"file '{gap}'")
            cursor = cue.end_sec
            if progress_cb:
                progress_cb(min((i + 1) / n * 0.9, 0.9), f"Cue {i + 1}/{n} (silent fallback)")
            continue

        clip_dur = _probe_duration(clip)

        # If the speech would run past the next cue's start, squash it to fit.
        # Cap the speedup so we don't get unintelligible audio — any residual
        # overflow is small and doesn't compound (the next cue still re-anchors
        # to its own start_sec via the gap logic above).
        if clip_dur > slot + 0.05 and slot > 0.1:
            ideal = clip_dur / slot
            speed = min(ideal, MAX_SPEEDUP)
            stretched = os.path.join(work_dir, f"cue_{i:04d}_fit.mp3")
            try:
                _atempo_mp3(clip, stretched, speed)
                stretched_dur = _probe_duration(stretched)
                if stretched_dur > 0:
                    clip = stretched
                    clip_dur = stretched_dur
            except Exception as e:
                logger.warning("atempo failed for cue %s: %s", i, e)

        concat_lines.append(f"file '{clip}'")
        cursor += clip_dur

        if progress_cb:
            progress_cb(min((i + 1) / n * 0.9, 0.9), f"Cue {i + 1}/{n}")

    if total_duration_sec and total_duration_sec > cursor + 0.05:
        tail = os.path.join(work_dir, "tail.mp3")
        _silence_mp3(total_duration_sec - cursor, tail)
        concat_lines.append(f"file '{tail}'")

    concat_path = os.path.join(work_dir, "concat.txt")
    with open(concat_path, "w", encoding="utf-8") as f:
        f.write("\n".join(concat_lines) + "\n")

    if progress_cb:
        progress_cb(0.95, "Concatenating audio…")

    ext = os.path.splitext(out_audio_path)[1].lower()
    codec_args = ["-c:a", "libmp3lame", "-b:a", "192k"] if ext == ".mp3" else ["-c:a", "aac", "-b:a", "192k"]

    r = subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_path, *codec_args, out_audio_path],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"concat failed: {r.stderr[-400:]}")

    # Cleanup fragments — keep final output only
    for name in os.listdir(work_dir):
        try:
            os.remove(os.path.join(work_dir, name))
        except OSError:
            pass
    try:
        os.rmdir(work_dir)
    except OSError:
        pass

    if progress_cb:
        progress_cb(1.0, "Voice generated")
    return out_audio_path


def mux_audio_track(
    video_path: str,
    audio_path: str,
    out_path: str,
    language: str = "und",
    title: str = "Translated voice",
    make_default: bool = False,
) -> str:
    """Mux an additional audio track into a video, preserving original streams."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    args = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v?", "-map", "0:a?", "-map", "0:s?", "-map", "1:a",
        "-c:v", "copy", "-c:a", "copy", "-c:s", "copy",
        "-metadata:s:a:1", f"language={language}",
        "-metadata:s:a:1", f"title={title}",
    ]
    if make_default:
        args += ["-disposition:a:0", "0", "-disposition:a:1", "default"]
    args += [out_path]

    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"mux failed: {r.stderr[-400:]}")
    return out_path


def _probe_duration(path: str) -> float:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return 0.0
    r = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True, timeout=10)
    for line in (r.stderr or "").splitlines():
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s)
    return 0.0
