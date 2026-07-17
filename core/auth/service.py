"""
PostgreSQL-backed authentication service.

EN: Users and server-side sessions live in Postgres; agent runs require a valid session.
    Streamlit login UI lives in ``app.auth_ui`` — this module is the domain logic.
AR: منطق المصادقة والجلسات؛ واجهة الدخول في ``app.auth_ui``.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import streamlit as st

from core.db.database import (
    database_configured,
    ensure_schema,
    execute,
    execute_returning,
    fetch_one,
)

_SESSION_TOKEN_KEY = "auth_session_token"
_SESSION_USER_KEY = "auth_user"
_SESSION_META_KEY = "auth_session_meta"
_DEFAULT_SESSION_HOURS = 168  # 7 days
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\u0600-\u06FF]{3,32}$")


def auth_disabled() -> bool:
    return (os.getenv("AUTH_DISABLED") or "").strip().lower() in {"1", "true", "yes"}


def auth_required() -> bool:
    return database_configured() and not auth_disabled()


def _session_ttl_hours() -> int:
    raw = (os.getenv("AUTH_SESSION_HOURS") or "").strip()
    try:
        return max(1, int(raw)) if raw else _DEFAULT_SESSION_HOURS
    except ValueError:
        return _DEFAULT_SESSION_HOURS


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _new_graph_thread_id(user_id: str) -> str:
    return f"{user_id}:{uuid.uuid4()}"


def _store_browser_session(*, token: str, user: dict[str, Any], session_row: dict[str, Any]) -> None:
    st.session_state[_SESSION_TOKEN_KEY] = token
    st.session_state[_SESSION_USER_KEY] = {
        "id": str(user["id"]),
        "email": user["email"],
        "username": user["username"],
    }
    st.session_state[_SESSION_META_KEY] = {
        "session_id": str(session_row["id"]),
        "graph_thread_id": session_row["graph_thread_id"],
        "expires_at": session_row["expires_at"].isoformat() if session_row.get("expires_at") else "",
    }


def _clear_browser_session() -> None:
    for key in (_SESSION_TOKEN_KEY, _SESSION_USER_KEY, _SESSION_META_KEY, "graph_thread_id"):
        st.session_state.pop(key, None)


def _create_db_session(*, user_id: str) -> tuple[str, dict[str, Any]]:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    graph_thread_id = _new_graph_thread_id(user_id)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_session_ttl_hours())
    row = execute_returning(
        """
        INSERT INTO user_sessions (user_id, token_hash, graph_thread_id, expires_at)
        VALUES (%s, %s, %s, %s)
        RETURNING id, user_id, graph_thread_id, expires_at, created_at, last_seen_at
        """,
        (user_id, token_hash, graph_thread_id, expires_at),
    )
    if not row:
        raise RuntimeError("تعذر إنشاء جلسة المستخدم.")
    return token, row


def _load_session_from_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    row = fetch_one(
        """
        SELECT
            s.id AS session_id,
            s.graph_thread_id,
            s.expires_at,
            s.last_seen_at,
            u.id AS user_id,
            u.email,
            u.username
        FROM user_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = %s
          AND s.expires_at > NOW()
        """,
        (_hash_token(token),),
    )
    if not row:
        return None

    execute(
        "UPDATE user_sessions SET last_seen_at = NOW() WHERE id = %s",
        (row["session_id"],),
    )
    return row


def ensure_auth_session() -> None:
    if not auth_required():
        return
    ensure_schema()
    token = st.session_state.get(_SESSION_TOKEN_KEY)
    if not isinstance(token, str) or not token:
        _clear_browser_session()
        return

    row = _load_session_from_token(token)
    if not row:
        _clear_browser_session()
        return

    st.session_state[_SESSION_USER_KEY] = {
        "id": str(row["user_id"]),
        "email": row["email"],
        "username": row["username"],
    }
    st.session_state[_SESSION_META_KEY] = {
        "session_id": str(row["session_id"]),
        "graph_thread_id": row["graph_thread_id"],
        "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else "",
    }
    st.session_state["graph_thread_id"] = row["graph_thread_id"]


def is_authenticated() -> bool:
    if not auth_required():
        return True
    ensure_auth_session()
    return bool(st.session_state.get(_SESSION_USER_KEY))


def get_current_user() -> dict[str, Any] | None:
    if not auth_required():
        return None
    user = st.session_state.get(_SESSION_USER_KEY)
    return user if isinstance(user, dict) and user.get("id") else None


def get_current_user_id() -> str | None:
    user = get_current_user()
    return str(user["id"]) if user and user.get("id") else None


def get_session_id() -> str | None:
    meta = st.session_state.get(_SESSION_META_KEY)
    if isinstance(meta, dict) and meta.get("session_id"):
        return str(meta["session_id"])
    return None


def get_graph_thread_id() -> str | None:
    ensure_auth_session()
    meta = st.session_state.get(_SESSION_META_KEY)
    if isinstance(meta, dict) and meta.get("graph_thread_id"):
        return str(meta["graph_thread_id"])
    return st.session_state.get("graph_thread_id")


def reset_graph_thread() -> str:
    user_id = get_current_user_id()
    session_id = get_session_id()
    if not user_id or not session_id:
        raise PermissionError("يجب تسجيل الدخول لتشغيل الوكيل.")

    graph_thread_id = _new_graph_thread_id(user_id)
    execute(
        "UPDATE user_sessions SET graph_thread_id = %s, last_seen_at = NOW() WHERE id = %s AND user_id = %s",
        (graph_thread_id, session_id, user_id),
    )
    meta = st.session_state.get(_SESSION_META_KEY)
    if isinstance(meta, dict):
        meta["graph_thread_id"] = graph_thread_id
        st.session_state[_SESSION_META_KEY] = meta
    st.session_state["graph_thread_id"] = graph_thread_id
    return graph_thread_id


def get_display_name() -> str:
    user = get_current_user()
    if not user:
        return ""
    return (user.get("username") or user.get("email") or "").strip() or "مستخدم"


def sign_up(*, email: str, password: str, username: str) -> tuple[bool, str]:
    email_clean = (email or "").strip().lower()
    password_clean = password or ""
    username_clean = (username or "").strip()

    if not username_clean:
        return False, "يرجى إدخال اسم المستخدم."
    if not _USERNAME_RE.fullmatch(username_clean):
        return False, "اسم المستخدم: 3–32 حرفاً (حروف، أرقام، _)."
    if not email_clean or not password_clean:
        return False, "يرجى إدخال البريد الإلكتروني وكلمة المرور."
    if len(password_clean) < 6:
        return False, "كلمة المرور يجب أن تكون 6 أحرف على الأقل."

    if fetch_one("SELECT id FROM users WHERE email = %s", (email_clean,)):
        return False, "هذا البريد مسجّل مسبقاً."
    if fetch_one("SELECT id FROM users WHERE username = %s", (username_clean,)):
        return False, "اسم المستخدم مستخدم مسبقاً."

    user = execute_returning(
        """
        INSERT INTO users (email, username, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id, email, username, created_at
        """,
        (email_clean, username_clean, _hash_password(password_clean)),
    )
    if not user:
        return False, "تعذر إنشاء الحساب."

    token, session_row = _create_db_session(user_id=str(user["id"]))
    _store_browser_session(token=token, user=user, session_row=session_row)
    st.session_state["graph_thread_id"] = session_row["graph_thread_id"]
    return True, "تم إنشاء الحساب وتسجيل الدخول."


def sign_in(*, email: str, password: str) -> tuple[bool, str]:
    email_clean = (email or "").strip().lower()
    password_clean = password or ""
    if not email_clean or not password_clean:
        return False, "يرجى إدخال البريد الإلكتروني وكلمة المرور."

    user = fetch_one(
        "SELECT id, email, username, password_hash FROM users WHERE email = %s",
        (email_clean,),
    )
    if not user or not _verify_password(password_clean, user["password_hash"]):
        return False, "البريد الإلكتروني أو كلمة المرور غير صحيحة."

    token, session_row = _create_db_session(user_id=str(user["id"]))
    _store_browser_session(
        token=token,
        user={"id": user["id"], "email": user["email"], "username": user["username"]},
        session_row=session_row,
    )
    st.session_state["graph_thread_id"] = session_row["graph_thread_id"]
    return True, "تم تسجيل الدخول بنجاح."


def sign_out() -> None:
    token = st.session_state.get(_SESSION_TOKEN_KEY)
    if isinstance(token, str) and token:
        execute("DELETE FROM user_sessions WHERE token_hash = %s", (_hash_token(token),))
    _clear_browser_session()


def record_agent_run(*, job_title: str, status: str = "completed") -> None:
    user_id = get_current_user_id()
    session_id = get_session_id()
    if not user_id or not session_id:
        return
    execute(
        """
        INSERT INTO agent_runs (user_id, session_id, job_title, status)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, session_id, job_title.strip(), status),
    )


def require_authenticated_for_agent() -> None:
    if not auth_required():
        return
    ensure_auth_session()
    if not get_current_user_id() or not get_graph_thread_id():
        st.warning("يجب تسجيل الدخول لتشغيل الوكيل.")
        st.stop()


def assert_streamlit_agent_allowed() -> str:
    if not auth_required():
        return ""
    ensure_auth_session()
    user_id = get_current_user_id()
    thread_id = get_graph_thread_id()
    if not user_id or not thread_id:
        raise PermissionError("يجب تسجيل الدخول لتشغيل الوكيل.")
    if not thread_id.startswith(f"{user_id}:"):
        raise PermissionError("جلسة الوكيل غير صالحة. أعد تسجيل الدخول.")
    return user_id
