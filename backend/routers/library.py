import os
import re
import shutil
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, or_, select

from backend.db import engine
from backend.models_db import Download, MediaFile, Task
from backend.schemas import (
    MediaFileResponse,
    SubtitleCueDTO,
    SubtitleCuesResponse,
    TranslateSubtitleRequest,
    UpdateSubtitleCuesRequest,
)
from backend.settings import settings
from core.library_service import register_media_file
from core.subtitle_service import srt_to_vtt, translate_cues, write_srt
from core.voice_service import parse_srt


router = APIRouter(prefix="/api", tags=["library"])


def _archive_dir() -> str:
    path = os.path.join(settings.data_dir, "archive")
    os.makedirs(path, exist_ok=True)
    return path


@router.get("/library", response_model=list[MediaFileResponse])
def list_library(
    kind: Optional[str] = None,
    q: Optional[str] = None,
    archived: bool = False,
    limit: int = 200,
    offset: int = 0,
):
    with Session(engine) as s:
        stmt = select(MediaFile).order_by(MediaFile.created_at.desc())
        if archived:
            stmt = stmt.where(MediaFile.archived_at.is_not(None))
        else:
            stmt = stmt.where(MediaFile.archived_at.is_(None))
        if kind:
            stmt = stmt.where(MediaFile.kind == kind)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(MediaFile.filename.like(like))
        return s.exec(stmt.offset(offset).limit(limit)).all()


@router.get("/library/{media_id}", response_model=MediaFileResponse)
def get_media(media_id: str):
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not mf:
            raise HTTPException(404, "not found")
        return mf


@router.get("/library/{media_id}/stream")
def stream_media(media_id: str):
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
    if not mf or not os.path.exists(mf.path):
        raise HTTPException(404, "file not found")
    return FileResponse(mf.path, filename=mf.filename)


@router.get("/library/{media_id}/subtitles", response_model=list[MediaFileResponse])
def list_subtitles(media_id: str):
    with Session(engine) as s:
        target = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not target:
            raise HTTPException(404, "media not found")
        parent_id = target.parent_id or target.id
        stmt = select(MediaFile).where(
            MediaFile.kind == "subtitle",
            MediaFile.archived_at.is_(None),
            or_(MediaFile.parent_id == media_id, MediaFile.parent_id == parent_id),
        ).order_by(MediaFile.created_at.desc())
        return s.exec(stmt).all()


@router.get("/library/{media_id}/audio_tracks", response_model=list[MediaFileResponse])
def list_audio_tracks(media_id: str):
    """Audio sidecars derived from the given video (e.g. translated voice MP3s)."""
    with Session(engine) as s:
        target = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not target:
            raise HTTPException(404, "media not found")
        parent_id = target.parent_id or target.id
        stmt = select(MediaFile).where(
            MediaFile.kind == "audio",
            MediaFile.archived_at.is_(None),
            or_(MediaFile.parent_id == media_id, MediaFile.parent_id == parent_id),
        ).order_by(MediaFile.created_at.desc())
        return s.exec(stmt).all()


@router.get("/library/{media_id}/vtt")
def serve_vtt(media_id: str):
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
    if not mf or mf.kind != "subtitle" or not os.path.exists(mf.path):
        raise HTTPException(404, "subtitle not found")
    if mf.path.lower().endswith(".vtt"):
        return FileResponse(mf.path, media_type="text/vtt")
    vtt_sibling = os.path.splitext(mf.path)[0] + ".vtt"
    if not os.path.exists(vtt_sibling):
        try:
            srt_to_vtt(mf.path, vtt_sibling)
        except Exception as e:
            raise HTTPException(500, f"VTT conversion failed: {e}")
    return FileResponse(vtt_sibling, media_type="text/vtt")


@router.get("/library/{media_id}/cues", response_model=SubtitleCuesResponse)
def get_subtitle_cues(media_id: str):
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
    if not mf or mf.kind != "subtitle" or not os.path.exists(mf.path):
        raise HTTPException(404, "subtitle not found")
    cues = [
        SubtitleCueDTO(index=c.index, start_sec=c.start_sec, end_sec=c.end_sec, text=c.text)
        for c in parse_srt(mf.path)
    ]
    return SubtitleCuesResponse(media_file_id=media_id, cues=cues)


@router.put("/library/{media_id}/cues", response_model=MediaFileResponse)
def update_subtitle_cues(media_id: str, req: UpdateSubtitleCuesRequest):
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not mf or mf.kind != "subtitle":
            raise HTTPException(404, "subtitle not found")
        if not mf.path or not os.path.exists(mf.path):
            raise HTTPException(404, "subtitle file missing on disk")

        cue_dicts = [c.model_dump() for c in req.cues]
        write_srt(cue_dicts, mf.path)
        try:
            srt_to_vtt(mf.path)
        except Exception:
            pass
        mf.size_bytes = os.path.getsize(mf.path)
        s.add(mf)
        s.commit()
        s.refresh(mf)
        return mf


@router.post("/library/{media_id}/translate", response_model=MediaFileResponse)
def translate_subtitle(media_id: str, req: TranslateSubtitleRequest):
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not mf or mf.kind != "subtitle" or not os.path.exists(mf.path):
            raise HTTPException(404, "subtitle not found")

        cues = [
            {"index": c.index, "start_sec": c.start_sec, "end_sec": c.end_sec, "text": c.text}
            for c in parse_srt(mf.path)
        ]
        if not cues:
            raise HTTPException(400, "subtitle has no parseable cues")

        try:
            translated = translate_cues(cues, target=req.target_language, source=req.source_language)
        except RuntimeError as e:
            raise HTTPException(500, str(e))

        if req.save_as_new:
            base = os.path.splitext(mf.filename)[0]
            base = re.sub(r"\.[a-z]{2,3}$", "", base, flags=re.IGNORECASE)
            out_dir = settings.subtitles_dir
            os.makedirs(out_dir, exist_ok=True)
            new_path = os.path.join(out_dir, f"{base}.{req.target_language}.srt")
            counter = 1
            while os.path.exists(new_path):
                new_path = os.path.join(out_dir, f"{base}.{req.target_language}__{counter}.srt")
                counter += 1
            write_srt(translated, new_path)
            try:
                srt_to_vtt(new_path)
            except Exception:
                pass
            parent_id = mf.parent_id or mf.id
            new_id = register_media_file(
                new_path,
                kind="subtitle",
                source_url=mf.source_url,
                parent_id=parent_id,
            )
            new_mf = s.exec(select(MediaFile).where(MediaFile.id == new_id)).first()
            return new_mf
        else:
            write_srt(translated, mf.path)
            try:
                srt_to_vtt(mf.path)
            except Exception:
                pass
            mf.size_bytes = os.path.getsize(mf.path)
            s.add(mf)
            s.commit()
            s.refresh(mf)
            return mf


@router.get("/library/{media_id}/thumbnail")
def thumbnail(media_id: str):
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
    if not mf or not mf.thumbnail_path or not os.path.exists(mf.thumbnail_path):
        raise HTTPException(404, "no thumbnail")
    return FileResponse(mf.thumbnail_path, media_type="image/jpeg")


@router.delete("/library/{media_id}")
def archive_media(media_id: str):
    """Soft-delete: move the file into data/archive/<id>/ and set archived_at."""
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not mf:
            raise HTTPException(404, "not found")
        if mf.archived_at is not None:
            return {"ok": True, "already_archived": True}

        bucket = os.path.join(_archive_dir(), mf.id)
        os.makedirs(bucket, exist_ok=True)

        new_path = mf.path
        if os.path.exists(mf.path):
            target = os.path.join(bucket, os.path.basename(mf.path))
            shutil.move(mf.path, target)
            new_path = target

        new_thumb = mf.thumbnail_path
        if mf.thumbnail_path and os.path.exists(mf.thumbnail_path):
            target = os.path.join(bucket, os.path.basename(mf.thumbnail_path))
            shutil.move(mf.thumbnail_path, target)
            new_thumb = target

        mf.path = new_path
        mf.thumbnail_path = new_thumb
        mf.archived_at = datetime.utcnow()
        s.add(mf)
        s.commit()
    return {"ok": True}


@router.post("/library/{media_id}/restore", response_model=MediaFileResponse)
def restore_media(media_id: str):
    """Move file out of archive back to its original kind-specific directory and clear flag."""
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not mf:
            raise HTTPException(404, "not found")
        if mf.archived_at is None:
            return mf

        if mf.kind == "subtitle":
            restore_dir = settings.subtitles_dir
        elif mf.kind == "audio":
            restore_dir = settings.converted_dir
        else:
            restore_dir = settings.downloads_dir
        os.makedirs(restore_dir, exist_ok=True)

        new_path = mf.path
        if os.path.exists(mf.path):
            target = os.path.join(restore_dir, os.path.basename(mf.path))
            if os.path.exists(target):
                base, ext = os.path.splitext(os.path.basename(mf.path))
                target = os.path.join(restore_dir, f"{base}__restored{ext}")
            shutil.move(mf.path, target)
            new_path = target

        new_thumb = mf.thumbnail_path
        if mf.thumbnail_path and os.path.exists(mf.thumbnail_path):
            thumb_dir = os.path.join(settings.data_dir, "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            target = os.path.join(thumb_dir, os.path.basename(mf.thumbnail_path))
            shutil.move(mf.thumbnail_path, target)
            new_thumb = target

        # Best-effort: remove now-empty archive bucket
        bucket = os.path.join(_archive_dir(), mf.id)
        if os.path.isdir(bucket):
            try:
                shutil.rmtree(bucket)
            except OSError:
                pass

        mf.path = new_path
        mf.thumbnail_path = new_thumb
        mf.archived_at = None
        s.add(mf)
        s.commit()
        s.refresh(mf)
        return mf


@router.delete("/library/{media_id}/permanent")
def permanent_delete(media_id: str):
    """Hard delete: drop the DB row and remove archived files."""
    paths_to_remove: list[str] = []
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not mf:
            raise HTTPException(404, "not found")
        if mf.path:
            paths_to_remove.append(mf.path)
        if mf.thumbnail_path:
            paths_to_remove.append(mf.thumbnail_path)

        # Detach references from history rows so SQLite's FK constraint doesn't
        # block deletion (Task.media_file_id and Download.media_file_id point here).
        for t in s.exec(select(Task).where(Task.media_file_id == media_id)).all():
            t.media_file_id = None
            s.add(t)
        for dl in s.exec(select(Download).where(Download.media_file_id == media_id)).all():
            dl.media_file_id = None
            s.add(dl)

        # Cascade-delete any child rows (e.g. subtitle MediaFiles attached to this video).
        for child in s.exec(select(MediaFile).where(MediaFile.parent_id == media_id)).all():
            if child.path:
                paths_to_remove.append(child.path)
            if child.thumbnail_path:
                paths_to_remove.append(child.thumbnail_path)
            for t in s.exec(select(Task).where(Task.media_file_id == child.id)).all():
                t.media_file_id = None
                s.add(t)
            for dl in s.exec(select(Download).where(Download.media_file_id == child.id)).all():
                dl.media_file_id = None
                s.add(dl)
            s.delete(child)

        s.delete(mf)
        s.commit()

    for p in paths_to_remove:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    bucket = os.path.join(_archive_dir(), media_id)
    if os.path.isdir(bucket):
        try:
            shutil.rmtree(bucket)
        except OSError:
            pass
    return {"ok": True}


@router.post("/library/upload", response_model=MediaFileResponse)
async def upload_media(file: UploadFile = File(...)):
    """Upload a local video/audio/subtitle file into the library."""
    if not file.filename:
        raise HTTPException(400, "missing filename")

    ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
    audio_exts = {"mp3", "wav", "m4a", "flac", "aac", "ogg", "opus"}
    sub_exts = {"srt", "vtt", "ass", "ssa"}
    if ext in sub_exts:
        kind = "subtitle"
        dest_dir = settings.subtitles_dir
    elif ext in audio_exts:
        kind = "audio"
        dest_dir = settings.downloads_dir
    else:
        kind = "video"
        dest_dir = settings.downloads_dir

    os.makedirs(dest_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    dest_path = os.path.join(dest_dir, safe_name)
    base, suffix = os.path.splitext(safe_name)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(dest_dir, f"{base}__{counter}{suffix}")
        counter += 1

    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)

    media_id = register_media_file(dest_path, kind=kind, source_url=f"local://upload/{os.path.basename(dest_path)}")
    with Session(engine) as s:
        mf = s.exec(select(MediaFile).where(MediaFile.id == media_id)).first()
        if not mf:
            raise HTTPException(500, "failed to register file")
        return mf
