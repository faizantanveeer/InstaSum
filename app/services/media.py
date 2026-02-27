from __future__ import annotations

import os
import shutil

AUDIO_SUBDIR = "audio"
THUMBNAILS_SUBDIR = "thumbnails"


class MediaError(Exception):
    pass


def download_reel_audio(
    reel_url: str,
    shortcode: str,
    username: str,
    downloads_dir: str,
    cookies_file: str = "",
    ffmpeg_location: str = "",
):
    if not reel_url:
        raise MediaError("Missing reel URL")
    try:
        import yt_dlp
    except Exception as exc:
        raise MediaError("yt-dlp is not installed") from exc

    ffmpeg_location = _detect_ffmpeg(ffmpeg_location)
    user_dir, audio_dir, thumbs_dir = _user_dirs(downloads_dir, username)

    existing_audio_path, _ = _resolve_audio_file(user_dir, shortcode)
    existing_thumb_path, _ = _resolve_thumbnail_file(user_dir, shortcode)
    if existing_audio_path:
        existing_audio_path = _move_to_subdir(existing_audio_path, audio_dir)
        if existing_thumb_path:
            existing_thumb_path = _move_to_subdir(existing_thumb_path, thumbs_dir)
        return {
            "audio_path": existing_audio_path,
            "thumbnail_path": existing_thumb_path,
            "audio_file": _to_user_relative_path(user_dir, existing_audio_path),
            "thumbnail_file": _to_user_relative_path(user_dir, existing_thumb_path),
        }

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(user_dir, f"{shortcode}.%(ext)s"),
        "writethumbnail": True,
        "quiet": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        },
    }
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts["cookiefile"] = cookies_file
    if ffmpeg_location:
        ydl_opts["ffmpeg_location"] = ffmpeg_location
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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([reel_url])
    except Exception as exc:
        msg = str(exc)
        audio_path, _ = _resolve_audio_file(user_dir, shortcode)
        thumb_path, _ = _resolve_thumbnail_file(user_dir, shortcode)
        if audio_path:
            audio_path = _move_to_subdir(audio_path, audio_dir)
            if thumb_path:
                thumb_path = _move_to_subdir(thumb_path, thumbs_dir)
            return {
                "audio_path": audio_path,
                "thumbnail_path": thumb_path,
                "audio_file": _to_user_relative_path(user_dir, audio_path),
                "thumbnail_file": _to_user_relative_path(user_dir, thumb_path),
            }
        if "ffmpeg" in msg.lower() or "ffprobe" in msg.lower():
            raise MediaError(
                "ffmpeg/ffprobe not found. Install ffmpeg or set FFMPEG_LOCATION in .env"
            ) from exc
        raise MediaError("Failed to download reel audio") from exc

    audio_path, _ = _resolve_audio_file(user_dir, shortcode)
    thumb_path, _ = _resolve_thumbnail_file(user_dir, shortcode)
    if not audio_path:
        raise MediaError("Failed to download reel audio")

    audio_path = _move_to_subdir(audio_path, audio_dir)
    if thumb_path:
        thumb_path = _move_to_subdir(thumb_path, thumbs_dir)

    return {
        "audio_path": audio_path,
        "thumbnail_path": thumb_path,
        "audio_file": _to_user_relative_path(user_dir, audio_path),
        "thumbnail_file": _to_user_relative_path(user_dir, thumb_path),
    }


def download_reel_thumbnail(
    reel_url: str,
    shortcode: str,
    username: str,
    downloads_dir: str,
    cookies_file: str = "",
):
    if not reel_url or not shortcode:
        return None

    user_dir, _, thumbs_dir = _user_dirs(downloads_dir, username)

    existing_path, _ = _resolve_thumbnail_file(user_dir, shortcode)
    if existing_path:
        existing_path = _move_to_subdir(existing_path, thumbs_dir)
        return _to_user_relative_path(user_dir, existing_path)

    try:
        import yt_dlp
    except Exception:
        return None

    ydl_opts = {
        "skip_download": True,
        "writethumbnail": True,
        "quiet": True,
        "outtmpl": os.path.join(user_dir, f"{shortcode}.%(ext)s"),
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        },
    }
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts["cookiefile"] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([reel_url])
    except Exception:
        pass

    thumb_path, _ = _resolve_thumbnail_file(user_dir, shortcode)
    if not thumb_path:
        return None
    thumb_path = _move_to_subdir(thumb_path, thumbs_dir)
    return _to_user_relative_path(user_dir, thumb_path)


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


def _user_dirs(downloads_dir: str, username: str):
    user_dir = os.path.join(downloads_dir, username)
    audio_dir = os.path.join(user_dir, AUDIO_SUBDIR)
    thumbs_dir = os.path.join(user_dir, THUMBNAILS_SUBDIR)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)
    return user_dir, audio_dir, thumbs_dir


def _to_user_relative_path(user_dir: str, abs_path: str | None):
    if not abs_path:
        return None
    rel = os.path.relpath(abs_path, user_dir)
    return rel.replace("\\", "/")


def _move_to_subdir(source_path: str, target_dir: str):
    if not source_path:
        return source_path

    source_dir = os.path.dirname(source_path)
    if os.path.normcase(source_dir) == os.path.normcase(target_dir):
        return source_path

    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, os.path.basename(source_path))
    if os.path.normcase(source_path) == os.path.normcase(target_path):
        return source_path
    if os.path.exists(target_path):
        return target_path

    try:
        shutil.move(source_path, target_path)
        return target_path
    except Exception:
        return source_path


def _resolve_audio_file(user_dir: str, shortcode: str):
    audio_dir = os.path.join(user_dir, AUDIO_SUBDIR)
    search_dirs = [audio_dir, user_dir]

    exts = ["mp3", "m4a", "mp4", "webm", "aac", "ogg", "opus", "mkv", "wav"]
    for directory in search_dirs:
        for ext in exts:
            candidate = os.path.join(directory, f"{shortcode}.{ext}")
            if os.path.exists(candidate):
                return candidate, os.path.basename(candidate)
        if os.path.isdir(directory):
            for name in os.listdir(directory):
                if name.startswith(shortcode + ".") and not name.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp", ".json", ".txt")
                ):
                    return os.path.join(directory, name), name
    return None, None


def _resolve_thumbnail_file(user_dir: str, shortcode: str):
    thumbs_dir = os.path.join(user_dir, THUMBNAILS_SUBDIR)
    search_dirs = [thumbs_dir, user_dir]

    exts = ["jpg", "jpeg", "png", "webp"]
    for directory in search_dirs:
        for ext in exts:
            candidate = os.path.join(directory, f"{shortcode}.{ext}")
            if os.path.exists(candidate):
                return candidate, os.path.basename(candidate)
        if os.path.isdir(directory):
            for name in os.listdir(directory):
                if name.startswith(shortcode + ".") and name.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp")
                ):
                    return os.path.join(directory, name), name
    return None, None
