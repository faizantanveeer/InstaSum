from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import queue
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, send_file, send_from_directory, stream_with_context

from ..db import get_session, upsert_reel_fts
from ..models import Job, Profile, Reel
from ..services.auth import current_user, login_required
from ..services.media import MediaError, download_reel_audio, download_reel_thumbnail
from ..services.summarization import SummarizationService
from ..services.transcription import TranscriptionError, TranscriptionService

bp = Blueprint("api", __name__)

_JOB_STREAMS: dict[int, dict] = {}


def _init_stream_state(job_id: int):
    state = _JOB_STREAMS.get(job_id)
    if state is None:
        state = {"queue": queue.Queue(), "thread": None, "lock": threading.Lock()}
        _JOB_STREAMS[job_id] = state
    return state


def _emit_event(job_id: int, event: dict):
    state = _init_stream_state(job_id)
    state["queue"].put(event)


def _guess_audio_mimetype(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    if guessed and guessed.startswith("audio/"):
        return guessed
    return "audio/mpeg"


def _safe_commit(db):
    for attempt in range(5):
        try:
            db.commit()
            return True
        except Exception as exc:
            db.rollback()
            if "database is locked" in str(exc).lower() and attempt < 4:
                time.sleep(0.15 * (attempt + 1))
                continue
            return False


def _error_text(exc: Exception, fallback: str = "Unexpected processing error") -> str:
    text = str(exc).strip() if exc else ""
    if not text:
        text = exc.__class__.__name__ if exc else fallback
    if len(text) > 280:
        text = text[:277] + "..."
    return text or fallback


def _summary_preview(detail: str) -> str:
    text = " ".join((detail or "").split())
    if len(text) <= 420:
        return text
    return text[:420].rsplit(" ", 1)[0] + "..."


def _parse_regenerate() -> bool:
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        return bool(payload.get("regenerate"))
    value = (request.form.get("regenerate") or "").strip().lower()
    return value in ("1", "true", "yes", "on")


@bp.get("/proxy-image")
@login_required
def proxy_image():
    image_url = (request.args.get("url") or "").strip()
    if not image_url:
        abort(400)

    parsed = urlparse(image_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        abort(400)

    try:
        upstream = requests.get(
            image_url,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.instagram.com/",
            },
        )
    except requests.RequestException:
        abort(502)

    if upstream.status_code >= 400:
        abort(502)

    content_type = (upstream.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        abort(415)

    return Response(
        upstream.content,
        mimetype=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@bp.post("/api/reels/<int:reel_id>/generate")
@login_required
def generate_reel(reel_id: int):
    user = current_user()
    regenerate = _parse_regenerate()

    db = get_session()
    try:
        reel = db.query(Reel).filter(Reel.id == reel_id, Reel.user_id == user.id).first()
        if not reel:
            abort(404)

        job = Job(
            profile_id=reel.profile_id,
            user_id=user.id,
            job_type="single",
            target_profile_id=reel.profile_id,
            target_reel_id=reel.id,
            status="queued",
            phase="queued",
            message="Queued",
            total_count=1,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
    finally:
        db.close()

    state = _init_stream_state(job.id)
    _start_job_thread(current_app._get_current_object(), job.id, user.id, [reel_id], regenerate, state)
    return {"job_id": job.id, "status": "queued", "total_targeted": 1}


@bp.post("/api/profiles/<int:profile_id>/generate-all")
@login_required
def generate_profile_all(profile_id: int):
    user = current_user()
    regenerate = _parse_regenerate()

    db = get_session()
    try:
        profile = db.get(Profile, profile_id)
        if not profile:
            abort(404)

        query = db.query(Reel).filter(Reel.profile_id == profile_id, Reel.user_id == user.id)
        if not regenerate:
            query = query.filter(Reel.processed.is_(False))
        reel_ids = [r.id for r in query.order_by(Reel.posted_at.is_(None), Reel.posted_at.desc()).all()]

        job = Job(
            profile_id=profile_id,
            user_id=user.id,
            job_type="batch",
            target_profile_id=profile_id,
            status="queued",
            phase="queued",
            message="Queued",
            total_count=len(reel_ids),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        if not reel_ids:
            job.status = "completed"
            job.phase = "completed"
            job.message = "No reels to process."
            job.finished_at = datetime.utcnow()
            db.commit()
            state = _init_stream_state(job.id)
            state["queue"].put(
                {
                    "type": "complete",
                    "message": "No reels to process.",
                    "processed": 0,
                    "total": 0,
                }
            )
            return {"job_id": job.id, "status": "completed", "total_targeted": 0}
    finally:
        db.close()

    state = _init_stream_state(job.id)
    _start_job_thread(current_app._get_current_object(), job.id, user.id, reel_ids, regenerate, state)
    return {"job_id": job.id, "status": "queued", "total_targeted": len(reel_ids)}


@bp.get("/api/stream/<int:job_id>")
@login_required
def stream_job(job_id: int):
    user = current_user()
    db = get_session()
    try:
        job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            abort(404)
    finally:
        db.close()

    state = _init_stream_state(job_id)
    thread_obj = state.get("thread")
    if state["queue"].empty() and (thread_obj is None or not thread_obj.is_alive()):
        if job.status in ("completed", "partial_failed"):
            state["queue"].put(
                {
                    "type": "complete",
                    "message": job.message or "Completed",
                    "processed": job.processed_count or 0,
                    "total": job.total_count or 0,
                    "success": job.success_count or 0,
                    "failed": job.failed_count or 0,
                    "skipped": job.skipped_count or 0,
                }
            )
        elif job.status == "failed":
            state["queue"].put({"type": "error", "message": job.message or "Failed"})

    def gen():
        q = state["queue"]
        while True:
            try:
                event = q.get(timeout=25)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("complete", "error"):
                break

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@bp.get("/thumbnails/<username>/<path:filename>")
@login_required
def thumbnails(username: str, filename: str):
    user = current_user()
    db = get_session()
    try:
        reel = (
            db.query(Reel)
            .filter(Reel.user_id == user.id, Reel.username == username, Reel.thumbnail_path == filename)
            .first()
        )
        if not reel:
            abort(404)

        base_dir = current_app.config["DOWNLOADS_DIR"]
        user_dir = os.path.join(base_dir, username)
        local_path = os.path.join(user_dir, filename)
        if os.path.exists(local_path):
            return send_from_directory(user_dir, filename)

        # Backward compatibility: if old DB rows store bare filename, also check thumbnails subfolder.
        if "/" not in filename and "\\" not in filename:
            alt_filename = f"thumbnails/{filename}"
            alt_path = os.path.join(user_dir, alt_filename)
            if os.path.exists(alt_path):
                reel.thumbnail_path = alt_filename
                _safe_commit(db)
                return send_from_directory(user_dir, alt_filename)

        # Attempt to recover a missing local thumbnail one time.
        try:
            recovered = download_reel_thumbnail(
                reel.reel_url,
                reel.shortcode,
                username,
                base_dir,
                current_app.config["IG_COOKIES_FILE"],
            )
        except Exception:
            recovered = None

        if recovered:
            recovered_path = os.path.join(user_dir, recovered)
            reel.thumbnail_path = recovered
            _safe_commit(db)
            if os.path.exists(recovered_path):
                return send_from_directory(user_dir, recovered)

        # Final fallback to provider URL if available.
        if reel.thumbnail_url:
            return redirect(reel.thumbnail_url, code=302)

        abort(404)
    finally:
        db.close()


@bp.get("/audio/<username>/<path:filename>")
@login_required
def audio(username: str, filename: str):
    user = current_user()
    db = get_session()

    try:
        normalized = (filename or "").replace("\\", "/").strip("/")
        file_name = os.path.basename(normalized)
        stem, _ = os.path.splitext(file_name)

        candidates = [normalized, file_name, f"audio/{file_name}"]

        reel = (
            db.query(Reel)
            .filter(
                Reel.user_id == user.id,
                Reel.username == username,
                Reel.audio_path.in_(candidates),
            )
            .first()
        )

        if not reel and stem:
            reel = (
                db.query(Reel)
                .filter(
                    Reel.user_id == user.id,
                    Reel.username == username,
                    Reel.shortcode == stem,
                )
                .first()
            )
            
        if not reel:
            current_app.logger.warning("No reel found in DB")
            abort(404)

        base_dir = current_app.config["DOWNLOADS_DIR"]
        user_dir = os.path.join(base_dir, username)

        paths_to_try = []

        if reel.audio_path:
            paths_to_try.append((reel.audio_path or "").replace("\\", "/").strip("/"))

        paths_to_try.extend([
            normalized,
            f"audio/{file_name}",
            file_name
        ])

        if reel.shortcode:
            paths_to_try.extend([
                f"audio/{reel.shortcode}.mp3",
                f"{reel.shortcode}.mp3"
            ])

        seen = set()
        for rel_path in paths_to_try:
            rel_path = rel_path.replace("\\", "/").strip("/")
            if not rel_path or rel_path in seen:
                continue

            seen.add(rel_path)
            local_path = os.path.join(user_dir, rel_path)

            if os.path.exists(local_path):

                if reel.audio_path != rel_path:
                    reel.audio_path = rel_path
                    _safe_commit(db)
                    
                abs_path = os.path.abspath(local_path)
                if not os.path.isfile(abs_path):
                    continue
                return send_file(
                    abs_path,
                    mimetype=_guess_audio_mimetype(abs_path),
                    conditional=True,
                    as_attachment=False,
                    max_age=3600,
                )

        abort(404)

    finally:
        db.close()

@bp.get("/export/profile/<int:profile_id>")
@login_required
def export_profile(profile_id: int):
    user = current_user()
    fmt = request.args.get("format", "csv").lower()

    db = get_session()
    try:
        profile = db.get(Profile, profile_id)
        if not profile:
            abort(404)

        reels = (
            db.query(Reel)
            .filter(Reel.user_id == user.id, Reel.profile_id == profile_id)
            .order_by(Reel.posted_at.is_(None), Reel.posted_at.desc())
            .all()
        )

        if fmt == "json":
            data = {
                "profile_id": profile_id,
                "username": profile.username,
                "reels": [_reel_to_dict(r) for r in reels[: current_app.config["EXPORT_MAX_ROWS"]]],
            }
            return Response(
                json.dumps(data, default=str),
                mimetype="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=insta_reels_{profile.username}.json"
                },
            )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "url",
                "title",
                "summary",
                "summary_detail",
                "transcript",
                "date",
                "views",
                "likes",
                "comments",
            ]
        )
        for r in reels[: current_app.config["EXPORT_MAX_ROWS"]]:
            writer.writerow(
                [
                    r.reel_url,
                    r.ai_title or "",
                    r.ai_summary or "",
                    r.summary_detail or "",
                    r.transcript or "",
                    r.posted_at.isoformat() if r.posted_at else "",
                    r.view_count or "",
                    r.like_count or "",
                    r.comment_count or "",
                ]
            )

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=insta_reels_{profile.username}.csv"
            },
        )
    finally:
        db.close()


def _start_job_thread(app, job_id: int, user_id: int, reel_ids: list[int], regenerate: bool, state: dict):
    with state["lock"]:
        t = state.get("thread")
        if t and t.is_alive():
            return
        t = threading.Thread(
            target=_process_job,
            args=(app, job_id, user_id, reel_ids, regenerate),
            daemon=True,
        )
        state["thread"] = t
        t.start()


def _process_job(app, job_id: int, user_id: int, reel_ids: list[int], regenerate: bool):
    with app.app_context():
        db = get_session()
        try:
            job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
            if not job:
                _emit_event(job_id, {"type": "error", "message": "Job not found."})
                return

            job.status = "running"
            job.phase = "running"
            job.message = "Starting processing..."
            job.started_at = datetime.utcnow()
            if not job.total_count:
                job.total_count = len(reel_ids)
            _safe_commit(db)

            _emit_event(
                job_id,
                {
                    "type": "progress",
                    "message": "Starting processing...",
                    "processed": 0,
                    "total": job.total_count,
                    "percent": 0,
                },
            )

            tx = TranscriptionService(
                app.config["WHISPER_MODEL"],
                app.config["FFMPEG_LOCATION"],
            )
            sm = SummarizationService(
                app.config["OPENAI_API_KEY"],
                app.config["OPENAI_SUMMARY_MODEL"],
                {
                    "endpoint": app.config["AZURE_OPENAI_ENDPOINT"],
                    "api_key": app.config["AZURE_OPENAI_API_KEY"],
                    "api_version": app.config["AZURE_OPENAI_API_VERSION"],
                    "deployment": app.config["AZURE_OPENAI_DEPLOYMENT"],
                },
            )

            profile_cache = {}

            for index, reel_id in enumerate(reel_ids, start=1):
                outcome = "failed"
                status_message = "Unexpected processing error"
                reel = db.query(Reel).filter(Reel.id == reel_id, Reel.user_id == user_id).first()

                if not reel:
                    outcome = "failed"
                    status_message = "Reel not found"
                else:
                    try:
                        if reel.processed and not regenerate:
                            outcome = "skipped"
                            status_message = "Already processed"
                        else:
                            reel.processing_status = "processing"
                            reel.error_reason = None
                            _safe_commit(db)

                            profile = profile_cache.get(reel.profile_id)
                            if profile is None:
                                profile = db.get(Profile, reel.profile_id)
                                profile_cache[reel.profile_id] = profile
                            username = reel.username or (profile.username if profile else "")
                            if not username:
                                raise MediaError("Missing username for reel")

                            _emit_event(
                                job_id,
                                {
                                    "type": "progress",
                                    "message": f"Preparing media for reel {index}/{len(reel_ids)}",
                                    "processed": job.processed_count,
                                    "total": job.total_count,
                                    "percent": int((job.processed_count / max(job.total_count, 1)) * 100),
                                },
                            )

                            audio_full_path = ""
                            if reel.audio_path:
                                candidate = os.path.join(app.config["DOWNLOADS_DIR"], username, reel.audio_path)
                                if os.path.exists(candidate):
                                    audio_full_path = candidate
                                elif "/" not in reel.audio_path and "\\" not in reel.audio_path:
                                    alt_rel = f"audio/{reel.audio_path}"
                                    alt_candidate = os.path.join(app.config["DOWNLOADS_DIR"], username, alt_rel)
                                    if os.path.exists(alt_candidate):
                                        reel.audio_path = alt_rel
                                        _safe_commit(db)
                                        audio_full_path = alt_candidate

                            if not audio_full_path:
                                media = download_reel_audio(
                                    reel.reel_url,
                                    reel.shortcode,
                                    username,
                                    app.config["DOWNLOADS_DIR"],
                                    app.config["IG_COOKIES_FILE"],
                                    app.config["FFMPEG_LOCATION"],
                                )
                                reel.audio_path = media.get("audio_file")
                                if media.get("thumbnail_file"):
                                    reel.thumbnail_path = media.get("thumbnail_file")
                                _safe_commit(db)
                                if reel.audio_path:
                                    audio_full_path = os.path.join(app.config["DOWNLOADS_DIR"], username, reel.audio_path)

                            if not audio_full_path or not os.path.exists(audio_full_path):
                                raise MediaError("Audio file is missing after download")
                            if os.path.getsize(audio_full_path) < 1024:
                                raise MediaError("Downloaded audio appears empty or invalid")

                            _emit_event(
                                job_id,
                                {
                                    "type": "progress",
                                    "message": f"Transcribing reel {index}/{len(reel_ids)}",
                                    "processed": job.processed_count,
                                    "total": job.total_count,
                                    "percent": int((job.processed_count / max(job.total_count, 1)) * 100),
                                },
                            )

                            raw_transcript = tx.transcribe(audio_full_path)
                            if raw_transcript.strip():
                                reel.transcript = raw_transcript
                                reel.transcript_status = "ok"
                            else:
                                reel.transcript = "No spoken content detected."
                                reel.transcript_status = "no_speech"

                            _emit_event(
                                job_id,
                                {
                                    "type": "progress",
                                    "message": f"Generating summary for reel {index}/{len(reel_ids)}",
                                    "processed": job.processed_count,
                                    "total": job.total_count,
                                    "percent": int((job.processed_count / max(job.total_count, 1)) * 100),
                                },
                            )

                            title, detailed_summary = sm.summarize(raw_transcript or "", reel.caption or "")
                            reel.ai_title = title or "Untitled Reel"
                            reel.summary_detail = detailed_summary or ""
                            reel.ai_summary = _summary_preview(reel.summary_detail)
                            reel.processing_status = "completed"
                            reel.processed = True
                            reel.error_reason = None
                            _safe_commit(db)

                            # FTS is useful but non-critical. A failure here should not fail the reel.
                            try:
                                upsert_reel_fts(
                                    db,
                                    reel.id,
                                    reel.ai_title,
                                    reel.ai_summary,
                                    reel.transcript,
                                    reel.summary_detail,
                                )
                                _safe_commit(db)
                            except Exception as exc:
                                db.rollback()
                                current_app.logger.warning(
                                    "FTS update failed for reel_id=%s: %s",
                                    reel.id,
                                    _error_text(exc, "FTS update failed"),
                                )

                            outcome = "success"
                            status_message = "Processed"

                    except (MediaError, TranscriptionError) as exc:
                        current_app.logger.exception(
                            "Media/Transcription failure for reel_id=%s job_id=%s",
                            reel_id,
                            job_id,
                        )
                        db.rollback()
                        reel = db.query(Reel).filter(Reel.id == reel_id, Reel.user_id == user_id).first()
                        if reel:
                            reel.processing_status = "failed"
                            reel.error_reason = _error_text(exc)
                            _safe_commit(db)
                        outcome = "failed"
                        status_message = _error_text(exc)
                    except Exception as exc:
                        current_app.logger.exception(
                            "Unexpected failure for reel_id=%s job_id=%s",
                            reel_id,
                            job_id,
                        )
                        db.rollback()
                        reel = db.query(Reel).filter(Reel.id == reel_id, Reel.user_id == user_id).first()
                        if reel:
                            reel.processing_status = "failed"
                            reel.error_reason = _error_text(exc)
                            _safe_commit(db)
                        outcome = "failed"
                        status_message = _error_text(exc)

                job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
                if not job:
                    _emit_event(job_id, {"type": "error", "message": "Job context lost."})
                    return

                if outcome == "success":
                    job.success_count += 1
                elif outcome == "skipped":
                    job.skipped_count += 1
                else:
                    job.failed_count += 1
                job.processed_count += 1
                job.message = status_message
                _safe_commit(db)

                percent = int((job.processed_count / max(job.total_count, 1)) * 100)
                _emit_event(
                    job_id,
                    {
                        "type": "progress",
                        "message": f"Processed {job.processed_count} of {job.total_count}",
                        "meta": status_message,
                        "processed": job.processed_count,
                        "total": job.total_count,
                        "percent": percent,
                    },
                )

                reel = db.query(Reel).filter(Reel.id == reel_id, Reel.user_id == user_id).first()
                if reel:
                    reel_html = ""
                    try:
                        reel_html = render_template("partials/reel_card.html", reel=reel)
                    except Exception:
                        reel_html = ""
                    _emit_event(
                        job_id,
                        {
                            "type": "reel_update",
                            "reel_id": reel.id,
                            "html": reel_html,
                        },
                    )

            job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
            if not job:
                _emit_event(job_id, {"type": "error", "message": "Job finalization failed."})
                return

            job.phase = "completed"
            if job.failed_count > 0 and job.success_count > 0:
                job.status = "partial_failed"
                job.message = "Completed with some failures."
            elif job.failed_count > 0 and job.success_count == 0:
                job.status = "failed"
                job.phase = "failed"
                job.message = "All reels failed."
            else:
                job.status = "completed"
                if job.skipped_count > 0 and job.success_count == 0:
                    job.message = "No reels required processing."
                else:
                    job.message = "Completed"
            job.finished_at = datetime.utcnow()
            _safe_commit(db)

            _emit_event(
                job_id,
                {
                    "type": "complete",
                    "message": job.message,
                    "processed": job.processed_count,
                    "total": job.total_count,
                    "success": job.success_count,
                    "failed": job.failed_count,
                    "skipped": job.skipped_count,
                },
            )
        except Exception as exc:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
            if job:
                job.status = "failed"
                job.phase = "failed"
                job.message = "Unexpected job error"
                job.finished_at = datetime.utcnow()
                _safe_commit(db)
            _emit_event(job_id, {"type": "error", "message": str(exc)})
        finally:
            db.close()


def _reel_to_dict(r: Reel):
    return {
        "url": r.reel_url,
        "title": r.ai_title,
        "summary": r.ai_summary,
        "summary_detail": r.summary_detail,
        "transcript": r.transcript,
        "date": r.posted_at.isoformat() if r.posted_at else None,
        "views": r.view_count,
        "likes": r.like_count,
        "comments": r.comment_count,
    }
