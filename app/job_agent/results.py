"""Render Job Hunter graph results in Streamlit."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.auth import reset_graph_thread
from core.agent.state import JobHunterState


def render_results(result: JobHunterState | dict[str, Any]) -> None:
    if result.get("status"):
        st.info(result["status"])

    top_jobs = result.get("top_jobs", [])
    if top_jobs:
        st.subheader("أفضل الفرص المطابقة")
        for idx, job in enumerate(top_jobs, start=1):
            st.markdown(
                f"**#{idx} {job.get('title','')}** — {job.get('company','')} | "
                f"{job.get('location','')} | نسبة المطابقة: {job.get('match_score', 0)}%"
            )
            if job.get("apply_url"):
                st.markdown(f"[رابط التقديم]({job.get('apply_url')})")
            if job.get("match_explanation"):
                st.caption(f"سبب المطابقة: {job.get('match_explanation')}")
            st.divider()
    else:
        st.warning(
            "لم يتم العثور على فرص مطابقة من المصادر الحقيقية الحالية. "
            "جرّب تغيير المسمى أو الدولة."
        )

    tab_cv, tab_cl, tab_pack, tab_alert = st.tabs(
        ["السيرة المحسّنة", "خطاب التقديم", "حزم التقديم", "التنبيهات اليومية"]
    )
    with tab_cv:
        st.text_area(
            "السيرة المحسّنة",
            value=result.get("optimized_cv", ""),
            height=420,
            label_visibility="collapsed",
        )
    with tab_cl:
        st.text_area(
            "خطاب التقديم",
            value=result.get("cover_letter", ""),
            height=420,
            label_visibility="collapsed",
        )
    with tab_pack:
        apps = result.get("generated_applications", [])
        if not apps:
            st.info("لا توجد حزم توليد بعد.")
        for app in apps:
            job = app.get("job", {})
            st.markdown(
                f"**{job.get('title','فرصة')}** — {job.get('company','')} "
                f"(نسبة المطابقة: {job.get('match_score', 0)}%)"
            )
            if job.get("apply_url"):
                st.markdown(f"[التقديم على الوظيفة]({job.get('apply_url')})")
            if app.get("why_fit"):
                st.caption(f"سبب المطابقة: {app.get('why_fit')}")
            st.text_area(
                f"سيرة مخصصة — #{app.get('rank', '')}",
                value=app.get("optimized_cv", ""),
                height=180,
            )
            st.text_area(
                f"خطاب تقديم — #{app.get('rank', '')}",
                value=app.get("cover_letter", ""),
                height=180,
            )
            st.divider()
    with tab_alert:
        alerts = result.get("alert_items", [])
        if not alerts:
            st.info("لا توجد تنبيهات جديدة اليوم.")
        for item in alerts:
            st.markdown(
                f"- **{item.get('title','')}** — {item.get('company','')} "
                f"({item.get('location','')}) | نسبة المطابقة: {item.get('match_score', 0)}%"
            )
            if item.get("apply_url"):
                st.markdown(f"  - [رابط التقديم]({item.get('apply_url')})")

    d1, d2, d3 = st.columns([1, 1, 2])
    with d1:
        st.download_button(
            label="تحميل السيرة (TXT)",
            data=result.get("optimized_cv", ""),
            file_name="optimized_cv.txt",
            mime="text/plain",
        )
    with d2:
        st.download_button(
            label="تحميل الخطاب (TXT)",
            data=result.get("cover_letter", ""),
            file_name="cover_letter.txt",
            mime="text/plain",
        )
    with d3:
        if st.button("بدء بحث جديد", help="مسح النتائج الحالية وبدء بحث جديد"):
            reset_graph_thread()
            st.rerun()
