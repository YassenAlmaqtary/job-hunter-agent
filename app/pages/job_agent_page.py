"""
صفحة وكيل البحث عن الوظائف.

EN: Thin Streamlit page — sidebar LLM controls, form, run, render results.
AR: صفحة رفيعة؛ المنطق الثقيل في ``core.agent`` والمساعدات في ``app.job_agent``.
"""

from __future__ import annotations

import os
from typing import Callable

import streamlit as st
from dotenv import load_dotenv

from app.job_agent.cv_io import extract_cv_text
from app.job_agent.errors import format_runtime_error
from app.job_agent.results import render_results
from core.agent.runner import run_job_hunter_graph
from core.agent.state import JobHunterState
from core.auth import (
    get_current_user_id,
    get_graph_thread_id,
    record_agent_run,
    require_authenticated_for_agent,
)
from core.llm.providers import LLM_PROVIDERS, get_provider, provider_key_configured
from core.observability import tracing_status_message

load_dotenv()
require_authenticated_for_agent()


def _run_graph(
    *,
    provider_id: str,
    model_name: str,
    temperature: float,
    cv_text: str,
    job_title: str,
    location: str,
    min_salary: str,
    experience_level: str,
    skills: str,
    target_country: str,
    job_type: str,
    expected_salary: str,
    remote_preference: str,
    human_feedback: str,
    thread_id: str,
    on_progress: Callable[[str], None] | None = None,
) -> JobHunterState:
    return run_job_hunter_graph(
        provider_id=provider_id,
        model_name=model_name,
        temperature=temperature,
        cv_text=cv_text,
        job_title=job_title,
        location=location,
        min_salary=min_salary,
        experience_level=experience_level,
        skills=skills,
        target_country=target_country,
        job_type=job_type,
        expected_salary=expected_salary,
        remote_preference=remote_preference,
        human_feedback=human_feedback,
        thread_id=thread_id,
        on_progress=on_progress,
        run_tags=["streamlit"],
    )


st.title("وكيل البحث عن الوظائف")
st.caption("مساعد بحث عن عمل — تحسين السيرة وخطاب التقديم (سوق الخليج واليمن)")

with st.sidebar:
    st.subheader("نموذج اللغة (LLM)")
    provider_ids = list(LLM_PROVIDERS.keys())
    default_pid = os.getenv("DEFAULT_LLM_PROVIDER", "gemini").strip().lower()
    if default_pid not in provider_ids:
        default_pid = provider_ids[0]
    p_index = provider_ids.index(default_pid)

    provider_id = st.selectbox(
        "المزود",
        options=provider_ids,
        index=p_index,
        format_func=lambda x: get_provider(x).label_ar,
        help="OpenAI (ChatGPT) · Google Gemini · xAI Grok · Groq",
    )
    spec = get_provider(provider_id)
    ok_key, _used_env = provider_key_configured(spec)
    if ok_key:
        st.success("الخدمة جاهزة للتشغيل")
    else:
        st.warning("خدمة هذا المزود غير متاحة حاليًا. يرجى المحاولة لاحقًا أو اختيار مزود آخر.")

    mode = st.radio(
        "اختيار النموذج",
        options=["من القائمة", "يدوي (معرّف كامل)"],
        horizontal=True,
        help="يمكنك لصق أي معرّف مدعوم من وثائق المزود.",
    )
    if mode == "من القائمة":
        choices = list(dict.fromkeys([spec.default_model, *spec.suggested_models]))
        model_name = st.selectbox("النموذج", options=choices, index=0)
    else:
        model_name = st.text_input(
            "معرّف النموذج",
            value=spec.default_model,
            help="مثال: gemini-3-flash-preview · llama-3.1-8b-instant",
        )

    temperature = st.slider(
        "درجة الإبداع (temperature)",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.05,
        help="0 = أكثر حرفية؛ 1 = أكثر تنوعاً.",
    )

    st.caption(tracing_status_message())

    st.divider()
    st.subheader("رفع السيرة الذاتية")
    uploaded = st.file_uploader(
        "PDF أو TXT",
        type=["pdf", "txt"],
        help="يُستخرج النص محليًا ولا يُشارك مع خوادم خارجية إلا عند تشغيل الوكيل.",
    )

    cv_text_local = ""
    if uploaded is not None:
        try:
            cv_text_local = extract_cv_text(uploaded)
            st.success(f"تمت قراءة الملف ({len(cv_text_local):,} حرف).")
        except Exception as e:
            st.error(f"تعذر قراءة الملف: {e}")

cv_text = cv_text_local

with st.form("job_hunter_form"):
    st.subheader("بيانات الوظيفة المستهدفة")
    c1, c2, c3 = st.columns(3)
    with c1:
        job_title = st.text_input("المسمى الوظيفي", placeholder="مثال: مهندس برمجيات أول")
        location = st.text_input("الموقع", placeholder="الرياض، دبي، عن بُعد…")
    with c2:
        min_salary = st.text_input("الحد الأدنى للراتب (اختياري)", placeholder="مثال: 20000 ريال")
        experience_level = st.selectbox(
            "مستوى الخبرة",
            options=["بدون خبرة", "1–3 سنوات", "3–5 سنوات", "5+ سنوات"],
            index=1,
        )
    with c3:
        target_country = st.text_input("الدولة المستهدفة", placeholder="Saudi Arabia / UAE ...")
        job_type = st.selectbox(
            "نوع الوظيفة",
            options=["Any", "Full-time", "Part-time", "Contract", "Internship", "Hybrid", "Remote"],
            index=0,
        )

    c4, c5 = st.columns(2)
    with c4:
        expected_salary = st.text_input("الراتب المتوقع", placeholder="مثال: 18000 SAR")
        remote_preference = st.selectbox(
            "تفضيل العمل",
            options=["Any", "Remote preferred", "Remote only", "Onsite only", "Hybrid preferred"],
            index=0,
        )
    with c5:
        skills = st.text_area(
            "المهارات",
            placeholder="Python, FastAPI, SQL, Laravel, React ...",
            height=95,
        )

    with st.expander("ملاحظات إضافية (اختياري)"):
        human_feedback = st.text_area(
            "ملاحظات للمراجعة قبل/بعد التوليد",
            placeholder="مثال: أبرز خبرة القطاع الحكومي، وتجنب ذكر راتب صريح في الخطاب.",
            height=100,
        )
    run = st.form_submit_button(
        "تشغيل الوكيل",
        type="primary",
        use_container_width=True,
        disabled=not get_current_user_id(),
    )

thread_id = get_graph_thread_id()
if thread_id:
    st.session_state["graph_thread_id"] = thread_id

if run:
    if not get_current_user_id():
        st.error("يجب تسجيل الدخول لتشغيل الوكيل.")
    elif not provider_key_configured(spec)[0]:
        st.warning("خدمة المزود المختار غير متاحة حاليًا. يرجى اختيار مزود آخر أو المحاولة لاحقًا.")
    elif not cv_text.strip():
        st.warning("يرجى رفع ملف سيرة ذاتية صالح (PDF أو TXT).")
    elif not job_title.strip() or not location.strip():
        st.warning("يرجى إدخال المسمى الوظيفي والموقع.")
    elif not skills.strip():
        st.warning("يرجى إدخال المهارات لرفع دقة المطابقة.")
    else:
        progress_widget = st.status("بدء تنفيذ الوكيل...", expanded=True)
        seen_progress: set[str] = set()

        def _progress_update(message: str) -> None:
            msg = message.strip()
            if not msg or msg in seen_progress:
                return
            seen_progress.add(msg)
            progress_widget.write(f"- {msg}")

        try:
            with st.spinner(
                f"جاري التشغيل عبر {spec.label_ar} / {model_name.strip() or spec.default_model}…"
            ):
                result = _run_graph(
                    provider_id=provider_id,
                    model_name=model_name.strip(),
                    temperature=float(temperature),
                    cv_text=cv_text.strip(),
                    job_title=job_title.strip(),
                    location=location.strip(),
                    min_salary=min_salary.strip(),
                    experience_level=experience_level,
                    skills=skills.strip(),
                    target_country=target_country.strip(),
                    job_type=job_type,
                    expected_salary=expected_salary.strip(),
                    remote_preference=remote_preference,
                    human_feedback=human_feedback.strip(),
                    thread_id=st.session_state.get("graph_thread_id") or get_graph_thread_id() or "",
                    on_progress=_progress_update,
                )
        except Exception as e:
            progress_widget.update(label="فشل التنفيذ", state="error", expanded=True)
            if isinstance(e, PermissionError):
                st.error(str(e))
            else:
                st.error(format_runtime_error(e, provider_id))
        else:
            record_agent_run(job_title=job_title.strip(), status="completed")
            progress_widget.update(label="اكتمل التنفيذ بنجاح", state="complete", expanded=False)
            st.success("اكتمل التشغيل بنجاح.")
            render_results(result)
