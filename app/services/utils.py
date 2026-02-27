from __future__ import annotations

import os
import re
import time
from urllib.parse import urlparse


def normalize_username(input_value: str) -> str:
    value = (input_value or "").strip()
    if not value:
        return ""

    # Strip leading @
    if value.startswith("@"):  # handle @username
        value = value[1:]

    # Remove query/fragment
    value = value.split("?")[0].split("#")[0].strip()

    # If it's a URL (with or without scheme), extract path segment
    if "instagram.com" in value:
        if not (value.startswith("http://") or value.startswith("https://")):
            value = "https://" + value
        try:
            parsed = urlparse(value)
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                value = parts[0]
        except Exception:
            pass
    elif value.startswith("http://") or value.startswith("https://"):
        try:
            parsed = urlparse(value)
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                value = parts[0]
        except Exception:
            pass

    # Instagram URLs sometimes include trailing slashes
    value = value.strip("/")
    if value.startswith("@"):
        value = value[1:]
    return value


def sanitize_fts_query(query: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z ]+", " ", query or "").strip()
    if not cleaned:
        return ""
    # Prefix match for each term
    terms = [t for t in cleaned.split() if t]
    return " AND ".join([f"{t}*" for t in terms])


def safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def retry_with_backoff(fn, max_retries: int, base: float = 1.5):
    last_err = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_err = exc
            sleep_for = base ** attempt
            time.sleep(sleep_for)
    if last_err:
        raise last_err


