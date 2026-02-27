from __future__ import annotations

import requests


def verify_captcha(token: str, secret: str, remote_ip: str | None = None) -> bool:
    if not secret:
        # If secret not configured, bypass to avoid blocking dev
        return True
    if not token:
        return False

    data = {
        "response": token,
        "secret": secret,
    }
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        resp = requests.post("https://hcaptcha.com/siteverify", data=data, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        return bool(payload.get("success"))
    except Exception:
        return False


