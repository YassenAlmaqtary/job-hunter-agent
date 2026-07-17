from __future__ import annotations

from core.auth import service as auth


def test_auth_required_when_database_configured(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("AUTH_DISABLED", "false")
    assert auth.auth_required() is True


def test_auth_disabled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    assert auth.auth_required() is False


def test_hash_and_verify_password_roundtrip():
    hashed = auth._hash_password("secret123")
    assert auth._verify_password("secret123", hashed) is True
    assert auth._verify_password("wrong", hashed) is False


def test_sign_up_requires_username(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")

    def fake_fetch_one(query, params=()):
        return None

    monkeypatch.setattr(auth, "fetch_one", fake_fetch_one)
    ok, message = auth.sign_up(email="a@b.com", password="secret123", username="")
    assert ok is False
    assert "اسم المستخدم" in message


def test_sign_up_rejects_duplicate_email(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setattr(auth, "fetch_one", lambda q, p=(): {"id": "1"})
    ok, message = auth.sign_up(email="a@b.com", password="secret123", username="yassen")
    assert ok is False
    assert "مسجّل" in message


def test_sign_in_invalid_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setattr(auth, "fetch_one", lambda q, p=(): None)
    ok, message = auth.sign_in(email="a@b.com", password="secret123")
    assert ok is False
    assert "غير صحيحة" in message


def test_new_graph_thread_id_format():
    thread = auth._new_graph_thread_id("user-1")
    assert thread.startswith("user-1:")


def test_database_configured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from core.db.database import database_configured

    assert database_configured() is False
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
    assert database_configured() is True
