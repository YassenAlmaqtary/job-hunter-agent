"""
Google OAuth 2.0 helpers for Streamlit login.

EN: Builds the consent URL and exchanges the auth code for a verified Google profile.
    Uses HMAC-signed ``state`` so Streamlit session loss after redirect does not break login.
AR: رابط موافقة Google؛ التحقق من state بتوقيع حتى لا تفشل الجلسة بعد الرجوع.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_OAUTH_SCOPES = "openid email profile"
_STATE_MAX_AGE_SECONDS = 600


def google_oauth_configured() -> bool:
    return bool(
        (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
        and (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
        and (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()
    )


def _client_id() -> str:
    return (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()


def _redirect_uri() -> str:
    return (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()


def _state_signing_key() -> bytes:
    raw = (
        (os.getenv("GOOGLE_OAUTH_STATE_SECRET") or "").strip()
        or _client_secret()
        or "job-hunter-oauth-state"
    )
    return raw.encode("utf-8")


def new_oauth_state() -> str:
    """Return a self-validating state token (nonce.ts.signature)."""
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    payload = f"{nonce}.{ts}"
    sig = hmac.new(_state_signing_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def verify_oauth_state(state: str, *, max_age_seconds: int = _STATE_MAX_AGE_SECONDS) -> bool:
    """Verify HMAC state without relying on Streamlit session_state."""
    raw = (state or "").strip()
    parts = raw.split(".")
    if len(parts) != 3:
        return False
    nonce, ts, sig = parts
    if not nonce or not ts or not sig:
        return False
    try:
        issued_at = int(ts)
    except ValueError:
        return False
    if abs(int(time.time()) - issued_at) > max_age_seconds:
        return False
    payload = f"{nonce}.{ts}"
    expected = hmac.new(_state_signing_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(sig, expected)


def build_google_auth_url(*, state: str) -> str:
    if not google_oauth_configured():
        raise RuntimeError("Google OAuth غير مضبوط.")
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": _OAUTH_SCOPES,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"فشل تبادل رمز Google: {detail or exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("استجابة Google غير صالحة.")
    return payload


def _get_json(url: str, *, access_token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"فشل جلب ملف Google: {detail or exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ملف Google غير صالح.")
    return payload


def exchange_code_for_profile(*, code: str) -> dict[str, str]:
    """
    Exchange authorization code → access token → userinfo.

    Returns keys: sub, email, name (optional), picture (optional).
    """
    if not google_oauth_configured():
        raise RuntimeError("Google OAuth غير مضبوط.")
    token_payload = _post_form(
        _GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        },
    )
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("لم يُرجع Google رمز وصول.")

    info = _get_json(_GOOGLE_USERINFO_URL, access_token=access_token)
    sub = str(info.get("sub") or "").strip()
    email = str(info.get("email") or "").strip().lower()
    if not sub or not email:
        raise RuntimeError("حساب Google بدون بريد أو معرّف صالح.")
    if info.get("email_verified") is False:
        raise RuntimeError("بريد Google غير موثّق.")

    return {
        "sub": sub,
        "email": email,
        "name": str(info.get("name") or "").strip(),
        "picture": str(info.get("picture") or "").strip(),
    }
