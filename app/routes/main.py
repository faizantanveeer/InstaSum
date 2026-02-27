from __future__ import annotations

import os
import time
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import OperationalError

from ..db import get_session
from ..models import Job, Profile, Reel
from ..services.auth import current_user, login_required
from ..services.instagram import InstagramError, InstagramService
from ..services.media import download_reel_thumbnail
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


@bp.get("/")
def index():
    if current_user():
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.get("/dashboard")
@login_required
def dashboard():
    user = current_user()
    profile_id = request.args.get("profile_id", type=int) or session.get("active_profile_id")
    profile = None
    reels = []

    if profile_id:
        db = get_session()
        try:
            profile = db.get(Profile, profile_id)
            if profile:
                reels = (
                    db.query(Reel)
                    .filter(Reel.user_id == user.id, Reel.profile_id == profile.id)
                    .order_by(Reel.posted_at.is_(None), Reel.posted_at.desc())
                    .all()
                )
            else:
                profile_id = None
        finally:
            db.close()

    return render_template(
        "dashboard.html",
        profile=profile,
        reels=reels,
        active_profile_id=profile_id,
    )


@bp.post("/dashboard/search")
@login_required
def dashboard_search():
    user = current_user()
    profile_input = request.form.get("profile_input", "")
    username = normalize_username(profile_input)
    if not username:
        flash("Please enter a valid Instagram username or profile URL.", "error")
        return redirect(url_for("main.dashboard"))

    ig = InstagramService(
        rapidapi_key=current_app.config["RAPIDAPI_KEY"],
        apify_token=current_app.config["APIFY_TOKEN"],
        cookies_file=current_app.config["IG_COOKIES_FILE"],
        temp_dir=current_app.config["TEMP_DIR"],
        cache_minutes=current_app.config["PROFILE_CACHE_MINUTES"],
    )

    try:
        reels_meta, source, profile_meta = ig.fetch_reels(username, limit=current_app.config["MAX_REELS"])
    except InstagramError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.dashboard"))

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
            flash("Profile is private or inaccessible.", "error")
            session["active_profile_id"] = profile.id
            return redirect(url_for("main.dashboard", profile_id=profile.id))

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

            # If DB has a stale thumbnail filename, force a refresh.
            if reel.thumbnail_path:
                existing_thumb = os.path.join(
                    current_app.config["DOWNLOADS_DIR"],
                    username,
                    reel.thumbnail_path,
                )
                if not os.path.exists(existing_thumb):
                    if "/" not in reel.thumbnail_path and "\\" not in reel.thumbnail_path:
                        alt_rel = f"thumbnails/{reel.thumbnail_path}"
                        alt_thumb = os.path.join(
                            current_app.config["DOWNLOADS_DIR"],
                            username,
                            alt_rel,
                        )
                        if os.path.exists(alt_thumb):
                            reel.thumbnail_path = alt_rel
                        else:
                            reel.thumbnail_path = None
                    else:
                        reel.thumbnail_path = None

            if not reel.thumbnail_path:
                thumb_file = download_reel_thumbnail(
                    reel.reel_url,
                    reel.shortcode,
                    username,
                    current_app.config["DOWNLOADS_DIR"],
                    current_app.config["IG_COOKIES_FILE"],
                )
                if thumb_file:
                    reel.thumbnail_path = thumb_file

        _commit_with_retry(db)
        session["active_profile_id"] = profile.id
    except OperationalError as exc:
        db.rollback()
        if _is_db_locked_error(exc):
            current_app.logger.warning("dashboard_search hit sqlite lock for username=%s", username)
            flash("Database is busy. Please retry in a few seconds.", "error")
            return redirect(url_for("main.dashboard", profile_id=session.get("active_profile_id")))
        raise
    finally:
        db.close()

    flash(f"Loaded reels for @{username} via {source}.", "info")
    return redirect(url_for("main.dashboard", profile_id=session.get("active_profile_id")))


@bp.post("/analyze")
@login_required
def analyze():
    return dashboard_search()


@bp.get("/results/<path:username>")
@login_required
def legacy_results(username: str):
    normalized = normalize_username(username)
    if not normalized:
        return redirect(url_for("main.dashboard"))

    db = get_session()
    try:
        profile = db.query(Profile).filter(Profile.username == normalized).first()
        if profile:
            session["active_profile_id"] = profile.id
            return redirect(url_for("main.dashboard", profile_id=profile.id))
    finally:
        db.close()

    return redirect(url_for("main.dashboard"))
