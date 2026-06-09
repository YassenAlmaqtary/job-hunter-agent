"""
Streamlit entrypoint — multipage navigation router.

EN: `page_title` in child pages does not set the sidebar label; use `st.Page(title=...)`.
AR: اسم الصفحة في الشريط الجانبي يُحدَّد هنا عبر st.navigation.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="وكيل البحث عن الوظائف",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

page = st.navigation(
    [
        st.Page("pages/jop_agent_page.py", title="وكيل البحث عن الوظائف", icon="🎯", default=True),
        st.Page("pages/feed_back_page.py", title="آراء حول الفكرة", icon="💬"),
    ]
)
page.run()
