from __future__ import annotations

import os

import cloudinary
import cloudinary.uploader


_CONFIGURED = False


def _ensure_configured():
    global _CONFIGURED
    if _CONFIGURED:
        return
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
        api_key=os.getenv("CLOUDINARY_API_KEY", ""),
        api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
        secure=True,
    )
    _CONFIGURED = True


def upload_thumbnail(local_path: str, shortcode: str, username: str) -> dict:
    _ensure_configured()
    if not local_path or not os.path.exists(local_path):
        return {"url": None, "public_id": None}

    try:
        result = cloudinary.uploader.upload(
            local_path,
            public_id=f"insta_sum/{username}/thumbnails/{shortcode}",
            resource_type="image",
            overwrite=True,
            transformation=[
                {"width": 640, "height": 640, "crop": "limit", "quality": "auto:good"},
                {"fetch_format": "auto"},
            ],
        )
        return {"url": result.get("secure_url"), "public_id": result.get("public_id")}
    except Exception:
        return {"url": None, "public_id": None}


def upload_audio(local_path: str, shortcode: str, username: str) -> dict:
    _ensure_configured()
    if not local_path or not os.path.exists(local_path):
        return {"url": None, "public_id": None}

    try:
        result = cloudinary.uploader.upload(
            local_path,
            public_id=f"insta_sum/{username}/audio/{shortcode}",
            resource_type="video",  # Cloudinary uses `video` for audio assets
            overwrite=True,
            format="mp3",
        )
        return {"url": result.get("secure_url"), "public_id": result.get("public_id")}
    except Exception:
        return {"url": None, "public_id": None}


def delete_media(public_id: str, resource_type: str = "image") -> bool:
    _ensure_configured()
    if not public_id:
        return False
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return True
    except Exception:
        return False
