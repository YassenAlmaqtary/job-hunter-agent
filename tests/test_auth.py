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
    ok, message = auth.sign_up(email="a@b.com", password="secret123", username="")
    assert ok is False
    assert "اسم المستخدم" in message


def test_sign_up_rejects_duplicate_email(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")

    class _FakeScalarResult:
        def __init__(self, value):
            self._value = value

    class _FakeSession:
        def scalar(self, stmt):  # noqa: ARG002
            return object()  # truthy → email already exists

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(auth, "session_scope", lambda: _FakeSession())
    ok, message = auth.sign_up(email="a@b.com", password="secret123", username="yassen")
    assert ok is False
    assert "مسجّل" in message


def test_sign_in_invalid_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")

    class _FakeSession:
        def scalar(self, stmt):  # noqa: ARG002
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(auth, "session_scope", lambda: _FakeSession())
    ok, message = auth.sign_in(email="a@b.com", password="secret123")
    assert ok is False
    assert "غير صحيحة" in message


def test_new_graph_thread_id_format():
    thread = auth._new_graph_thread_id("user-1")
    assert thread.startswith("user-1:")


def test_database_configured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from core.db.database import database_configured, database_url, reset_engine_for_tests

    reset_engine_for_tests()
    assert database_configured() is False
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
    assert database_configured() is True
    assert database_url().startswith("postgresql+psycopg://")


def test_username_from_google():
    assert auth._username_from_google(email="ali@gmail.com", name="Ali Hassan").startswith("Ali")
    assert len(auth._username_from_google(email="ab@x.com", name="")) >= 3


def test_sign_in_with_google_profile_creates_user(monkeypatch):
    import uuid as uuid_mod

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    created = {}

    class _FakeSession:
        def scalar(self, stmt):  # noqa: ARG002
            return None

        def add(self, obj):
            if getattr(obj, "id", None) is None:
                obj.id = uuid_mod.UUID("11111111-1111-1111-1111-111111111111")
            created["email"] = obj.email
            created["google_sub"] = obj.google_sub
            created["password_hash"] = obj.password_hash
            created["username"] = obj.username

        def flush(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(auth, "session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        auth,
        "_create_db_session",
        lambda *, user_id: (
            "tok",
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "graph_thread_id": f"{user_id}:t",
                "expires_at": None,
            },
        ),
    )
    monkeypatch.setattr(auth, "_store_browser_session", lambda **kwargs: None)

    ok, message = auth.sign_in_with_google_profile(
        google_sub="google-sub-1",
        email="ali@gmail.com",
        name="Ali",
    )
    assert ok is True
    assert "Google" in message
    assert created["email"] == "ali@gmail.com"
    assert created["google_sub"] == "google-sub-1"
    assert created["password_hash"] is None


def test_google_oauth_configured(monkeypatch):
    from core.auth import google_oauth

    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_REDIRECT_URI", raising=False)
    assert google_oauth.google_oauth_configured() is False

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/")
    assert google_oauth.google_oauth_configured() is True
    url = google_oauth.build_google_auth_url(state="abc")
    assert "accounts.google.com" in url
    assert "client_id=cid" in url


def test_oauth_state_roundtrip(monkeypatch):
    from core.auth import google_oauth

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    state = google_oauth.new_oauth_state()
    assert google_oauth.verify_oauth_state(state) is True
    assert google_oauth.verify_oauth_state("bad.state") is False
    assert google_oauth.verify_oauth_state(state + "x") is False
