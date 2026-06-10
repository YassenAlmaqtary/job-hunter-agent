"""
Streamlit UI for Job Hunter Agent — wired to LangGraph `core` package.

EN: Loads secrets from `.env`, supports multiple LLM providers, runs graph.
AR: دعم عدة مزودين (OpenAI / Gemini / Grok) مع اختيار مرن للنموذج.
"""

from __future__ import annotations

import io
import os
import re
import uuid
from typing import Any, Callable

import streamlit as st
from dotenv import load_dotenv

from core.graph import create_job_hunter_graph
from core.llm_providers import (
    LLM_PROVIDERS,
    build_chat_llm,
    get_provider,
    provider_key_configured,
)
from core.state import JobHunterState

load_dotenv()


def _extract_cv_text(uploaded: Any) -> str:
    """EN: Read TXT or PDF bytes into plain text. AR: استخراج النص من الملف."""
    name = (uploaded.name or "").lower()
    raw = uploaded.getvalue()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError("تثبيت pypdf مطلوب لقراءة PDF: pip install pypdf") from e
        reader = PdfReader(io.BytesIO(raw))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    return raw.decode("utf-8", errors="ignore").strip()


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
    """EN: Single invoke with MemorySaver thread. AR: تشغيلة واحدة مع معرف جلسة."""
    # نبني النموذج حسب المزود المختار ثم نشغّل graph كامل.
    llm = build_chat_llm(provider_id, model=model_name or None, temperature=temperature)
    graph = create_job_hunter_graph(llm)

    initial: JobHunterState = {
        # state الابتدائية تعتمد بالكامل على مدخلات المستخدم.
        "user_cv_text": cv_text,
        "job_title": job_title,
        "location": location,
        "min_salary": min_salary,
        "experience_level": experience_level,
        "skills": skills,
        "target_country": target_country,
        "job_type": job_type,
        "expected_salary": expected_salary,
        "remote_preference": remote_preference,
        "job_listings": [],
        "matched_jobs": [],
        "top_jobs": [],
        "messages": [],
        "human_feedback": human_feedback,
        "status": "جاري التنفيذ…",
    }

    config = {"configurable": {"thread_id": thread_id}}
    # thread_id يضمن استمرارية الحالة داخل الجلسة.
    final_state: JobHunterState | None = None
    try:
        # stream_mode="values" يعطي الحالة بعد كل عقدة، فنقدر نعرض progress حي.
        for state_value in graph.stream(initial, config=config, stream_mode="values"):
            if isinstance(state_value, dict):
                final_state = state_value
                status_msg = str(state_value.get("status") or "").strip()
                if on_progress and status_msg:
                    on_progress(status_msg)
    except Exception:
        # fallback آمن إذا لم يدعم المزود/البيئة stream.
        return graph.invoke(initial, config=config)

    if final_state is None:
        return graph.invoke(initial, config=config)
    return final_state


def _format_runtime_error(exc: Exception, provider_id: str) -> str:
    """
    EN: Convert raw provider errors into concise actionable Arabic guidance.
    AR: تحويل أخطاء المزود الطويلة إلى رسالة عملية وواضحة.
    """
    raw = str(exc or "").strip()
    low = raw.lower()

    # Gemini / Google quota and rate-limit cases
    if (
        "resource_exhausted" in low
        or "quota exceeded" in low
        or "you exceeded your current quota" in low
        or "429" in low
    ):
        wait_hint = ""
        delay_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", low)
        if delay_match:
            try:
                secs = int(float(delay_match.group(1)))
                wait_hint = f"\n- أعد المحاولة بعد حوالي {secs} ثانية."
            except ValueError:
                wait_hint = "\n- أعد المحاولة بعد دقيقة تقريبًا."

        if provider_id == "gemini":
            return (
                "تعذر التشغيل عبر Gemini بسبب تجاوز الحصة (Quota 429).\n"
                "- تحقق أن مشروع Google AI لديه حصة فعالة وفوترة مفعلة.\n"
                "- راجع الاستهلاك والحدود من لوحة Google AI Studio."
                f"{wait_hint}\n"
                "- كحل سريع: بدّل المزود إلى OpenAI أو Grok إن كان المفتاح متاحًا."
            )

        return (
            "تعذر التشغيل بسبب تجاوز الحصة/الحد الأقصى للطلبات (429).\n"
            "- انتظر قليلًا ثم أعد المحاولة.\n"
            "- تحقق من الفوترة وحدود الاستخدام لدى المزود.\n"
            "- أو بدّل إلى مزود آخر مؤقتًا."
        )

    if "api key" in low or "غير مضبوط" in low or "not set" in low:
        # Explicit auth failures (key exists but invalid/revoked/wrong project).
        if (
            "invalid_api_key" in low
            or "invalid api key" in low
            or "authenticationerror" in low
            or "401" in low
            or "unauthorized" in low
        ):
            provider_name = {
                "gemini": "Gemini",
                "groq": "Groq",
                "grok": "xAI Grok",
                "openai": "OpenAI",
            }.get(provider_id, "المزوّد")
            return (
                f"تعذر التشغيل عبر {provider_name}: الخدمة غير متاحة حاليًا.\n"
                "- جرّب مزودًا آخر من القائمة.\n"
                "- أو أعد المحاولة لاحقًا."
            )

        return (
            "تعذر التشغيل بسبب مشكلة في إعدادات الخدمة.\n"
            "- جرّب مزودًا آخر من القائمة.\n"
            "- أو أعد المحاولة لاحقًا."
        )

    return f"فشل التشغيل: {raw}"


# --- Streamlit layout -------------------------------------------------------

st.title("وكيل البحث عن الوظائف")
st.caption("مساعد بحث عن عمل — تحسين السيرة وخطاب التقديم (سوق الخليج واليمن)")

# --- Sidebar: LLM provider + secrets + upload -------------------------------

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
            help="مثال OpenAI: gpt-4o-mini — Gemini: gemini-3-flash-preview — Grok: grok-2-latest — Groq: llama-3.1-8b-instant",
        )

    temperature = st.slider(
        "درجة الإبداع (temperature)",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.05,
        help="0 = أكثر حرفية؛ 1 = أكثر تنوعاً.",
    )

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
            cv_text_local = _extract_cv_text(uploaded)
            st.success(f"تمت قراءة الملف ({len(cv_text_local):,} حرف).")
        except Exception as e:
            st.error(f"تعذر قراءة الملف: {e}")
    else:
        cv_text_local = ""

cv_text = cv_text_local

# --- Main form -------------------------------------------------------------

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
    run = st.form_submit_button("تشغيل الوكيل", type="primary", use_container_width=True)

# Session thread for MemorySaver continuity (multi-step / HITL later)
if "graph_thread_id" not in st.session_state:
    st.session_state["graph_thread_id"] = str(uuid.uuid4())

if run:
    if not provider_key_configured(spec)[0]:
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
                # نقطة التشغيل المركزية لكل خط المعالجة.
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
                    thread_id=st.session_state["graph_thread_id"],
                    on_progress=_progress_update,
                )
        except Exception as e:
            progress_widget.update(label="فشل التنفيذ", state="error", expanded=True)
            st.error(_format_runtime_error(e, provider_id))
        else:
            progress_widget.update(label="اكتمل التنفيذ بنجاح", state="complete", expanded=False)
            st.success("اكتمل التشغيل بنجاح.")
            if result.get("status"):
                st.info(result["status"])

            # عرض أفضل الفرص بعد المطابقة.
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
                st.warning("لم يتم العثور على فرص مطابقة من المصادر الحقيقية الحالية. جرّب تغيير المسمى أو الدولة.")

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
                    st.session_state["graph_thread_id"] = str(uuid.uuid4())
                    st.rerun()
