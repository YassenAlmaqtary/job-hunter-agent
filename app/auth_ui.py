"""
Streamlit auth UI — login, signup, Google OAuth, sidebar, and gate.

EN: Presentation only; domain logic stays in ``core.auth.service``.
AR: واجهة المصادقة فقط؛ المنطق في ``core.auth.service``.
"""

from __future__ import annotations

import streamlit as st

from core.auth.google_oauth import (
    build_google_auth_url,
    exchange_code_for_profile,
    google_oauth_configured,
    new_oauth_state,
    verify_oauth_state,
)
from core.auth.service import (
    auth_disabled,
    auth_required,
    ensure_auth_session,
    get_display_name,
    is_authenticated,
    sign_in,
    sign_in_with_google_profile,
    sign_out,
    sign_up,
)
from core.db.database import database_configured, ensure_schema


def _query_param(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def render_auth_sidebar() -> None:
    if not auth_required() or not is_authenticated():
        return
    with st.sidebar:
        st.divider()
        st.caption(f"مسجّل: **{get_display_name()}**")
        if st.button("تسجيل الخروج", use_container_width=True, key="auth_sign_out"):
            sign_out()
            st.rerun()


def _handle_google_oauth_callback() -> bool:
    """
    Process ``?code=&state=`` from Google redirect.
    Returns True when a login was completed (caller should rerun).
    """
    code = _query_param("code")
    state = _query_param("state")
    error = _query_param("error")

    if error:
        st.query_params.clear()
        st.error(f"تعذر تسجيل الدخول عبر Google: {error}")
        return False

    if not code or not state:
        return False

    st.query_params.clear()
    if not verify_oauth_state(state):
        st.error("جلسة Google غير صالحة أو انتهت. أعد المحاولة من زر Google.")
        return False

    try:
        profile = exchange_code_for_profile(code=code)
        ok, message = sign_in_with_google_profile(
            google_sub=profile["sub"],
            email=profile["email"],
            name=profile.get("name", ""),
        )
    except Exception as exc:
        st.error(str(exc))
        return False

    if ok:
        st.success(message)
        return True
    st.error(message)
    return False


def _render_google_button() -> None:
    if not google_oauth_configured():
        st.caption("تسجيل Google غير مفعّل — أضف مفاتيح OAuth في `.env`.")
        return

    try:
        auth_url = build_google_auth_url(state=new_oauth_state())
    except Exception as exc:
        st.warning(str(exc))
        return

    st.link_button(
        "تسجيل الدخول عبر Google",
        auth_url,
        use_container_width=True,
        type="secondary",
    )


def render_login_page() -> None:
    st.title("تسجيل الدخول")
    st.caption("سجّل دخولك للوصول إلى وكيل البحث عن الوظائف")

    _render_google_button()
    st.divider()

    tab_login, tab_signup = st.tabs(["تسجيل الدخول", "إنشاء حساب"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("البريد الإلكتروني", placeholder="you@example.com")
            password = st.text_input("كلمة المرور", type="password")
            submit = st.form_submit_button("دخول", type="primary", use_container_width=True)
        if submit:
            ok, message = sign_in(email=email, password=password)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with tab_signup:
        with st.form("signup_form"):
            username = st.text_input("اسم المستخدم", placeholder="مثال: yassen")
            new_email = st.text_input(
                "البريد الإلكتروني", placeholder="you@example.com", key="signup_email"
            )
            new_password = st.text_input("كلمة المرور", type="password", key="signup_password")
            confirm = st.text_input("تأكيد كلمة المرور", type="password")
            create = st.form_submit_button("إنشاء حساب", type="primary", use_container_width=True)
        if create:
            if new_password != confirm:
                st.error("كلمتا المرور غير متطابقتين.")
            else:
                ok, message = sign_up(email=new_email, password=new_password, username=username)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def render_auth_gate() -> bool:
    """Return True when the user may enter the app; otherwise stop rendering."""
    if auth_disabled():
        return True

    if not database_configured():
        st.error("قاعدة البيانات غير مضبوطة.")
        st.markdown(
            """
أضف إلى ملف `.env`:

```
DATABASE_URL=postgresql://jobhunter:jobhunter_secret@localhost:5432/jobhunter
```

ثم شغّل PostgreSQL:

```bash
docker compose up -d postgres
```
            """
        )
        st.stop()
        return False

    try:
        ensure_schema()
    except Exception as exc:
        st.error(f"تعذر الاتصال بقاعدة البيانات: {exc}")
        st.stop()
        return False

    # Handle Google redirect before the normal session check.
    if _handle_google_oauth_callback():
        st.rerun()

    ensure_auth_session()
    if is_authenticated():
        render_auth_sidebar()
        return True

    render_login_page()
    st.stop()
    return False
