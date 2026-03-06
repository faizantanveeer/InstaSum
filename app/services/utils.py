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


def resolve_valid_cookiefile(path: str) -> tuple[str, str]:
    """
    Return a ytdlp-compatible cookie file path and a warning (if any).

    The only supported format here is Netscape cookie file format.
    If the file is missing, empty, or invalid, this returns ("", warning).
    """
    if not path:
        return "", ""
    if not os.path.exists(path):
        # Missing cookie file is a common optional state; ignore silently.
        return "", ""
    if not os.path.isfile(path):
        return "", f"Cookie path is not a file: {path}"

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().splitlines()
    except Exception:
        return "", f"Cookie file could not be read: {path}"

    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        # Empty file is treated as "not configured".
        return "", ""

    header_ok = non_empty[0].lower().startswith("# netscape http cookie file")
    if not header_ok:
        return "", f"Cookie file is not Netscape format: {path}"

    # Validate at least one cookie row with 7 tab-separated columns.
    has_cookie_row = False
    for line in non_empty[1:]:
        if line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            has_cookie_row = True
            break
    if not has_cookie_row:
        return "", f"Cookie file has no valid cookie rows: {path}"

    return path, ""


def build_ytdlp_auth_strategies(
    cookies_file: str,
    browser_name: str = "",
    browser_profile: str = "",
    enable_browser: bool = True,
):
    """
    Build yt-dlp auth strategies in priority order:
    1) Browser cookies
    2) Netscape cookie file
    3) No cookies
    """
    strategies = []
    warnings = []

    if enable_browser and (browser_name or "").strip():
        profile = (browser_profile or "").strip() or None
        for browser in _expand_browser_names(browser_name):
            # Try explicit profile first (if provided), then auto profile.
            if profile:
                strategies.append(
                    (
                        f"browser:{browser}:{profile}",
                        {"cookiesfrombrowser": (browser, profile, None, None)},
                    )
                )
            strategies.append(
                (
                    f"browser:{browser}",
                    {"cookiesfrombrowser": (browser, None, None, None)},
                )
            )

    cookiefile, cookie_warning = resolve_valid_cookiefile(cookies_file)
    if cookiefile:
        strategies.append(("cookiefile", {"cookiefile": cookiefile}))
    elif cookie_warning:
        warnings.append(cookie_warning)

    strategies.append(("no_cookies", {}))
    return strategies, warnings


def _expand_browser_names(value: str):
    """
    Expand browser config value into yt-dlp browser names.

    Examples:
    - "edge" -> ["edge"]
    - "chrome" -> ["chrome"]
    - "edge,chrome" -> ["edge", "chrome"]
    - "auto" / "both" -> ["edge", "chrome"]
    """
    raw = (value or "").strip().lower()
    if not raw:
        return []

    if raw in {"auto", "both"}:
        return ["edge", "chrome"]

    alias = {
        "microsoft-edge": "edge",
        "msedge": "edge",
        "google-chrome": "chrome",
    }

    candidates = re.split(r"[,|]+", raw)
    out = []
    for item in candidates:
        token = alias.get(item.strip(), item.strip())
        if not token:
            continue
        if token not in out:
            out.append(token)
    return out


