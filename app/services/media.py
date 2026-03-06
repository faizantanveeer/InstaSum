from __future__ import annotations

from contextlib import contextmanager
import os
import shutil
import tempfile
import logging

from .storage import upload_audio, upload_thumbnail
from .utils import build_ytdlp_auth_strategies


class MediaError(Exception):
    pass


logger = logging.getLogger(__name__)


class _YtdlpLogger:
    def debug(self, _msg):
        return

    def warning(self, _msg):
        return

    def error(self, _msg):
        return


@contextmanager
def download_reel_media_tmp(
    reel_url: str,
    shortcode: str,
    cookies_file: str = "",
    cookies_from_browser: bool = True,
    browser_name: str = "edge,chrome",
    browser_profile: str = "",
    ffmpeg_location: str = "",
):
    if not reel_url:
        raise MediaError("Missing reel URL")

    try:
        import yt_dlp
    except Exception as exc:
        raise MediaError("yt-dlp is not installed") from exc

    ffmpeg_bin = _detect_ffmpeg(ffmpeg_location)

    with tempfile.TemporaryDirectory() as tmp_dir:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmp_dir, f"{shortcode}.%(ext)s"),
            "writethumbnail": True,
            "quiet": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            },
            "logger": _YtdlpLogger(),
            "noprogress": True,
        }
        auth_strategies, auth_warnings = build_ytdlp_auth_strategies(
            cookies_file=cookies_file,
            browser_name=browser_name,
            browser_profile=browser_profile,
            enable_browser=cookies_from_browser,
        )
        for warn in auth_warnings:
            logger.warning("Ignoring IG_COOKIES_FILE during media download: %s", warn)
        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = ffmpeg_bin
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                },
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                },
            ]

        last_exc = None
        for _mode, auth_opts in auth_strategies:
            opts = dict(ydl_opts)
            opts.update(auth_opts)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([reel_url])
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            msg = str(last_exc).lower()
            if "ffmpeg" in msg or "ffprobe" in msg:
                raise MediaError(
                    "ffmpeg/ffprobe not found. Install ffmpeg or set FFMPEG_LOCATION in .env"
                ) from last_exc
            raise MediaError("Failed to download reel media") from last_exc

        audio_path = _resolve_audio_file(tmp_dir, shortcode)
        thumb_path = _resolve_thumbnail_file(tmp_dir, shortcode)
        if not audio_path:
            raise MediaError("Failed to download reel audio")

        yield {
            "audio_path": audio_path,
            "thumbnail_path": thumb_path,
            "tmp_dir": tmp_dir,
        }


def download_and_upload_reel(
    reel_url: str,
    shortcode: str,
    username: str,
    cookies_file: str = "",
    cookies_from_browser: bool = True,
    browser_name: str = "edge,chrome",
    browser_profile: str = "",
    ffmpeg_location: str = "",
):
    with download_reel_media_tmp(
        reel_url,
        shortcode,
        cookies_file,
        cookies_from_browser,
        browser_name,
        browser_profile,
        ffmpeg_location,
    ) as media:
        audio_result = upload_audio(media["audio_path"], shortcode, username)
        thumb_result = upload_thumbnail(media["thumbnail_path"], shortcode, username)
        return {
            "audio_url": audio_result.get("url"),
            "audio_cloudinary_id": audio_result.get("public_id"),
            "thumbnail_url": thumb_result.get("url"),
            "thumbnail_cloudinary_id": thumb_result.get("public_id"),
            "audio_local_path": None,
        }


# Backward compatibility wrapper used by legacy worker paths.
def download_reel_audio(
    reel_url: str,
    shortcode: str,
    username: str,
    _unused_downloads_dir: str,
    cookies_file: str = "",
    cookies_from_browser: bool = True,
    browser_name: str = "edge,chrome",
    browser_profile: str = "",
    ffmpeg_location: str = "",
):
    return download_and_upload_reel(
        reel_url=reel_url,
        shortcode=shortcode,
        username=username,
        cookies_file=cookies_file,
        cookies_from_browser=cookies_from_browser,
        browser_name=browser_name,
        browser_profile=browser_profile,
        ffmpeg_location=ffmpeg_location,
    )


# Thumbnail-only local persistence is deprecated in Cloudinary mode.
def download_reel_thumbnail(
    _reel_url: str,
    _shortcode: str,
    _username: str,
    _downloads_dir: str,
    _cookies_file: str = "",
):
    return None


def _detect_ffmpeg(ffmpeg_location: str) -> str:
    if ffmpeg_location:
        loc = ffmpeg_location
        if os.path.isfile(loc):
            loc_dir = os.path.dirname(loc)
            if os.path.exists(os.path.join(loc_dir, "ffprobe.exe")) or os.path.exists(
                os.path.join(loc_dir, "ffprobe")
            ):
                return loc_dir
            return ""
        if os.path.isdir(loc):
            if os.path.exists(os.path.join(loc, "ffmpeg.exe")) or os.path.exists(
                os.path.join(loc, "ffmpeg")
            ):
                if os.path.exists(os.path.join(loc, "ffprobe.exe")) or os.path.exists(
                    os.path.join(loc, "ffprobe")
                ):
                    return loc
            return ""
        return ""

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        return os.path.dirname(ffmpeg_path)

    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            candidate_dir = os.path.dirname(candidate)
            if os.path.exists(os.path.join(candidate_dir, "ffprobe.exe")):
                return candidate_dir

    return ""


def _resolve_audio_file(base_dir: str, shortcode: str):
    exts = ["mp3", "m4a", "mp4", "webm", "aac", "ogg", "opus", "mkv", "wav"]
    for ext in exts:
        candidate = os.path.join(base_dir, f"{shortcode}.{ext}")
        if os.path.exists(candidate):
            return candidate
    for name in os.listdir(base_dir):
        if name.startswith(shortcode + ".") and not name.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp", ".json", ".txt")
        ):
            return os.path.join(base_dir, name)
    return None


def _resolve_thumbnail_file(base_dir: str, shortcode: str):
    exts = ["jpg", "jpeg", "png", "webp"]
    for ext in exts:
        candidate = os.path.join(base_dir, f"{shortcode}.{ext}")
        if os.path.exists(candidate):
            return candidate
    for name in os.listdir(base_dir):
        if name.startswith(shortcode + ".") and name.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            return os.path.join(base_dir, name)
    return None
