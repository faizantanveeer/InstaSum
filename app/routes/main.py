from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy.exc import OperationalError

from ..db import get_session
from ..models import Job, Profile, Reel
from ..services.auth import current_user, login_required
from ..services.instagram import InstagramService
from ..services.media import MediaError, download_reel_media_tmp
from ..services.summarization import SummarizationService
from ..services.transcription import TranscriptionError, TranscriptionService
from ..services.utils import normalize_username, safe_int

bp = Blueprint("main", __name__)


def _is_db_locked_error(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


def _commit_with_retry(db, attempts: int = 5):
    last_exc = None
    for attempt in range(attempts):
        try:
            db.commit()
            return
        except OperationalError as exc:
            db.rollback()
            last_exc = exc
            if not _is_db_locked_error(exc) or attempt == attempts - 1:
                raise
            time.sleep(0.25 * (attempt + 1))
    if last_exc:
        raise last_exc


def _wants_json() -> bool:
    if request.is_json:
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept.lower()


def _spa_index_response():
    static_dir = Path(current_app.static_folder or "")
    dist_dir = static_dir / "dist"
    dist_index = dist_dir / "index.html"
    if dist_index.exists():
        return send_from_directory(dist_dir, "index.html")
    # Fallback while SPA isn't built yet.
    return render_template("index.html")


def search_and_upsert_profile(user, profile_input: str) -> tuple[dict, int]:
    username = normalize_username(profile_input or "")
    if not username:
        return {
            "ok": False,
            "message": "Please enter a valid Instagram username or profile URL.",
            "errors": [{"layer": "input", "reason": "invalid_username"}],
        }, 400

    # DB cache short-circuit to avoid unnecessary external fetch attempts.
    cache_minutes = int(current_app.config["PROFILE_CACHE_MINUTES"])
    if cache_minutes > 0:
        db = get_session()
        try:
            existing_profile = db.query(Profile).filter(Profile.username == username).first()
            if (
                existing_profile
                and existing_profile.last_fetched_at
                and (datetime.utcnow() - existing_profile.last_fetched_at).total_seconds() < (cache_minutes * 60)
            ):
                existing_count = (
                    db.query(Reel)
                    .filter(Reel.user_id == user.id, Reel.profile_id == existing_profile.id)
                    .count()
                )
                if existing_count > 0:
                    session["active_profile_id"] = existing_profile.id
                    return {
                        "ok": True,
                        "message": f"Loaded cached reels for @{username}.",
                        "source": "cache",
                        "profile_id": existing_profile.id,
                        "username": existing_profile.username,
                        "reels_count": existing_count,
                    }, 200
        finally:
            db.close()

    ig = InstagramService(
        apify_token=current_app.config["APIFY_TOKEN"],
        ig_username=current_app.config["IG_USERNAME"],
        ig_password=current_app.config["IG_PASSWORD"],
        cookies_file=current_app.config["IG_COOKIES_FILE"],
        cookies_from_browser=current_app.config["IG_COOKIES_FROM_BROWSER"],
        browser_name=current_app.config["IG_BROWSER"],
        browser_profile=current_app.config["IG_BROWSER_PROFILE"],
        temp_dir=current_app.config["TEMP_DIR"],
        cache_minutes=current_app.config["PROFILE_CACHE_MINUTES"],
        fetch_timeout_seconds=current_app.config["FETCH_TIMEOUT_SECONDS"],
        fetch_delay_min=current_app.config["FETCH_DELAY_MIN"],
        fetch_delay_max=current_app.config["FETCH_DELAY_MAX"],
    )

    fetch_result = ig.fetch_reels_result(username, limit=current_app.config["MAX_REELS"])
    if not fetch_result.get("success"):
        reasons = "; ".join(
            f"{err.get('layer')}: {err.get('reason')}" for err in (fetch_result.get("errors") or [])
        )
        if reasons:
            current_app.logger.error("[Fetch:All] username=%s reasons=%s", username, reasons)
        return {
            "ok": False,
            "message": fetch_result.get("message")
            or "Instagram data could not be retrieved. Please try again in a few minutes.",
            "errors": fetch_result.get("errors") or [],
        }, 502

    reels_meta = fetch_result.get("reels") or []
    source = fetch_result.get("source") or "unknown"
    profile_meta = fetch_result.get("profile") or {}

    db = get_session()
    try:
        profile = db.query(Profile).filter(Profile.username == username).first()
        if not profile:
            profile = Profile(username=username)
            db.add(profile)
            _commit_with_retry(db)
            db.refresh(profile)

        if isinstance(profile_meta, dict):
            profile.full_name = profile_meta.get("full_name") or profile.full_name or username
            profile.biography = profile_meta.get("biography") or profile.biography
            profile.profile_pic_url = profile_meta.get("profile_pic_url") or profile.profile_pic_url
            profile.followers = safe_int(profile_meta.get("followers"), profile.followers)
            profile.following = safe_int(profile_meta.get("following"), profile.following)
            profile.post_count = safe_int(profile_meta.get("post_count"), profile.post_count)

        profile.last_fetched_at = datetime.utcnow()

        metadata_job = Job(
            profile_id=profile.id,
            user_id=user.id,
            target_profile_id=profile.id,
            status="completed",
            phase="fetched",
            message="Fetched profile and reels metadata",
            job_type="batch",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
        )
        db.add(metadata_job)
        _commit_with_retry(db)
        db.refresh(metadata_job)

        if profile_meta and profile_meta.get("is_private"):
            profile.is_private_last_seen = True
            _commit_with_retry(db)
            session["active_profile_id"] = profile.id
            return {
                "ok": False,
                "message": "Profile is private or inaccessible.",
                "errors": [{"layer": "instagram", "reason": "private_or_inaccessible"}],
                "profile_id": profile.id,
                "username": username,
            }, 403

        tx = None
        try:
            tx = TranscriptionService(
                current_app.config["WHISPER_MODEL"],
                current_app.config["FFMPEG_LOCATION"],
            )
        except Exception as exc:
            current_app.logger.warning("Title pre-generation transcription disabled: %s", exc)

        sm = SummarizationService(
            current_app.config["OPENAI_API_KEY"],
            current_app.config["OPENAI_SUMMARY_MODEL"],
            {
                "endpoint": current_app.config["AZURE_OPENAI_ENDPOINT"],
                "api_key": current_app.config["AZURE_OPENAI_API_KEY"],
                "api_version": current_app.config["AZURE_OPENAI_API_VERSION"],
                "deployment": current_app.config["AZURE_OPENAI_DEPLOYMENT"],
            },
        )

        for meta in reels_meta:
            if not isinstance(meta, dict):
                continue
            shortcode = meta.get("shortcode") or meta.get("id")
            if not shortcode:
                continue

            reel = (
                db.query(Reel)
                .filter(
                    Reel.user_id == user.id,
                    Reel.profile_id == profile.id,
                    Reel.shortcode == shortcode,
                )
                .first()
            )

            if not reel:
                reel = Reel(
                    job_id=metadata_job.id,
                    profile_id=profile.id,
                    user_id=user.id,
                    username=username,
                    shortcode=shortcode,
                    reel_url=meta.get("reel_url") or f"https://www.instagram.com/reel/{shortcode}/",
                    processing_status="pending",
                    transcript_status="pending",
                    processed=False,
                )
                db.add(reel)

            reel.job_id = metadata_job.id
            reel.username = username
            reel.reel_url = meta.get("reel_url") or reel.reel_url or f"https://www.instagram.com/reel/{shortcode}/"
            reel.thumbnail_url = meta.get("thumbnail_url")
            reel.video_url = meta.get("video_url")
            reel.posted_at = meta.get("posted_at")
            reel.like_count = meta.get("like_count")
            reel.comment_count = meta.get("comment_count")
            reel.view_count = meta.get("view_count")
            reel.video_duration = meta.get("video_duration")
            reel.caption = meta.get("caption")

            needs_title = not (reel.ai_title and reel.ai_title.strip() and reel.ai_title.strip().lower() != "untitled reel")
            if needs_title:
                transcript_for_title = (reel.transcript or "").strip()
                if transcript_for_title.lower() == "transcript pending.":
                    transcript_for_title = ""

                if not transcript_for_title and tx is not None:
                    try:
                        with download_reel_media_tmp(
                            reel_url=reel.reel_url,
                            shortcode=reel.shortcode,
                            cookies_file=current_app.config["IG_COOKIES_FILE"],
                            cookies_from_browser=current_app.config["IG_COOKIES_FROM_BROWSER"],
                            browser_name=current_app.config["IG_BROWSER"],
                            browser_profile=current_app.config["IG_BROWSER_PROFILE"],
                            ffmpeg_location=current_app.config["FFMPEG_LOCATION"],
                        ) as media:
                            transcript_for_title = tx.transcribe(media.get("audio_path") or "")
                    except (MediaError, TranscriptionError) as exc:
                        current_app.logger.warning(
                            "Skipping title pre-generation for %s due to media/transcription issue: %s",
                            reel.shortcode,
                            exc,
                        )
                    except Exception as exc:
                        current_app.logger.warning(
                            "Skipping title pre-generation for %s due to unexpected issue: %s",
                            reel.shortcode,
                            exc,
                        )

                if transcript_for_title:
                    reel.transcript = transcript_for_title
                    reel.transcript_status = "ok"
                elif not reel.transcript:
                    reel.transcript = "No spoken content detected."
                    reel.transcript_status = "no_speech"

                try:
                    reel.ai_title = sm.generate_title(transcript_for_title, reel.caption or "")
                except Exception as exc:
                    current_app.logger.warning(
                        "Failed title generation for %s: %s",
                        reel.shortcode,
                        exc,
                    )

            _commit_with_retry(db)

        session["active_profile_id"] = profile.id

        reels_count = (
            db.query(Reel)
            .filter(Reel.user_id == user.id, Reel.profile_id == profile.id)
            .count()
        )

        return {
            "ok": True,
            "message": f"Loaded reels for @{username} via {source}.",
            "source": source,
            "profile_id": profile.id,
            "username": username,
            "reels_count": reels_count,
        }, 200
    except OperationalError as exc:
        db.rollback()
        if _is_db_locked_error(exc):
            current_app.logger.warning("dashboard_search hit sqlite lock for username=%s", username)
            return {
                "ok": False,
                "message": "Database is busy. Please retry in a few seconds.",
                "errors": [{"layer": "database", "reason": "database_locked"}],
                "profile_id": session.get("active_profile_id"),
            }, 503
        raise
    finally:
        db.close()


@bp.get("/")
def index():
    return _spa_index_response()


@bp.get("/dashboard")
def dashboard():
    return _spa_index_response()


@bp.get("/login")
def login_page():
    return _spa_index_response()


@bp.get("/signup")
def signup_page():
    return _spa_index_response()


@bp.get("/profile/<path:username>")
def profile_page(username: str):
    _ = username
    return _spa_index_response()


@bp.route("/dashboard/search", methods=["POST"])
@login_required
def dashboard_search():
    user = current_user()
    payload = request.get_json(silent=True) if request.is_json else None
    profile_input = (payload or {}).get("profile_input") if payload is not None else request.form.get("profile_input", "")

    data, status = search_and_upsert_profile(user, profile_input or "")
    if _wants_json():
        return jsonify(data), status

    if data.get("ok"):
        flash(data.get("message") or "Loaded.", "info")
        return redirect(url_for("main.dashboard", profile_id=data.get("profile_id")))

    flash(data.get("message") or "Operation failed.", "error")
    if data.get("profile_id"):
        return redirect(url_for("main.dashboard", profile_id=data.get("profile_id")))
    return redirect(url_for("main.dashboard"))


@bp.post("/analyze")
@login_required
def analyze():
    return dashboard_search()


@bp.get("/results/<path:username>")
def legacy_results(username: str):
    normalized = normalize_username(username)
    if not normalized:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.profile_page", username=normalized))


@bp.get("/<path:path>")
def spa_catch_all(path: str):
    blocked_prefixes = (
        "api/",
        "auth/",
        "static/",
        "export/",
        "thumbnails/",
        "audio/",
        "dashboard/search",
    )
    if any(path.startswith(prefix) for prefix in blocked_prefixes):
        abort(404)
    return _spa_index_response()
