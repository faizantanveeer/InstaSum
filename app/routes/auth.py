from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_session
from ..models import User
from ..services.auth import current_user, login_user, logout_user

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.get("/login")
def login():
    if current_user():
        return redirect(url_for("main.dashboard"))
    return render_template("auth_login.html")


@bp.post("/login")
def login_post():
    if current_user():
        return redirect(url_for("main.dashboard"))
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("auth.login"))

    db = get_session()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.", "error")
            return redirect(url_for("auth.login"))
        if not user.is_active:
            flash("Account is disabled.", "error")
            return redirect(url_for("auth.login"))
        user.last_login_at = datetime.utcnow()
        db.commit()
        login_user(user)
    finally:
        db.close()

    return redirect(url_for("main.dashboard"))


@bp.get("/signup")
def signup():
    if current_user():
        return redirect(url_for("main.dashboard"))
    return render_template("auth_signup.html")


@bp.post("/signup")
def signup_post():
    if current_user():
        return redirect(url_for("main.dashboard"))

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("auth.signup"))
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.signup"))
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("auth.signup"))

    db = get_session()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            flash("Email is already registered.", "error")
            return redirect(url_for("auth.signup"))

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
    finally:
        db.close()

    return redirect(url_for("main.dashboard"))


@bp.post("/logout")
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))
