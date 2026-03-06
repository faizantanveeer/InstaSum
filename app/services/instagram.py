from __future__ import annotations

import json
import logging
import os
import random
import re
import threading
import time
from datetime import datetime

try:
    import instaloader
    from instaloader import Profile
    from instaloader import exceptions as instaloader_exceptions
except Exception:
    instaloader = None
    Profile = None
    instaloader_exceptions = None


class InstagramError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


logger = logging.getLogger(__name__)
_FETCH_LOCK = threading.Lock()
_INSTALOADER_LOCK = threading.Lock()
_INSTALOADER_CLIENTS: dict[str, object] = {}


class _YtdlpLogger:
    def debug(self, _msg):
        return

    def warning(self, _msg):
        return

    def error(self, _msg):
        return


class InstagramService:
    def __init__(
        self,
        apify_token: str = "",
        cookies_file: str = "",
        cookies_from_browser: bool = True,
        browser_name: str = "chrome",
        browser_profile: str = "",
        ig_username: str = "",
        ig_password: str = "",
        temp_dir: str = "./tmp",
        cache_minutes: int = 60,
        fetch_timeout_seconds: int = 180,
        fetch_delay_min: float = 1.0,
        fetch_delay_max: float = 3.0,
    ):
        self.apify_token = apify_token
        self.cookies_file = cookies_file
        self.cookies_from_browser = cookies_from_browser
        self.browser_name = browser_name
        self.browser_profile = browser_profile
        self.ig_username = (ig_username or os.getenv("IG_USERNAME", "")).strip()
        self.ig_password = (ig_password or os.getenv("IG_PASSWORD", "")).strip()
        self.temp_dir = temp_dir
        self.cache_minutes = cache_minutes
        self.fetch_timeout_seconds = max(30, int(fetch_timeout_seconds or 180))

        self.fetch_delay_min = float(fetch_delay_min or 1.0)
        self.fetch_delay_max = float(fetch_delay_max or 3.0)
        if self.fetch_delay_max < self.fetch_delay_min:
            self.fetch_delay_min, self.fetch_delay_max = self.fetch_delay_max, self.fetch_delay_min

        # Instaloader politeness delay must never go below 2 seconds.
        self.instaloader_delay_min = 3.0
        self.instaloader_delay_max = 6.0

        os.makedirs(self.temp_dir, exist_ok=True)

    def fetch_profile(self, username: str, preview_limit: int = 9, force_refresh: bool = False):
        if not force_refresh:
            cached = self._read_cache(username)
            if cached:
                return cached["profile"], cached["reels"]

        result = self.fetch_reels_result(username, limit=preview_limit)
        if result.get("success"):
            return result.get("profile") or self._default_profile(username), result.get("reels") or []

        return self._default_profile(username), []

    def fetch_reels(self, username: str, limit: int = 100):
        """
        Backward-compatible tuple interface.
        """
        result = self.fetch_reels_result(username, limit)
        return (
            result.get("reels") or [],
            result.get("source") or "failed",
            result.get("profile") or self._default_profile(username),
        )

    def fetch_reels_result(self, username: str, limit: int = 100) -> dict:
        limit = max(1, int(limit or 100))

        # Fast path: fresh cache first.
        cached = self._read_cache(username)
        if cached and cached.get("reels"):
            logger.info("[Fetch:cache] hit username=%s reels=%s", username, len(cached.get("reels", [])))
            return {
                "success": True,
                "source": "cache",
                "profile": cached.get("profile") or self._default_profile(username),
                "reels": cached.get("reels") or [],
                "message": "Loaded from cache",
                "errors": [],
            }

        errors: list[dict] = []

        # Serialize Instagram fetch operations globally.
        with _FETCH_LOCK:
            # Check cache again after waiting for lock.
            cached = self._read_cache(username)
            if cached and cached.get("reels"):
                logger.info("[Fetch:cache] hit-after-lock username=%s reels=%s", username, len(cached.get("reels", [])))
                return {
                    "success": True,
                    "source": "cache",
                    "profile": cached.get("profile") or self._default_profile(username),
                    "reels": cached.get("reels") or [],
                    "message": "Loaded from cache",
                    "errors": [],
                }

            # Layer 1: Apify (primary)
            try:
                reels, profile = self._fetch_reels_apify(username, limit)
                self._write_cache(username, profile or self._default_profile(username), reels or [])
                logger.info("[Fetch:Apify] success username=%s reels=%s", username, len(reels))
                return {
                    "success": True,
                    "source": "apify",
                    "profile": profile or self._default_profile(username),
                    "reels": reels,
                    "message": "Fetched via Apify",
                    "errors": [],
                }
            except Exception as exc:
                reason = _safe_error_text(exc)
                errors.append({"layer": "apify", "reason": reason})
                logger.warning("[Fetch:Apify] failed username=%s reason=%s", username, reason)

            # Layer 2: Instaloader with authenticated session.
            try:
                reels, profile = self._fetch_reels_instaloader(username, limit)
                self._write_cache(username, profile or self._default_profile(username), reels or [])
                logger.info("[Fetch:instaloader] success username=%s reels=%s", username, len(reels))
                return {
                    "success": True,
                    "source": "instaloader",
                    "profile": profile or self._default_profile(username),
                    "reels": reels,
                    "message": "Fetched via Instaloader",
                    "errors": errors,
                }
            except Exception as exc:
                reason = _safe_error_text(exc)
                errors.append({"layer": "instaloader", "reason": reason})
                logger.warning(
                    "[Fetch:instaloader] failed username=%s apify_reason=%s reason=%s",
                    username,
                    errors[0]["reason"] if errors else "",
                    reason,
                )
                if _is_terminal_instaloader_error(reason):
                    logger.warning("[Fetch:instaloader] terminal username=%s reason=%s", username, reason)
                    return {
                        "success": False,
                        "source": None,
                        "profile": self._default_profile(username),
                        "reels": [],
                        "message": reason,
                        "errors": errors,
                    }

            # Layer 3: yt-dlp with browser cookie extraction (dev fallback)
            try:
                reels, profile = self._fetch_reels_ytdlp_with_browser(username, limit)
                self._write_cache(username, profile or self._default_profile(username), reels or [])
                logger.info("[Fetch:ytdlp-browser] success username=%s reels=%s", username, len(reels))
                return {
                    "success": True,
                    "source": "ytdlp-browser",
                    "profile": profile or self._default_profile(username),
                    "reels": reels,
                    "message": "Fetched via yt-dlp (browser cookies)",
                    "errors": errors,
                }
            except Exception as exc:
                reason = _safe_error_text(exc)
                errors.append({"layer": "ytdlp-browser", "reason": reason})
                logger.warning(
                    "[Fetch:ytdlp-browser] failed username=%s previous=%s reason=%s",
                    username,
                    "; ".join(f"{e['layer']}: {e['reason']}" for e in errors[:-1]),
                    reason,
                )

        # Structured failure response (no exception).
        grouped = "; ".join(f"{e['layer']}: {e['reason']}" for e in errors)
        logger.error("[Fetch:All] failed username=%s reasons=%s", username, grouped)
        return {
            "success": False,
            "source": None,
            "profile": self._default_profile(username),
            "reels": [],
            "message": "Instagram data could not be retrieved right now. Please try again in a few minutes.",
            "errors": errors,
        }

    def _fetch_reels_apify(self, username: str, limit: int):
        if not self.apify_token:
            raise InstagramError("APIFY_TOKEN is not configured")

        try:
            from apify_client import ApifyClient
            from apify_client.errors import ApifyApiError
        except Exception as exc:
            raise InstagramError("apify-client is not installed") from exc

        client = ApifyClient(self.apify_token)
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username}/reels/"],
            "resultsType": "posts",
            "resultsLimit": int(limit),
            "addParentData": False,
        }

        try:
            run = client.actor("apify/instagram-scraper").call(
                run_input=run_input,
                timeout_secs=self.fetch_timeout_seconds,
                wait_secs=self.fetch_timeout_seconds + 10,
            )
        except ApifyApiError as exc:
            msg = _safe_error_text(exc)
            if "monthly usage hard limit exceeded" in msg.lower():
                raise InstagramError("Apify monthly usage limit exceeded") from exc
            raise InstagramError(f"Apify API error: {msg}") from exc
        except TimeoutError as exc:
            raise InstagramError(
                f"Apify timed out after {self.fetch_timeout_seconds}s"
            ) from exc
        except Exception as exc:
            raise InstagramError(f"Apify request failed: {_safe_error_text(exc)}") from exc

        dataset_id = (run or {}).get("defaultDatasetId")
        if not dataset_id:
            raise InstagramError("Apify returned no dataset id")

        try:
            items = list(client.dataset(dataset_id).iterate_items())
        except Exception as exc:
            raise InstagramError(f"Apify dataset read failed: {_safe_error_text(exc)}") from exc

        if not items:
            raise InstagramError("Apify returned empty dataset")

        reels = []
        profile = self._default_profile(username)

        for item in items:
            if len(reels) >= limit:
                break
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type") or "").lower()
            video_url = item.get("videoUrl") or item.get("video_url") or ""
            if (item_type and "video" not in item_type) or (not item_type and not video_url):
                continue

            shortcode = (
                item.get("shortCode")
                or item.get("shortcode")
                or item.get("code")
                or item.get("id")
                or ""
            )
            if not shortcode:
                continue

            if item.get("ownerUsername"):
                profile["username"] = item.get("ownerUsername")
            if item.get("ownerFullName"):
                profile["full_name"] = item.get("ownerFullName")

            reels.append(
                {
                    "shortcode": shortcode,
                    "reel_url": item.get("url") or f"https://www.instagram.com/reel/{shortcode}/",
                    "video_url": video_url,
                    "thumbnail_url": item.get("displayUrl") or item.get("thumbnailUrl") or item.get("thumbnail_url"),
                    "caption": item.get("caption") or "",
                    "posted_at": self._parse_apify_ts(item.get("timestamp") or item.get("takenAt")),
                    "like_count": item.get("likesCount") or item.get("likeCount") or item.get("likes"),
                    "view_count": item.get("videoViewCount") or item.get("playCount") or item.get("viewCount"),
                    "comment_count": item.get("commentsCount") or item.get("commentCount") or item.get("comments"),
                    "video_duration": item.get("videoDuration") or item.get("duration"),
                }
            )

        if not reels:
            raise InstagramError("Apify returned no video reels")

        return reels, profile

    def _fetch_reels_instaloader(self, username: str, limit: int):
        if instaloader is None or Profile is None:
            raise InstagramError("instaloader is not installed")

        if not self.ig_username or not self.ig_password:
            raise InstagramError("IG_USERNAME / IG_PASSWORD are not configured for Instaloader")

        loader = self._get_or_create_instaloader_client()

        try:
            profile_obj = Profile.from_username(loader.context, username)
        except Exception as exc:
            if _instaloader_exc_matches(exc, "ProfileNotExistsException", "QueryReturnedNotFoundException"):
                raise InstagramError(f"Instagram username @{username} was not found") from exc
            if _instaloader_exc_matches(exc, "PrivateProfileNotFollowedException", "QueryReturnedForbiddenException"):
                raise InstagramError(f"Instagram profile @{username} is private and cannot be accessed") from exc
            if _instaloader_exc_matches(exc, "TooManyRequestsException", "QueryReturnedBadRequestException"):
                raise InstagramError("Instagram query rate limit reached for Instaloader") from exc
            if _instaloader_exc_matches(exc, "BadCredentialsException"):
                self._invalidate_instaloader_client()
                raise InstagramError("Instaloader login failed due to invalid IG_USERNAME / IG_PASSWORD") from exc
            if _instaloader_exc_matches(
                exc,
                "TwoFactorAuthRequiredException",
                "CheckpointRequiredException",
                "LoginRequiredException",
            ):
                self._invalidate_instaloader_client()
                raise InstagramError("Instaloader session requires manual re-authentication (checkpoint/2FA)") from exc
            raise InstagramError(f"Instaloader profile fetch failed: {_safe_error_text(exc)}") from exc

        profile_meta = self._profile_meta_from_instaloader(profile_obj, username)
        if profile_meta.get("is_private"):
            raise InstagramError(f"Instagram profile @{username} is private and cannot be accessed")

        reels = []
        non_video_streak = 0
        max_non_video_streak = max(limit * 4, 80)

        try:
            posts = profile_obj.get_posts()
        except Exception as exc:
            if _instaloader_exc_matches(exc, "TooManyRequestsException", "QueryReturnedBadRequestException"):
                raise InstagramError("Instagram query rate limit reached for Instaloader") from exc
            raise InstagramError(f"Instaloader post iteration failed: {_safe_error_text(exc)}") from exc

        for post in posts:
            if len(reels) >= limit:
                break

            is_video = _safe_call(lambda: bool(post.is_video), False)
            if not is_video:
                non_video_streak += 1
                if non_video_streak >= max_non_video_streak:
                    break
                continue

            non_video_streak = 0
            reel = self._normalize_instaloader_post(post)
            if not reel:
                continue

            reels.append(reel)
            time.sleep(random.uniform(self.instaloader_delay_min, self.instaloader_delay_max))

        if not reels:
            raise InstagramError("Instaloader returned no video reels")

        return reels, profile_meta

    def _get_or_create_instaloader_client(self):
        if instaloader is None:
            raise InstagramError("instaloader is not installed")

        with _INSTALOADER_LOCK:
            existing = _INSTALOADER_CLIENTS.get(self.ig_username)
            if existing is not None:
                return existing

            loader = instaloader.Instaloader(
                download_videos=False,
                download_video_thumbnails=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                post_metadata_txt_pattern="",
                quiet=True,
                max_connection_attempts=3,
                request_timeout=30,
            )

            session_file = os.path.abspath(f"{self.ig_username}.session")
            loaded_session = False

            try:
                loader.load_session_from_file(self.ig_username, filename=session_file)
                loaded_session = True
                logger.info("[Fetch:instaloader] loaded session file=%s", session_file)
            except FileNotFoundError:
                loaded_session = False
            except Exception as exc:
                logger.warning(
                    "[Fetch:instaloader] session load failed username=%s reason=%s",
                    self.ig_username,
                    _safe_error_text(exc),
                )

            if not loaded_session:
                try:
                    loader.login(self.ig_username, self.ig_password)
                    loader.save_session_to_file(filename=session_file)
                    logger.info("[Fetch:instaloader] created new session file=%s", session_file)
                except Exception as exc:
                    if _instaloader_exc_matches(exc, "BadCredentialsException"):
                        raise InstagramError("Instaloader login failed due to invalid IG_USERNAME / IG_PASSWORD") from exc
                    if _instaloader_exc_matches(
                        exc,
                        "TwoFactorAuthRequiredException",
                        "CheckpointRequiredException",
                        "LoginRequiredException",
                    ):
                        raise InstagramError("Instaloader login requires manual re-authentication (checkpoint/2FA)") from exc
                    raise InstagramError(f"Instaloader login failed: {_safe_error_text(exc)}") from exc

            _INSTALOADER_CLIENTS[self.ig_username] = loader
            return loader

    def _invalidate_instaloader_client(self):
        with _INSTALOADER_LOCK:
            _INSTALOADER_CLIENTS.pop(self.ig_username, None)

    def _profile_meta_from_instaloader(self, profile_obj, fallback_username: str):
        username = _safe_call(lambda: profile_obj.username, fallback_username) or fallback_username
        return {
            "username": username,
            "full_name": _safe_call(lambda: profile_obj.full_name, username) or username,
            "biography": _safe_call(lambda: profile_obj.biography, "") or "",
            "profile_pic_url": _safe_call(lambda: profile_obj.profile_pic_url, "") or "",
            "followers": _to_int(_safe_call(lambda: profile_obj.followers, 0)) or 0,
            "following": _to_int(_safe_call(lambda: profile_obj.followees, 0)) or 0,
            "post_count": _to_int(_safe_call(lambda: profile_obj.mediacount, 0)) or 0,
            "is_private": bool(_safe_call(lambda: profile_obj.is_private, False)),
        }

    def _normalize_instaloader_post(self, post):
        shortcode = (_safe_call(lambda: post.shortcode, "") or "").strip()
        if not shortcode:
            return None

        reel_url = f"https://www.instagram.com/reel/{shortcode}/"

        video_url = _safe_call(lambda: post.video_url, "") or ""
        thumbnail_url = _safe_call(lambda: post.url, "") or ""
        caption = _safe_call(lambda: post.caption, "") or ""
        posted_iso = _safe_call(lambda: post.date_utc.isoformat() if post.date_utc else "", "") or ""
        posted_at = _parse_iso_datetime(posted_iso)

        likes = _to_int(_safe_call(lambda: post.likes, None))
        views = _to_int(_safe_call(lambda: post.video_view_count, None))
        duration = _to_int(_safe_call(lambda: post.video_duration, None))

        return {
            "shortcode": shortcode,
            "url": reel_url,
            "reel_url": reel_url,
            "video_url": video_url,
            "thumbnail_url": thumbnail_url,
            "caption": caption,
            "date": posted_iso,
            "posted_at": posted_at,
            "likes": likes,
            "like_count": likes,
            "views": views,
            "view_count": views,
            "duration": duration,
            "video_duration": duration,
            "comment_count": None,
        }

    def _fetch_reels_ytdlp_with_browser(self, username: str, limit: int):
        if not self.cookies_from_browser:
            raise InstagramError("Browser cookie fallback is disabled")

        browsers = self._browser_candidates(self.browser_name)
        if not browsers:
            raise InstagramError("No valid browser configured for IG_BROWSER")

        last_exc = None
        details = []
        for browser in browsers:
            explicit_profile = (self.browser_profile or "").strip() or None
            profile_candidates = [explicit_profile] if explicit_profile else [None]
            if explicit_profile is not None:
                profile_candidates.append(None)
            for profile_candidate in profile_candidates:
                try:
                    return self._fetch_reels_ytdlp(
                        username,
                        limit,
                        browser=browser,
                        browser_profile=profile_candidate,
                    )
                except Exception as exc:
                    last_exc = exc
                    suffix = f":{profile_candidate}" if profile_candidate else ""
                    details.append(f"{browser}{suffix}: {_safe_error_text(exc)}")
                    continue

        raise InstagramError(
            "Browser cookie extraction failed. " + "; ".join(details)
        ) from last_exc

    def _fetch_reels_ytdlp(
        self,
        username: str,
        limit: int,
        browser: str | None = None,
        browser_profile: str | None = None,
    ):
        try:
            import yt_dlp
        except Exception as exc:
            raise InstagramError("yt-dlp is not installed") from exc

        profile_url = f"https://www.instagram.com/{username}/"
        reels_url = f"https://www.instagram.com/{username}/reels/"
        urls_to_try = [profile_url, reels_url]

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "socket_timeout": 30,
            "retries": 3,
            "playlistend": int(limit),
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            "logger": _YtdlpLogger(),
            "noprogress": True,
        }

        if browser:
            ydl_opts["cookiesfrombrowser"] = (browser, browser_profile, None, None)

        result = None
        last_exc = None
        for candidate_url in urls_to_try:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(candidate_url, download=False)
                if isinstance(result, dict) and result.get("entries"):
                    break
            except Exception as exc:
                last_exc = exc
                continue

        entries = result.get("entries", []) if isinstance(result, dict) else []
        reels = self._normalize_ytdlp_entries(entries, limit)
        if reels:
            return reels, self._default_profile(username)

        if last_exc is not None:
            raise InstagramError(f"yt-dlp extraction failed: {_safe_error_text(last_exc)}") from last_exc
        raise InstagramError("yt-dlp returned no valid reel metadata")

    def _normalize_ytdlp_entries(self, entries, limit: int):
        reels = []
        if not isinstance(entries, list):
            return reels

        for entry in entries:
            if len(reels) >= limit:
                break
            if not isinstance(entry, dict):
                continue

            reel_url = entry.get("webpage_url") or entry.get("url")
            if reel_url and reel_url.startswith("/"):
                reel_url = f"https://www.instagram.com{reel_url}"
            if reel_url and "/reel/" not in reel_url:
                continue

            rid = entry.get("id")
            if not rid and reel_url:
                match = re.search(r"/reel/([^/?#]+)/?", reel_url)
                if match:
                    rid = match.group(1)
            if not rid:
                rid = entry.get("url")
            if not rid:
                continue
            if not reel_url:
                reel_url = f"https://www.instagram.com/reel/{rid}/"

            posted_at = self._parse_ytdlp_date(entry.get("upload_date"))
            if not posted_at and isinstance(entry.get("timestamp"), (int, float)):
                try:
                    posted_at = datetime.utcfromtimestamp(entry.get("timestamp"))
                except Exception:
                    posted_at = None

            reels.append(
                {
                    "shortcode": str(rid),
                    "reel_url": reel_url,
                    "thumbnail_url": entry.get("thumbnail"),
                    "video_url": entry.get("url") or "",
                    "posted_at": posted_at,
                    "like_count": entry.get("like_count"),
                    "comment_count": entry.get("comment_count"),
                    "view_count": entry.get("view_count"),
                    "video_duration": entry.get("duration"),
                    "caption": entry.get("description") or "",
                }
            )

            time.sleep(random.uniform(self.fetch_delay_min, self.fetch_delay_max))

        return reels

    def _browser_candidates(self, value: str):
        allowed = {"chrome", "firefox", "edge", "safari", "brave", "opera"}
        text = (value or "chrome").strip().lower()
        if not text:
            text = "chrome"
        if text in {"auto", "both"}:
            return ["chrome", "edge", "firefox", "brave", "opera", "safari"]

        out = []
        for item in text.replace("|", ",").split(","):
            token = item.strip().lower()
            if not token:
                continue
            alias = {
                "msedge": "edge",
                "microsoft-edge": "edge",
                "google-chrome": "chrome",
            }.get(token, token)
            if alias in allowed and alias not in out:
                out.append(alias)
        return out

    def _default_profile(self, username: str):
        return {
            "username": username,
            "full_name": username,
            "biography": "",
            "profile_pic_url": "",
            "followers": 0,
            "following": 0,
            "post_count": 0,
            "is_private": False,
        }

    def _parse_ytdlp_date(self, value: str | None):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y%m%d")
        except Exception:
            return None

    def _parse_apify_ts(self, value):
        if not value:
            return None
        if isinstance(value, (int, float)):
            try:
                return datetime.utcfromtimestamp(value)
            except Exception:
                return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                return None
        return None

    def _cache_path(self, username: str) -> str:
        safe = "".join([c if c.isalnum() or c == "_" else "_" for c in username])
        return os.path.join(self.temp_dir, f"profile_cache_{safe}.json")

    def _read_cache(self, username: str):
        if self.cache_minutes <= 0:
            return None
        path = self._cache_path(username)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("ts", 0)
            if time.time() - ts > (self.cache_minutes * 60):
                return None
            profile = data.get("profile", self._default_profile(username))
            reels = data.get("reels", [])
            if isinstance(reels, list):
                for item in reels:
                    if not isinstance(item, dict):
                        continue
                    value = item.get("posted_at")
                    if isinstance(value, str) and value:
                        try:
                            item["posted_at"] = datetime.fromisoformat(value)
                        except Exception:
                            item["posted_at"] = None
            return {"profile": profile, "reels": reels}
        except Exception:
            return None

    def _write_cache(self, username: str, profile: dict, reels: list):
        try:
            cached_reels = []
            for reel in reels:
                item = dict(reel)
                posted_at = item.get("posted_at")
                if isinstance(posted_at, datetime):
                    item["posted_at"] = posted_at.isoformat()
                cached_reels.append(item)
            payload = {"ts": time.time(), "profile": profile, "reels": cached_reels}
            with open(self._cache_path(username), "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass


def _safe_error_text(exc: Exception) -> str:
    text = str(exc).strip() if exc else ""
    if not text:
        text = exc.__class__.__name__ if exc else "Unknown error"
    if len(text) > 240:
        text = text[:237] + "..."
    return text


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _instaloader_exc_matches(exc: Exception, *names: str) -> bool:
    if instaloader_exceptions is None or exc is None:
        return False

    classes = []
    for name in names:
        klass = getattr(instaloader_exceptions, name, None)
        if isinstance(klass, type) and issubclass(klass, Exception):
            classes.append(klass)

    return bool(classes) and isinstance(exc, tuple(classes))


def _is_terminal_instaloader_error(reason: str) -> bool:
    text = (reason or "").lower()
    return "was not found" in text or "is private and cannot be accessed" in text


def _parse_iso_datetime(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _to_int(value):
    try:
        return int(value)
    except Exception:
        return None
