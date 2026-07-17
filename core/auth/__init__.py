"""Auth service — signup, signin, sessions, agent-run recording."""

from core.auth import service as _service
from core.auth.service import (  # noqa: F401 — re-export for `from core import auth`
    assert_streamlit_agent_allowed,
    auth_disabled,
    auth_required,
    ensure_auth_session,
    get_current_user,
    get_current_user_id,
    get_display_name,
    get_graph_thread_id,
    get_session_id,
    is_authenticated,
    record_agent_run,
    require_authenticated_for_agent,
    reset_graph_thread,
    sign_in,
    sign_out,
    sign_up,
)

# Tests monkeypatch these on `core.auth`; expose the same names used by service.
fetch_one = _service.fetch_one
_hash_password = _service._hash_password
_verify_password = _service._verify_password
_new_graph_thread_id = _service._new_graph_thread_id

__all__ = [
    "assert_streamlit_agent_allowed",
    "auth_disabled",
    "auth_required",
    "ensure_auth_session",
    "fetch_one",
    "get_current_user",
    "get_current_user_id",
    "get_display_name",
    "get_graph_thread_id",
    "get_session_id",
    "is_authenticated",
    "record_agent_run",
    "require_authenticated_for_agent",
    "reset_graph_thread",
    "sign_in",
    "sign_out",
    "sign_up",
]
