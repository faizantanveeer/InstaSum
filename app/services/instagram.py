from __future__ import annotations

import json
import os
import time
from datetime import datetime

import requests


class InstagramError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class InstagramService:
    def __init__(
        self,
        rapidapi_key: str = "",
        apify_token: str = "",
        cookies_file: str = "",
        temp_dir: str = "./tmp",
        cache_minutes: int = 60,
    ):
        self.rapidapi_key = rapidapi_key
        self.apify_token = apify_token
        self.cookies_file = cookies_file
        self.temp_dir = temp_dir
        self.cache_minutes = cache_minutes
        os.makedirs(self.temp_dir, exist_ok=True)

    def fetch_profile(self, username: str, preview_limit: int = 9, force_refresh: bool = False):
        if not force_refresh:
            cached = self._read_cache(username)
            if cached:
                return cached["profile"], cached["reels"]

        reels, source, profile = self.fetch_reels(username, limit=preview_limit)
        if not profile:
            profile = {
                "username": username,
                "full_name": username,
                "biography": "",
                "profile_pic_url": "",
                "followers": 0,
                "following": 0,
                "post_count": 0,
                "is_private": False,
                "source": source,
            }
        else:
            profile["source"] = source

        self._write_cache(username, profile, reels)
        return profile, reels

    def fetch_reels(self, username: str, limit: int = 100):
        errors = []

        # Layer 1: RapidAPI
        try:
            reels, profile = self._fetch_reels_rapidapi(username, limit)
            return reels, "rapidapi", profile
        except InstagramError as exc:
            errors.append(f"RapidAPI failed: {exc}")

        # Layer 2: yt-dlp
        try:
            reels, profile = self._fetch_reels_ytdlp(username, limit)
            return reels, "ytdlp", profile
        except InstagramError as exc:
            errors.append(f"yt-dlp failed: {exc}")

        # Layer 3: Apify
        try:
            reels, profile = self._fetch_reels_apify(username, limit)
            return reels, "apify", profile
        except InstagramError as exc:
            errors.append(f"Apify failed: {exc}")

        raise InstagramError(
            "All fetch methods failed. " + "; ".join(errors)
        )

    def _fetch_reels_rapidapi(self, username: str, limit: int):
        if not self.rapidapi_key:
            raise InstagramError("RAPIDAPI_KEY not set")

        url = "https://instagram-scraper-api2.p.rapidapi.com/v1/reels"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        params = {"username_or_id_or_url": username}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except Exception as exc:
            raise InstagramError("RapidAPI request failed") from exc
        if resp.status_code == 429:
            raise InstagramError("RapidAPI quota or rate limit exceeded")
        if resp.status_code >= 400:
            raise InstagramError(f"RapidAPI request failed ({resp.status_code})")

        try:
            data = resp.json() if resp.text else {}
        except Exception as exc:
            raise InstagramError("RapidAPI returned invalid JSON") from exc
        if not isinstance(data, dict):
            data = {}
        data_node = data.get("data")
        if not isinstance(data_node, dict):
            data_node = {}
        items = (
            data_node.get("items")
            or data_node.get("reels")
            or data.get("items")
            or []
        )
        if not isinstance(items, list):
            items = []

        profile = self._extract_profile_from_rapidapi(data, username)

        reels = []
        for item in items:
            if len(reels) >= limit:
                break
            if not isinstance(item, dict):
                continue
            code = item.get("code") or item.get("shortcode") or item.get("id")
            video_url = item.get("video_url")
            if not video_url:
                video_versions = item.get("video_versions") or []
                if video_versions and isinstance(video_versions, list):
                    first_version = video_versions[0] if video_versions else {}
                    if isinstance(first_version, dict):
                        video_url = first_version.get("url")
            thumb = (
                item.get("thumbnail_url")
                or item.get("display_url")
                or item.get("image_url")
            )
            caption = ""
            cap = item.get("caption")
            if isinstance(cap, dict):
                caption = cap.get("text") or ""
            elif isinstance(cap, str):
                caption = cap
            taken_at = item.get("taken_at") or item.get("taken_at_timestamp")
            posted_at = None
            if isinstance(taken_at, (int, float)):
                posted_at = datetime.utcfromtimestamp(taken_at)

            reels.append(
                {
                    "shortcode": code or "",
                    "reel_url": f"https://www.instagram.com/reel/{code}/" if code else "",
                    "thumbnail_url": thumb,
                    "video_url": video_url or "",
                    "posted_at": posted_at,
                    "like_count": item.get("like_count") or item.get("likes"),
                    "comment_count": item.get("comment_count") or item.get("comments"),
                    "view_count": item.get("play_count") or item.get("view_count"),
                    "video_duration": item.get("video_duration") or item.get("duration"),
                    "caption": caption,
                }
            )

        return reels, profile

    def _fetch_reels_ytdlp(self, username: str, limit: int):
        if not self.cookies_file or not os.path.exists(self.cookies_file):
            raise InstagramError("IG_COOKIES_FILE not found for yt-dlp fallback")

        try:
            import yt_dlp
        except Exception as exc:
            raise InstagramError("yt-dlp not installed") from exc

        url = f"https://www.instagram.com/{username}/reels/"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "cookiefile": self.cookies_file,
            "socket_timeout": 30,
            "retries": 3,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)

        entries = result.get("entries", []) if isinstance(result, dict) else []
        reels = []
        for entry in entries:
            if len(reels) >= limit:
                break
            if not isinstance(entry, dict):
                continue
            rid = entry.get("id") or entry.get("url")
            reel_url = entry.get("url")
            if reel_url and reel_url.startswith("/"):
                reel_url = f"https://www.instagram.com{reel_url}"
            if not reel_url and rid:
                reel_url = f"https://www.instagram.com/reel/{rid}/"
            reels.append(
                {
                    "shortcode": rid or "",
                    "reel_url": reel_url or "",
                    "thumbnail_url": entry.get("thumbnail"),
                    "video_url": entry.get("url") or "",
                    "posted_at": self._parse_ytdlp_date(entry.get("upload_date")),
                    "like_count": entry.get("like_count"),
                    "comment_count": entry.get("comment_count"),
                    "view_count": entry.get("view_count"),
                    "video_duration": entry.get("duration"),
                    "caption": entry.get("description") or "",
                }
            )

        profile = {"username": username, "full_name": username}
        return reels, profile

    def _fetch_reels_apify(self, username: str, limit: int):
        if not self.apify_token:
            raise InstagramError("APIFY_TOKEN not set")

        try:
            from apify_client import ApifyClient
        except Exception as exc:
            raise InstagramError("apify-client not installed") from exc

        client = ApifyClient(self.apify_token)
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username}/reels/"],
            "resultsType": "posts",
            "resultsLimit": min(limit, 50),
            "addParentData": False,
        }
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        items = client.dataset(run["defaultDatasetId"]).iterate_items()

        reels = []
        profile = {"username": username, "full_name": username}
        for item in items:
            if len(reels) >= limit:
                break
            if not isinstance(item, dict):
                continue
            if item.get("type") and item.get("type") != "Video":
                continue
            reels.append(
                {
                    "shortcode": item.get("shortCode") or item.get("id") or "",
                    "reel_url": item.get("url") or "",
                    "thumbnail_url": item.get("displayUrl"),
                    "video_url": item.get("videoUrl") or "",
                    "posted_at": self._parse_apify_ts(item.get("timestamp")),
                    "like_count": item.get("likesCount"),
                    "comment_count": item.get("commentsCount"),
                    "view_count": item.get("videoViewCount"),
                    "video_duration": item.get("videoDuration"),
                    "caption": item.get("caption") or "",
                }
            )

        return reels, profile

    def _parse_ytdlp_date(self, value: str | None):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y%m%d")
        except Exception:
            return None

    def _parse_apify_ts(self, value: str | None):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def _extract_profile_from_rapidapi(self, data: dict, username: str) -> dict:
        profile = {"username": username, "full_name": username}
        if not isinstance(data, dict):
            return profile
        data_node = data.get("data")
        if not isinstance(data_node, dict):
            data_node = {}
        user = data_node.get("user") or data.get("user") or {}
        if not isinstance(user, dict):
            return profile
        if isinstance(user, dict):
            profile.update(
                {
                    "username": user.get("username", username),
                    "full_name": user.get("full_name", "") or user.get("name", "") or username,
                    "biography": user.get("biography", ""),
                    "profile_pic_url": user.get("profile_pic_url") or user.get("profile_pic_url_hd") or "",
                    "followers": user.get("follower_count") or user.get("followers") or 0,
                    "following": user.get("following_count") or user.get("following") or 0,
                    "post_count": user.get("media_count") or user.get("posts") or 0,
                    "is_private": user.get("is_private") or False,
                }
            )
        return profile

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
            profile = data.get("profile", {})
            return {"profile": profile, "reels": data.get("reels", [])}
        except Exception:
            return None

    def _write_cache(self, username: str, profile: dict, reels: list):
        try:
            cached_reels = []
            for r in reels:
                item = dict(r)
                posted_at = item.get("posted_at")
                if isinstance(posted_at, datetime):
                    item["posted_at"] = posted_at.isoformat()
                cached_reels.append(item)
            payload = {"ts": time.time(), "profile": profile, "reels": cached_reels}
            with open(self._cache_path(username), "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass
