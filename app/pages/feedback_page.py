"""
صفحة آراء حول الفكرة — جمع ملاحظات الزوار.

EN: Streamlit page for idea feedback; data via ``core.feedback``.
AR: شارك الرابط مع الآخرين لقراءة آرائهم حول المشروع.
"""

from __future__ import annotations

import streamlit as st

from core.auth import get_display_name
from core.feedback import (
    SENTIMENT_LABELS_AR,
    add_comment,
    comment_counts,
    format_created_at,
    load_comments,
)

st.title("💬 آراء حول الفكرة")
st.caption(
    "شارك رأيك في Job Hunter Agent — مساعد ذكي لبحث الوظائف وتحسين السيرة وخطاب التقديم"
)

st.markdown(
    """
**ما هي الفكرة؟**

وكيل ذكي يبحث عن فرص عمل حقيقية (مصادر متعددة)، يطابقها مع سيرتك ومهاراتك،
ثم يولّد سيرة محسّنة وخطاب تقديم مخصص لسوق الخليج — مع دعم عدة مزودي LLM.

**ما الذي نبحث عنه منك؟**
- هل الفكرة مفيدة لك شخصياً؟
- ما الذي ينقصها أو يزعجك؟
- ما الميزة التي تتمنى رؤيتها أولاً؟
"""
)

comments = load_comments()
counts = comment_counts(comments)
total = len(comments)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("إجمالي التعليقات", total)
with m2:
    st.metric("مؤيد", counts.get("positive", 0))
with m3:
    st.metric("محايد", counts.get("neutral", 0))
with m4:
    st.metric("غير مؤيد", counts.get("negative", 0))

st.divider()

logged_in_name = get_display_name()
with st.form("feedback_form", clear_on_submit=True):
    st.subheader("أضف تعليقك")
    c1, c2 = st.columns([1, 2])
    with c1:
        if logged_in_name:
            st.text_input("الاسم", value=logged_in_name, disabled=True)
            author = logged_in_name
        else:
            author = st.text_input("الاسم (اختياري)", placeholder="مثال: أحمد")
        sentiment = st.radio(
            "موقفك من الفكرة",
            options=["positive", "neutral", "negative"],
            format_func=lambda x: SENTIMENT_LABELS_AR[x],
            horizontal=True,
        )
    with c2:
        body = st.text_area(
            "تعليقك",
            placeholder="مثال: الفكرة ممتازة، لكن أتمنى دعم اللغة العربية بالكامل في الخطاب…",
            height=140,
        )
    submit = st.form_submit_button("نشر التعليق", type="primary", use_container_width=True)

if submit:
    try:
        add_comment(author=author, comment=body, sentiment=sentiment)
        st.success("شكراً! تم نشر تعليقك.")
        st.rerun()
    except ValueError as e:
        st.warning(str(e))

st.divider()
st.subheader("التعليقات")

if not comments:
    st.info("لا توجد تعليقات بعد — كن أول من يشارك رأيه.")
else:
    for item in comments:
        label = SENTIMENT_LABELS_AR.get(item.get("sentiment", "neutral"), "محايد")
        author_name = item.get("author") or "مجهول"
        when = format_created_at(item.get("created_at", ""))
        st.markdown(f"**{author_name}** · {label} · {when}")
        st.write(item.get("comment", ""))
        st.divider()
