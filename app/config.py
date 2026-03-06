from __future__ import annotations

import os
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", ""
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
    OPENAI_WHISPER_MODEL = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Cloudinary
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

    # Instagram fetchers
    APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
    IG_USERNAME = os.getenv("IG_USERNAME", "")
    IG_PASSWORD = os.getenv("IG_PASSWORD", "")
    IG_COOKIES_FILE = os.getenv("IG_COOKIES_FILE", "./instagram_cookies.txt")
    IG_COOKIES_FROM_BROWSER = os.getenv("IG_COOKIES_FROM_BROWSER", "1") == "1"
    IG_BROWSER = os.getenv("IG_BROWSER", "chrome")
    IG_BROWSER_PROFILE = os.getenv("IG_BROWSER_PROFILE", "")
    FETCH_TIMEOUT_SECONDS = int(os.getenv("FETCH_TIMEOUT_SECONDS", "180"))
    FETCH_DELAY_MIN = float(os.getenv("FETCH_DELAY_MIN", "1.0"))
    FETCH_DELAY_MAX = float(os.getenv("FETCH_DELAY_MAX", "3.0"))
    PROFILE_CACHE_MINUTES = int(os.getenv("PROFILE_CACHE_MINUTES", "60"))

    # Whisper / media tools
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    FFMPEG_LOCATION = os.getenv("FFMPEG_LOCATION", "")

    # Limits
    MAX_REELS = int(os.getenv("MAX_REELS", "100"))
    MAX_REEL_SECONDS = int(os.getenv("MAX_REEL_SECONDS", "180"))
    CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

    # Polling
    PAGE_SIZE = int(os.getenv("PAGE_SIZE", "12"))

    # Rate limiting
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per day")
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "0") == "1"

    # CAPTCHA (hCaptcha)
    HCAPTCHA_SITEKEY = os.getenv("HCAPTCHA_SITEKEY", "")
    HCAPTCHA_SECRET = os.getenv("HCAPTCHA_SECRET", "")
    CAPTCHA_ENABLED = os.getenv("CAPTCHA_ENABLED", "1") == "1"

    # Temp storage
    TEMP_DIR = os.getenv("TEMP_DIR", "./tmp")

    # Retry/backoff
    FETCH_RETRY_MAX = int(os.getenv("FETCH_RETRY_MAX", "3"))
    FETCH_RETRY_BASE = float(os.getenv("FETCH_RETRY_BASE", "1.5"))

    # Job worker
    WORKER_POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "2"))
    STALE_JOB_MINUTES = int(os.getenv("STALE_JOB_MINUTES", "30"))

    # HTMX polling
    STATUS_POLL_SECONDS = int(os.getenv("STATUS_POLL_SECONDS", "2"))
    LIST_POLL_SECONDS = int(os.getenv("LIST_POLL_SECONDS", "5"))

    # Export
    EXPORT_MAX_ROWS = int(os.getenv("EXPORT_MAX_ROWS", "5000"))

    # Optional: disable local whisper for faster dev
    DISABLE_LOCAL_WHISPER = os.getenv("DISABLE_LOCAL_WHISPER", "0") == "1"


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False
