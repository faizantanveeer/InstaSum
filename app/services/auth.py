from __future__ import annotations

from functools import wraps

from flask import abort, g, has_app_context, has_request_context, redirect, request, session, url_for

from ..db import get_session
from ..models import User


def current_user():
    if not has_app_context():
        return None
    if hasattr(g, "current_user"):
        return g.current_user
    if not has_request_context():
        g.current_user = None
        return None
    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None
    db = get_session()
    try:
        user = db.get(User, user_id)
        g.current_user = user if user and user.is_active else None
        return g.current_user
    finally:
        db.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/"):
                return abort(401)
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)

    return wrapper


def login_user(user: User):
    session["user_id"] = user.id


def logout_user():
    session.pop("user_id", None)
