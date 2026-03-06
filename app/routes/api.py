from __future__ import annotations

import csv
import io
import json
import queue
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Blueprint, Response, abort, current_app, render_template, request, stream_with_context
from sqlalchemy import case, func
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_session
from ..models import Job, Profile, Reel, User
from ..services.auth import current_user, login_required, login_user, logout_user
from ..services.media import MediaError, download_reel_media_tmp
from ..services.utils import normalize_username
from ..services.storage import upload_audio, upload_thumbnail
from ..services.summarization import SummarizationService
from ..services.transcription import TranscriptionError, TranscriptionService
from .main import search_and_upsert_profile

bp = Blueprint("api", __name__)

_JOB_STREAMS: dict[int, dict] = {}


@bp.errorhandler(401)
def _api_unauthorized(_err):
    return {"message": "Unauthorized"}, 401


@bp.errorhandler(404)
def _api_not_found(_err):
    return {"message": "Not found"}, 404


def _init_stream_state(job_id: int):
    state = _JOB_STREAMS.get(job_id)
    if state is None:
        state = {"queue": queue.Queue(), "thread": None, "lock": threading.Lock()}
        _JOB_STREAMS[job_id] = state
    return state


def _emit_event(job_id: int, event: dict):
    state = _init_stream_state(job_id)
    state["queue"].put(event)


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


def _config_page_size() -> int:
    return max(1, int(current_app.config.get("PAGE_SIZE", 12) or 12))


def _format_dt(value):
    if not value:
        return None
    try:
        return value.isoformat()
    except Exception:
        return None


def _abbr(value):
    if value is None:
        return "-"
    try:
        num = float(value)
    except Exception:
        return str(value)
    abs_num = abs(num)
    if abs_num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B".rstrip("0").rstrip(".")
    if abs_num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M".rstrip("0").rstrip(".")
    if abs_num >= 1_000:
        return f"{num / 1_000:.1f}K".rstrip("0").rstrip(".")
    return str(int(num))


def _reel_payload(reel: Reel):
    return {
        "id": reel.id,
        "profile_id": reel.profile_id,
        "username": reel.username,
        "shortcode": reel.shortcode,
        "reel_url": reel.reel_url,
        "video_url": reel.video_url,
        "thumbnail_url": reel.thumbnail_url,
        "audio_url": reel.audio_url,
        "caption": reel.caption or "",
        "posted_at": _format_dt(reel.posted_at),
        "like_count": reel.like_count,
        "comment_count": reel.comment_count,
        "view_count": reel.view_count,
        "video_duration": reel.video_duration,
        "transcript": reel.transcript or "",
        "transcript_status": reel.transcript_status or "pending",
        "ai_title": reel.ai_title or "",
        "ai_summary": reel.ai_summary or "",
        "summary_detail": reel.summary_detail or "",
        "processed": bool(reel.processed),
        "processing_status": reel.processing_status or "pending",
        "error_reason": reel.error_reason or "",
        "created_at": _format_dt(reel.created_at),
        "has_audio": bool(reel.audio_url),
    }


@bp.get("/api/config")
@login_required
def api_config():
    return {
        "page_size": _config_page_size(),
        "max_reels": int(current_app.config.get("MAX_REELS", 100) or 100),
        "status_poll_seconds": int(current_app.config.get("STATUS_POLL_SECONDS", 3) or 3),
        "list_poll_seconds": int(current_app.config.get("LIST_POLL_SECONDS", 5) or 5),
    }


@bp.get("/api/auth/me")
def api_auth_me():
    user = current_user()
    if not user:
        return {"message": "Unauthorized"}, 401
    return {
        "id": user.id,
        "email": user.email,
        "created_at": _format_dt(user.created_at),
        "last_login_at": _format_dt(user.last_login_at),
    }


@bp.post("/api/auth/login")
def api_auth_login():
    if current_user():
        user = current_user()
        return {"message": "Already logged in.", "user": {"id": user.id, "email": user.email}}, 200

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return {"message": "Email and password are required."}, 400

    db = get_session()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return {"message": "Invalid credentials."}, 401
        if not user.is_active:
            return {"message": "Account is disabled."}, 403
        user.last_login_at = datetime.utcnow()
        db.commit()
        login_user(user)
        return {"message": "Logged in.", "user": {"id": user.id, "email": user.email}}, 200
    finally:
        db.close()


@bp.post("/api/auth/signup")
def api_auth_signup():
    if current_user():
        user = current_user()
        return {"message": "Already logged in.", "user": {"id": user.id, "email": user.email}}, 200

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or payload.get("confirmPassword") or ""

    if not email or not password:
        return {"message": "Email and password are required."}, 400
    if password != confirm_password:
        return {"message": "Passwords do not match."}, 400
    if len(password) < 8:
        return {"message": "Password must be at least 8 characters."}, 400

    db = get_session()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {"message": "Email is already registered."}, 409

        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            created_at=datetime.utcnow(),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        login_user(user)
        return {"message": "Account created.", "user": {"id": user.id, "email": user.email}}, 201
    finally:
        db.close()


@bp.post("/api/auth/logout")
def api_auth_logout():
    if not current_user():
        return {"message": "Unauthorized"}, 401
    logout_user()
    return {"message": "Signed out."}, 200


@bp.get("/api/profiles")
@login_required
def api_profiles():
    user = current_user()
    db = get_session()
    try:
        rows = (
            db.query(
                Profile.id,
                Profile.username,
                Profile.full_name,
                Profile.profile_pic_url,
                Profile.last_fetched_at,
                func.count(Reel.id).label("reels_count"),
                func.coalesce(func.sum(case((Reel.processed.is_(True), 1), else_=0)), 0).label("processed_count"),
            )
            .join(Reel, Reel.profile_id == Profile.id)
            .filter(Reel.user_id == user.id)
            .group_by(Profile.id)
            .order_by(Profile.last_fetched_at.desc().nullslast(), Profile.id.desc())
            .limit(10)
            .all()
        )

        items = []
        for row in rows:
            items.append(
                {
                    "id": row.id,
                    "username": row.username,
                    "full_name": row.full_name or row.username,
                    "avatar_url": row.profile_pic_url or "",
                    "last_fetched_at": _format_dt(row.last_fetched_at),
                    "reels_count": int(row.reels_count or 0),
                    "processed_count": int(row.processed_count or 0),
                }
            )
        return {"profiles": items}
    finally:
        db.close()


@bp.post("/api/profiles/search")
@login_required
def api_profiles_search():
    user = current_user()
    payload = request.get_json(silent=True) or {}
    profile_input = payload.get("profile_input") or payload.get("query") or payload.get("username") or ""

    data, status = search_and_upsert_profile(user, profile_input)
    return data, status


@bp.get("/api/profiles/<string:username>")
@login_required
def api_profile_details(username: str):
    user = current_user()
    normalized = normalize_username(username)
    if not normalized:
        return {"message": "Invalid username."}, 400

    page = max(1, int(request.args.get("page", 1) or 1))
    page_size = int(request.args.get("page_size", _config_page_size()) or _config_page_size())
    page_size = max(1, min(page_size, 100))

    db = get_session()
    try:
        profile = db.query(Profile).filter(Profile.username == normalized).first()
        if not profile:
            return {"message": "Profile not found."}, 404

        base_query = (
            db.query(Reel)
            .filter(Reel.user_id == user.id, Reel.profile_id == profile.id)
            .order_by(Reel.posted_at.is_(None), Reel.posted_at.desc(), Reel.id.desc())
        )
        total = base_query.count()
        reels = base_query.offset((page - 1) * page_size).limit(page_size).all()

        processed_count = (
            db.query(func.count(Reel.id))
            .filter(Reel.user_id == user.id, Reel.profile_id == profile.id, Reel.processed.is_(True))
            .scalar()
            or 0
        )

        return {
            "profile": {
                "id": profile.id,
                "username": profile.username,
                "full_name": profile.full_name or profile.username,
                "biography": profile.biography or "",
                "profile_pic_url": profile.profile_pic_url or "",
                "followers": profile.followers,
                "followers_abbr": _abbr(profile.followers),
                "following": profile.following,
                "following_abbr": _abbr(profile.following),
                "post_count": profile.post_count,
                "post_count_abbr": _abbr(profile.post_count),
                "is_private_last_seen": bool(profile.is_private_last_seen),
                "last_fetched_at": _format_dt(profile.last_fetched_at),
                "reels_count": int(total),
                "processed_count": int(processed_count),
            },
            "reels": [_reel_payload(r) for r in reels],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": int(total),
                "total_pages": max(1, (int(total) + page_size - 1) // page_size),
            },
        }
    finally:
        db.close()


@bp.get("/api/reels/<int:reel_id>/status")
@login_required
def api_reel_status(reel_id: int):
    user = current_user()
    db = get_session()
    try:
        reel = db.query(Reel).filter(Reel.id == reel_id, Reel.user_id == user.id).first()
        if not reel:
            return {"message": "Reel not found."}, 404
        return {
            "reel": {
                "id": reel.id,
                "processing_status": reel.processing_status or "pending",
                "processed": bool(reel.processed),
                "ai_title": reel.ai_title or "",
                "ai_summary": reel.ai_summary or "",
                "summary_detail": reel.summary_detail or "",
                "transcript": reel.transcript or "",
                "error_reason": reel.error_reason or "",
                "audio_url": reel.audio_url or "",
                "thumbnail_url": reel.thumbnail_url or "",
            }
        }
    finally:
        db.close()


@bp.get("/api/jobs/<int:job_id>/status")
@login_required
def api_job_status(job_id: int):
    user = current_user()
    db = get_session()
    try:
        job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            return {"message": "Job not found."}, 404

        reels = (
            db.query(Reel.id, Reel.processing_status, Reel.processed)
            .filter(Reel.user_id == user.id, Reel.job_id == job.id)
            .all()
        )
        reel_statuses = [
            {
                "id": row.id,
                "processing_status": row.processing_status or "pending",
                "processed": bool(row.processed),
            }
            for row in reels
        ]

        return {
            "job": {
                "id": job.id,
                "status": job.status or "queued",
                "phase": job.phase or "queued",
                "message": job.message or "",
                "total_count": int(job.total_count or 0),
                "processed_count": int(job.processed_count or 0),
                "success_count": int(job.success_count or 0),
                "failed_count": int(job.failed_count or 0),
                "skipped_count": int(job.skipped_count or 0),
                "requested_at": _format_dt(job.requested_at),
                "started_at": _format_dt(job.started_at),
                "finished_at": _format_dt(job.finished_at),
            },
            "reels": reel_statuses,
        }
    finally:
        db.close()


@bp.get("/proxy-image")
@login_required
def proxy_image():
    image_url = (request.args.get("url") or "").strip()
    if not image_url:
        abort(400)

    parsed = urlparse(image_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        abort(400)

    host = parsed.netloc.lower()
    allowed_suffixes = (
        "cdninstagram.com",
        "fbcdn.net",
        "instagram.com",
        "cloudinary.com",
    )
    if not any(host.endswith(sfx) for sfx in allowed_suffixes):
        abort(400)

    try:
        upstream = requests.get(
            image_url,
            timeout=20,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
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
            return {"message": "Reel not found."}, 404

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
    return {"job_id": job.id, "status": "queued", "total_targeted": 1, "reel_ids": [reel_id]}


@bp.post("/api/profiles/<int:profile_id>/generate-all")
@login_required
def generate_profile_all(profile_id: int):
    user = current_user()
    regenerate = _parse_regenerate()

    db = get_session()
    try:
        profile = db.get(Profile, profile_id)
        if not profile:
            return {"message": "Profile not found."}, 404

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
            return {"job_id": job.id, "status": "completed", "total_targeted": 0, "reel_ids": []}
    finally:
        db.close()

    state = _init_stream_state(job.id)
    _start_job_thread(current_app._get_current_object(), job.id, user.id, reel_ids, regenerate, state)
    return {"job_id": job.id, "status": "queued", "total_targeted": len(reel_ids), "reel_ids": reel_ids}


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
                "audio_url",
                "thumbnail_url",
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
                    r.audio_url or "",
                    r.thumbnail_url or "",
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


def _start_job_thread(app, job_id: int, user_id: str, reel_ids: list[int], regenerate: bool, state: dict):
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


def _process_job(app, job_id: int, user_id: str, reel_ids: list[int], regenerate: bool):
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

                                if not audio_tmp_path:
                                    raise MediaError("Audio file is missing after download")
                                if not audio_tmp_path or not isinstance(audio_tmp_path, str):
                                    raise MediaError("Invalid audio path")

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

                                raw_transcript = tx.transcribe(audio_tmp_path)
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

                                audio_upload = upload_audio(audio_tmp_path, reel.shortcode, username)
                                thumb_upload = upload_thumbnail(thumb_tmp_path, reel.shortcode, username)

                            if not audio_upload.get("url"):
                                raise MediaError("Failed to upload reel audio to Cloudinary")

                            reel.audio_url = audio_upload.get("url")
                            reel.audio_cloudinary_id = audio_upload.get("public_id")
                            if thumb_upload.get("url"):
                                reel.thumbnail_url = thumb_upload.get("url")
                                reel.thumbnail_cloudinary_id = thumb_upload.get("public_id")

                            reel.processing_status = "completed"
                            reel.processed = True
                            reel.error_reason = None
                            _safe_commit(db)

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
        "audio_url": r.audio_url,
        "thumbnail_url": r.thumbnail_url,
        "date": r.posted_at.isoformat() if r.posted_at else None,
        "views": r.view_count,
        "likes": r.like_count,
        "comments": r.comment_count,
    }
