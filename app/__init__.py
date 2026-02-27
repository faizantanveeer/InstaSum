from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from flask import Flask

# Load .env before config import so env vars are available at class init time
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from .config import DevConfig, ProdConfig
from .db import init_engine, init_db
from .services.utils import ensure_dir
from .routes.main import bp as main_bp
from .routes.api import bp as api_bp
from .routes.auth import bp as auth_bp
from .extensions import limiter
from .services.auth import current_user


def create_app():
    app = Flask(__name__)
    env = os.getenv("FLASK_ENV", "development")
    if env == "production":
        app.config.from_object(ProdConfig)
    else:
        app.config.from_object(DevConfig)

    # Database
    init_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    from . import models  # noqa: F401
    init_db()

    # Temp dir
    ensure_dir(app.config["TEMP_DIR"])
    ensure_dir(app.config["DOWNLOADS_DIR"])

    # Rate limiting (disabled by default for dev)
    if app.config["RATELIMIT_ENABLED"]:
        limiter.default_limits = [app.config["RATELIMIT_DEFAULT"]]
        limiter.enabled = True
        limiter.init_app(app)

    # Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_auth():
        return {"current_user": current_user()}

    return app


