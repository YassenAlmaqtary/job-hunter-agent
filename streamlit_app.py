"""
Streamlit entrypoint — multipage navigation router.

EN: Auth gate first, then st.navigation to app pages.
AR: بوابة المصادقة ثم التنقل بين الصفحات.
"""

from __future__ import annotations

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

from app.auth_ui import render_auth_gate
from core.observability import ensure_tracing_env

ensure_tracing_env()

st.set_page_config(
    page_title="وكيل البحث عن الوظائف",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not render_auth_gate():
    st.stop()

page = st.navigation(
    [
        st.Page("app/pages/job_agent_page.py", title="وكيل البحث عن الوظائف", icon="🎯", default=True),
        st.Page("app/pages/feedback_page.py", title="آراء حول الفكرة", icon="💬"),
    ]
)
page.run()
