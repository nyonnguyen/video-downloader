import os
from threading import Event
from typing import Callable, Optional

from sqlmodel import Session, select

from backend.db import engine
from backend.models_db import MediaFile
from backend.queue import register_runner
from backend.settings import settings
from core.library_service import register_media_file
from core.subtitle_service import (
    srt_to_vtt,
    transcribe_to_srt,
    translate_cues,
    write_srt,
)
from core.voice_service import mux_audio_track, parse_srt, synthesize_srt_to_audio
from utils.logging import get_logger

logger = get_logger("voice_runner")


def _get_media(media_id: str) -> Optional[MediaFile]:
    with Session(engine) as s:
        return s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()


@register_runner("voice")
def run(task_id: str, payload: dict, progress_cb: Callable[[float, str], None], cancel_event: Event) -> dict:
    media_id = payload["media_file_id"]
    subtitle_id = payload.get("subtitle_file_id")
    voice = payload.get("voice", "en-US-AriaNeural")
    rate = payload.get("rate", "+0%")
    mux = payload.get("mux_into_video", False)
    make_default = payload.get("make_default_track", False)
    whisper_model = payload.get("whisper_model", "small")
    source_language = payload.get("source_language")
    # Target language for the voice. Default to the voice locale's language
    # prefix (e.g. vi-VN-NamMinhNeural → "vi") so the SRT we feed to TTS
    # actually matches the voice the user picked.
    target_language = (payload.get("target_language") or voice.split("-", 1)[0] or "en").lower()

    src = _get_media(media_id)
    if src is None or not os.path.exists(src.path):
        raise FileNotFoundError(f"video {media_id}")

    base = os.path.splitext(src.filename)[0]

    # Resolve the SRT to drive TTS
    if subtitle_id:
        sub = _get_media(subtitle_id)
        if sub is None or sub.kind != "subtitle" or not os.path.exists(sub.path):
            raise FileNotFoundError(f"subtitle {subtitle_id}")
        srt_path = sub.path
        sub_parent = sub.id
    else:
        progress_cb(0.0, f"Transcribing with whisper ({whisper_model})…")
        transcribe_target_en = target_language == "en"
        srt_out = os.path.join(
            settings.subtitles_dir,
            f"{base}.{target_language if transcribe_target_en else 'src'}.srt",
        )
        srt_path, detected = transcribe_to_srt(
            src.path, srt_out,
            model_name=whisper_model,
            language=source_language,
            translate_to_en=transcribe_target_en,
            progress_cb=lambda p, m: progress_cb(p * 0.3, m),
            cancel_event=cancel_event,
        )
        if not srt_path:
            return {}

        # If the target language isn't English, run the cues through Google
        # Translate so the TTS voice actually speaks its native language.
        if not transcribe_target_en and (detected or "").lower() != target_language:
            progress_cb(0.3, f"Translating subtitles to {target_language}…")
            cues = parse_srt(srt_path)
            translated = translate_cues(
                [
                    {
                        "index": c.index,
                        "start_sec": c.start_sec,
                        "end_sec": c.end_sec,
                        "text": c.text,
                    }
                    for c in cues
                ],
                target=target_language,
                source=detected or None,
                progress_cb=lambda p, m: progress_cb(0.3 + p * 0.1, m),
            )
            srt_path = os.path.join(
                settings.subtitles_dir, f"{base}.{target_language}.srt"
            )
            write_srt(translated, srt_path)

        try:
            srt_to_vtt(srt_path)
        except Exception as e:
            logger.warning("VTT generation failed: %s", e)
        sub_parent = register_media_file(srt_path, kind="subtitle", source_url=src.source_url, parent_id=src.id)

    # Synthesize audio aligned to subtitle timings
    voice_dir = os.path.join(settings.converted_dir)
    os.makedirs(voice_dir, exist_ok=True)
    safe_voice = voice.replace("/", "_")
    audio_path = os.path.join(voice_dir, f"{base}__voice_{safe_voice}.mp3")

    progress_cb(0.4, f"Generating voice ({voice})…")
    synthesize_srt_to_audio(
        srt_path, audio_path,
        voice=voice, rate=rate,
        total_duration_sec=src.duration_sec or None,
        progress_cb=lambda p, m: progress_cb(0.4 + p * 0.5, m),
        cancel_event=cancel_event,
    )
    if cancel_event.is_set():
        return {}

    audio_id = register_media_file(audio_path, kind="audio", source_url=src.source_url, parent_id=src.id)
    primary_id = audio_id

    if mux:
        progress_cb(0.92, "Muxing voice track into video…")
        out_path = os.path.join(voice_dir, f"{base}__withvoice_{safe_voice}.mp4")
        mux_audio_track(
            src.path, audio_path, out_path,
            language=(voice.split("-", 1)[0] or "und"),
            title=f"Voice ({voice})",
            make_default=make_default,
        )
        primary_id = register_media_file(out_path, kind="video", source_url=src.source_url, parent_id=src.id)

    progress_cb(1.0, "Done")
    return {"media_file_id": primary_id}
