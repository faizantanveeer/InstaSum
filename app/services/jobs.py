from __future__ import annotations

import os
import time
import threading
from datetime import datetime, timedelta

from sqlalchemy import text

from ..db import get_session
from ..models import Job, Profile, Reel, ReelError
from .instagram import InstagramService, InstagramError
from .transcription import TranscriptionService, TranscriptionError
from .summarization import SummarizationService
from .media import download_reel_media_tmp, MediaError
from .storage import upload_audio, upload_thumbnail
from .utils import ensure_dir

_worker_thread = None
_worker_event = threading.Event()


def start_worker(app):
    global _worker_thread
    if _worker_thread is not None:
        return

    def _loop():
        with app.app_context():
            _requeue_stale_jobs(app)
            while True:
                job_id = _get_next_queued_job_id()
                if job_id is None:
                    _worker_event.wait(timeout=app.config["WORKER_POLL_SECONDS"])
                    _worker_event.clear()
                    continue
                try:
                    _process_job(app, job_id)
                except Exception:
                    # If job crashes unexpectedly, move to failed state
                    _mark_job_failed(job_id, "Unexpected error during processing")

    _worker_thread = threading.Thread(target=_loop, daemon=True)
    _worker_thread.start()


def enqueue_job(profile_id: int):
    session = get_session()
    try:
        job = Job(profile_id=profile_id, status="queued", phase="queued", message="Queued")
        session.add(job)
        session.commit()
        session.refresh(job)
    finally:
        session.close()
    _worker_event.set()
    return job


def _requeue_stale_jobs(app):
    cutoff = datetime.utcnow() - timedelta(minutes=app.config["STALE_JOB_MINUTES"])
    session = get_session()
    try:
        session.execute(
            text(
                "UPDATE jobs SET status='queued', phase='queued', message='Requeued after stale run' "
                "WHERE status='running' AND started_at < :cutoff"
            ),
            {"cutoff": cutoff},
        )
        session.commit()
    finally:
        session.close()


def _get_next_queued_job_id():
    session = get_session()
    try:
        job = (
            session.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.requested_at.asc())
            .first()
        )
        if not job:
            return None
        job.status = "running"
        job.phase = "fetching_reels"
        job.started_at = datetime.utcnow()
        job.message = "Fetching reels..."
        session.commit()
        return job.id
    finally:
        session.close()


def _mark_job_failed(job_id: int, message: str):
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            return
        job.status = "failed"
        job.phase = "failed"
        job.message = message
        job.finished_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()


def _process_job(app, job_id: int):
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            return
        profile = session.get(Profile, job.profile_id)
        if not profile:
            _mark_job_failed(job_id, "Profile not found")
            return

        ig = InstagramService(
            apify_token=app.config["APIFY_TOKEN"],
            ig_username=app.config["IG_USERNAME"],
            ig_password=app.config["IG_PASSWORD"],
            cookies_file=app.config["IG_COOKIES_FILE"],
            cookies_from_browser=app.config["IG_COOKIES_FROM_BROWSER"],
            browser_name=app.config["IG_BROWSER"],
            browser_profile=app.config["IG_BROWSER_PROFILE"],
            temp_dir=app.config["TEMP_DIR"],
            cache_minutes=app.config["PROFILE_CACHE_MINUTES"],
            fetch_timeout_seconds=app.config["FETCH_TIMEOUT_SECONDS"],
            fetch_delay_min=app.config["FETCH_DELAY_MIN"],
            fetch_delay_max=app.config["FETCH_DELAY_MAX"],
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

        fetch_result = ig.fetch_reels_result(profile.username, limit=app.config["MAX_REELS"])
        if not fetch_result.get("success"):
            reasons = "; ".join(
                f"{err.get('layer')}: {err.get('reason')}" for err in (fetch_result.get("errors") or [])
            )
            job.status = "failed"
            job.phase = "failed"
            job.message = fetch_result.get("message") or "Instagram fetch failed."
            if reasons:
                job.message = f"{job.message} ({reasons})"
            job.finished_at = datetime.utcnow()
            profile.last_error = job.message
            session.commit()
            return
        reels = fetch_result.get("reels") or []
        source = fetch_result.get("source") or "unknown"

        job.total_count = len(reels)
        job.phase = "downloading_media"
        job.message = "Downloading media (Instagram may throttle; this can be slow)..."
        session.commit()

        ensure_dir(app.config["TEMP_DIR"])

        for meta in reels:
            if not isinstance(meta, dict):
                job.failed_count += 1
                job.processed_count += 1
                session.commit()
                continue
            # Skip long reels to cap cost
            duration = meta.get("video_duration")
            if duration and duration > app.config["MAX_REEL_SECONDS"]:
                _record_skip(session, job, profile, meta, "duration too long")
                session.commit()
                continue

            reel = Reel(
                job_id=job.id,
                profile_id=profile.id,
                username=profile.username,
                shortcode=meta.get("shortcode"),
                reel_url=meta.get("reel_url"),
                thumbnail_url=meta.get("thumbnail_url"),
                video_url=meta.get("video_url"),
                posted_at=meta.get("posted_at"),
                like_count=meta.get("like_count"),
                comment_count=meta.get("comment_count"),
                view_count=meta.get("view_count"),
                video_duration=meta.get("video_duration"),
                caption=meta.get("caption"),
                processing_status="pending",
                transcript_status="pending",
            )
            session.add(reel)
            session.commit()
            session.refresh(reel)

            try:
                job.phase = "transcribing"
                job.message = "Extracting audio and transcribing..."
                session.commit()

                with download_reel_media_tmp(
                    reel_url=reel.reel_url,
                    shortcode=reel.shortcode,
                    cookies_file=app.config["IG_COOKIES_FILE"],
                    cookies_from_browser=app.config["IG_COOKIES_FROM_BROWSER"],
                    browser_name=app.config["IG_BROWSER"],
                    browser_profile=app.config["IG_BROWSER_PROFILE"],
                    ffmpeg_location=app.config["FFMPEG_LOCATION"],
                ) as media:
                    audio_tmp_path = media.get("audio_path")
                    thumb_tmp_path = media.get("thumbnail_path")
                    raw_transcript = tx.transcribe(audio_tmp_path or "")
                    audio_upload = upload_audio(audio_tmp_path, reel.shortcode, profile.username)
                    thumb_upload = upload_thumbnail(thumb_tmp_path, reel.shortcode, profile.username)

                reel.audio_url = audio_upload.get("url")
                reel.audio_cloudinary_id = audio_upload.get("public_id")
                if thumb_upload.get("url"):
                    reel.thumbnail_url = thumb_upload.get("url")
                    reel.thumbnail_cloudinary_id = thumb_upload.get("public_id")
                if raw_transcript.strip():
                    reel.transcript = raw_transcript
                    reel.transcript_status = "ok"
                else:
                    reel.transcript = "No spoken content detected."
                    reel.transcript_status = "no_speech"

                job.phase = "summarizing"
                job.message = "Generating summaries..."
                session.commit()

                title, summary = sm.summarize(raw_transcript or "", reel.caption or "")
                reel.ai_title = title
                reel.ai_summary = summary

                reel.processing_status = "completed"
                reel.processed = True
                job.success_count += 1


            except (TranscriptionError, InstagramError, MediaError) as exc:
                session.rollback()
                reel.processing_status = "failed"
                reel.error_reason = str(exc)
                job.failed_count += 1
                _log_reel_error(session, job.id, reel.shortcode, "processing", str(exc))
            except Exception:
                session.rollback()
                reel.processing_status = "failed"
                reel.error_reason = "Unexpected processing error"
                job.failed_count += 1
                _log_reel_error(session, job.id, reel.shortcode, "processing", "Unexpected processing error")
            finally:
                job.processed_count += 1
                try:
                    session.commit()
                except Exception:
                    session.rollback()
                time.sleep(0.4)

        job.finished_at = datetime.utcnow()
        if job.total_count == 0:
            job.status = "completed"
            job.phase = "completed"
            job.message = "No reels found."
            profile.last_success_at = datetime.utcnow()
            profile.last_error = None
            profile.last_job_id = job.id
        elif job.failed_count > 0 and job.success_count > 0:
            job.status = "partial_failed"
            job.phase = "completed"
            job.message = "Completed with some failures."
            profile.last_success_at = datetime.utcnow()
            profile.last_error = job.message
            profile.last_job_id = job.id
        elif job.failed_count > 0 and job.success_count == 0:
            job.status = "failed"
            job.phase = "failed"
            job.message = "All reels failed."
        else:
            job.status = "completed"
            job.phase = "completed"
            job.message = "Completed successfully."
            profile.last_success_at = datetime.utcnow()
            profile.last_error = None
            profile.last_job_id = job.id

        session.commit()
    finally:
        session.close()


def _record_skip(session, job, profile, meta, reason):
    reel = Reel(
        job_id=job.id,
        profile_id=profile.id,
        username=profile.username,
        shortcode=meta.get("shortcode"),
        reel_url=meta.get("reel_url"),
        thumbnail_url=meta.get("thumbnail_url"),
        video_url=meta.get("video_url"),
        posted_at=meta.get("posted_at"),
        like_count=meta.get("like_count"),
        comment_count=meta.get("comment_count"),
        view_count=meta.get("view_count"),
        processing_status="skipped",
        transcript_status="skipped",
        error_reason=reason,
    )
    session.add(reel)
    job.skipped_count += 1
    job.processed_count += 1


def _log_reel_error(session, job_id, shortcode, stage, message):
    session.add(ReelError(job_id=job_id, shortcode=shortcode, stage=stage, error_text=message))


def _cleanup_temp(*paths):
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


