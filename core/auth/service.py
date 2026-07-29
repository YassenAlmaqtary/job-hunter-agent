"""
PostgreSQL-backed authentication service (SQLAlchemy ORM).

EN: Users and server-side sessions live in Postgres; agent runs require a valid session.
    Streamlit login UI lives in ``app.auth_ui`` — this module is the domain logic.
AR: منطق المصادقة والجلسات عبر ORM؛ واجهة الدخول في ``app.auth_ui``.
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
from sqlalchemy import select

from core.db.database import database_configured, ensure_schema, session_scope
from core.db.models import AgentRun, User, UserSession

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


def _user_to_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "created_at": user.created_at,
    }


def _session_to_dict(row: UserSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "graph_thread_id": row.graph_thread_id,
        "expires_at": row.expires_at,
        "created_at": row.created_at,
        "last_seen_at": row.last_seen_at,
    }


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
    with session_scope() as db:
        row = UserSession(
            user_id=uuid.UUID(str(user_id)),
            token_hash=token_hash,
            graph_thread_id=graph_thread_id,
            expires_at=expires_at,
        )
        db.add(row)
        db.flush()
        payload = _session_to_dict(row)
    return token, payload


def _load_session_from_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    with session_scope() as db:
        stmt = (
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.token_hash == token_hash, UserSession.expires_at > now)
        )
        result = db.execute(stmt).first()
        if not result:
            return None
        session_row, user = result
        session_row.last_seen_at = now
        db.flush()
        return {
            "session_id": session_row.id,
            "graph_thread_id": session_row.graph_thread_id,
            "expires_at": session_row.expires_at,
            "last_seen_at": session_row.last_seen_at,
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
        }


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
    with session_scope() as db:
        row = db.get(UserSession, uuid.UUID(str(session_id)))
        if row is None or str(row.user_id) != str(user_id):
            raise PermissionError("جلسة الوكيل غير صالحة. أعد تسجيل الدخول.")
        row.graph_thread_id = graph_thread_id
        row.last_seen_at = datetime.now(timezone.utc)

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

    with session_scope() as db:
        if db.scalar(select(User.id).where(User.email == email_clean)):
            return False, "هذا البريد مسجّل مسبقاً."
        if db.scalar(select(User.id).where(User.username == username_clean)):
            return False, "اسم المستخدم مستخدم مسبقاً."

        user = User(
            email=email_clean,
            username=username_clean,
            password_hash=_hash_password(password_clean),
        )
        db.add(user)
        db.flush()
        user_payload = _user_to_dict(user)

    token, session_row = _create_db_session(user_id=str(user_payload["id"]))
    _store_browser_session(token=token, user=user_payload, session_row=session_row)
    st.session_state["graph_thread_id"] = session_row["graph_thread_id"]
    return True, "تم إنشاء الحساب وتسجيل الدخول."


def sign_in(*, email: str, password: str) -> tuple[bool, str]:
    email_clean = (email or "").strip().lower()
    password_clean = password or ""
    if not email_clean or not password_clean:
        return False, "يرجى إدخال البريد الإلكتروني وكلمة المرور."

    with session_scope() as db:
        user = db.scalar(select(User).where(User.email == email_clean))
        if user is None or not _verify_password(password_clean, user.password_hash):
            return False, "البريد الإلكتروني أو كلمة المرور غير صحيحة."
        user_payload = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
        }

    token, session_row = _create_db_session(user_id=str(user_payload["id"]))
    _store_browser_session(token=token, user=user_payload, session_row=session_row)
    st.session_state["graph_thread_id"] = session_row["graph_thread_id"]
    return True, "تم تسجيل الدخول بنجاح."


def sign_out() -> None:
    token = st.session_state.get(_SESSION_TOKEN_KEY)
    if isinstance(token, str) and token:
        token_hash = _hash_token(token)
        with session_scope() as db:
            row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
            if row is not None:
                db.delete(row)
    _clear_browser_session()


def record_agent_run(*, job_title: str, status: str = "completed") -> None:
    user_id = get_current_user_id()
    session_id = get_session_id()
    if not user_id or not session_id:
        return
    with session_scope() as db:
        db.add(
            AgentRun(
                user_id=uuid.UUID(str(user_id)),
                session_id=uuid.UUID(str(session_id)),
                job_title=job_title.strip(),
                status=status,
            )
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
