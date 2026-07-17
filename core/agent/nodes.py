"""
LangGraph node implementations — pure functions (state in, partial state out).

EN: Each node accepts `JobHunterState` + `llm` and returns a dict merged into state.
    Structured outputs use Pydantic for robust parsing (extend fields anytime).
AR: كل عقدة دالة نقية: (حالة، نموذج لغوي) → تحديث جزئي للحالة.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from pydantic import BaseModel, Field

from core.agent.prompts import build_cover_letter_prompt, build_cv_optimizer_prompt
from core.agent.state import JobHunterState
from core.jobs.alerts import build_daily_alert_items
from core.jobs.matching import score_job_match
from core.jobs.sources import aggregate_job_listings


# ---------------------------------------------------------------------------
# Structured outputs (EN: extend these models as the product grows)
# ---------------------------------------------------------------------------


class CVOptimizerOutput(BaseModel):
    """EN: Parsed CV optimization; AR: مخرجات تحسين السيرة."""

    optimized_cv: str = Field(
        ...,
        description="السيرة الذاتية المحسّنة كاملة، جاهزة للنسخ.",
    )


class CoverLetterOutput(BaseModel):
    """EN: Parsed cover letter; AR: مخرجات خطاب التقديم."""

    cover_letter: str = Field(
        ...,
        description="نص خطاب التقديم كاملاً.",
    )


def _invoke_text_fallback(chain: Any, payload: dict[str, Any]) -> str:
    """
    EN: Fallback when structured/tool-calling fails on some providers/models.
    AR: مسار احتياطي عند فشل الـ structured output في بعض المزودات.
    """
    msgs = chain.invoke(payload)
    content = getattr(msgs, "content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text")
                if txt:
                    parts.append(str(txt))
            elif isinstance(item, str):
                parts.append(item)
        content = "\n".join(parts).strip()
    return str(content or "").strip()


def cv_optimizer_node(state: JobHunterState, llm: BaseChatModel) -> dict[str, Any]:
    """
    EN: Rewrites CV for ATS + Gulf market using structured output.
    AR: يعيد صياغة السيرة بتوافق ATS وسوق الخليج.
    """
    prompt = build_cv_optimizer_prompt()
    # نولّد مستندات لعدد محدود من أفضل الفرص لتقليل التكلفة والزمن.
    top_jobs = state.get("top_jobs") or state.get("matched_jobs") or state.get("job_listings") or []
    generated_applications: list[dict[str, Any]] = []
    for idx, job in enumerate(top_jobs[:3], start=1):
        payload = {
            "user_cv_text": state.get("user_cv_text", ""),
            "job_title": job.get("title") or state.get("job_title", ""),
            "location": job.get("location") or state.get("location", ""),
            "min_salary": state.get("min_salary", "غير محدد"),
            "experience_level": state.get("experience_level", "غير محدد"),
            "skills": state.get("skills", ""),
            "job_type": state.get("job_type", ""),
            "remote_preference": state.get("remote_preference", "Any"),
            "job_description": job.get("description", ""),
        }
        optimized_cv = ""
        try:
            structured = llm.with_structured_output(CVOptimizerOutput)
            structured_chain = prompt | structured
            result: CVOptimizerOutput = structured_chain.invoke(payload)
            optimized_cv = (result.optimized_cv or "").strip()
        except Exception:
            # Some models (e.g. specific Groq models) may fail tool/function calls.
            text_chain = prompt | llm
            optimized_cv = _invoke_text_fallback(text_chain, payload)
        generated_applications.append(
            {
                "rank": idx,
                "job": job,
                "optimized_cv": optimized_cv,
            }
        )

    # نحفظ نسخة "أفضل CV" للتبويب السريع في الواجهة.
    best_cv = generated_applications[0]["optimized_cv"] if generated_applications else ""

    return {
        "optimized_cv": best_cv,
        "generated_applications": generated_applications,
        "status": "تم تحسين السيرة الذاتية لأفضل الفرص.",
        "messages": [
            AIMessage(
                content="[cv_optimizer] اكتمل تحسين السيرة الذاتية.",
                name="cv_optimizer",
            )
        ],
    }


def cover_letter_node(state: JobHunterState, llm: BaseChatModel) -> dict[str, Any]:
    """
    EN: Writes a personalized cover letter from optimized CV + job context.
    AR: يكتب خطاب تقديم مبني على السيرة المحسّنة وسياق الوظيفة.
    """
    prompt = build_cover_letter_prompt()
    feedback = (state.get("human_feedback") or "").strip()
    human_feedback_section = (
        "**ملاحظات المراجع / المستخدم (Human-in-the-loop):**\n" + feedback
        if feedback
        else "**ملاحظات المراجع:** لا توجد — تابع بالمعطيات أعلاه فقط."
    )
    # نكمل نفس الحزم التي بدأت في مرحلة تحسين الـCV.
    generated_applications = list(state.get("generated_applications") or [])
    for app in generated_applications:
        job = app.get("job", {})
        payload = {
            "optimized_cv": app.get("optimized_cv", state.get("optimized_cv", "")),
            "job_title": job.get("title") or state.get("job_title", ""),
            "location": job.get("location") or state.get("location", ""),
            "min_salary": state.get("min_salary", "غير محدد"),
            "experience_level": state.get("experience_level", "غير محدد"),
            "job_type": job.get("job_type") or state.get("job_type", ""),
            "skills": state.get("skills", ""),
            "apply_url": job.get("apply_url", ""),
            "job_description": job.get("description", ""),
            "human_feedback_section": human_feedback_section,
        }
        cover_letter = ""
        try:
            structured = llm.with_structured_output(CoverLetterOutput)
            structured_chain = prompt | structured
            result: CoverLetterOutput = structured_chain.invoke(payload)
            cover_letter = (result.cover_letter or "").strip()
        except Exception:
            text_chain = prompt | llm
            cover_letter = _invoke_text_fallback(text_chain, payload)
        app["cover_letter"] = cover_letter
        app["why_fit"] = job.get("match_explanation", "")

    top_cover = generated_applications[0].get("cover_letter", "") if generated_applications else ""
    links = [
        str(app.get("job", {}).get("apply_url", "")).strip()
        for app in generated_applications
        if str(app.get("job", {}).get("apply_url", "")).strip()
    ]

    return {
        "cover_letter": top_cover,
        "generated_applications": generated_applications,
        "application_links": links,
        "status": "تم إعداد خطابات التقديم لأفضل الفرص.",
        "messages": [
            AIMessage(
                content="[cover_letter] اكتمل خطاب التقديم.",
                name="cover_letter",
            )
        ],
    }


def job_search_node(state: JobHunterState, llm: BaseChatModel) -> dict[str, Any]:
    # هذه عقدة deterministic: لا تعتمد على LLM.
    del llm
    listings = aggregate_job_listings(
        job_title=state.get("job_title", ""),
        target_country=state.get("target_country", ""),
        job_type=state.get("job_type", ""),
        remote_preference=state.get("remote_preference", "Any"),
        skills_text=state.get("skills", ""),
        cv_text=state.get("user_cv_text", ""),
        limit=50,
    )
    return {
        "job_listings": listings,
        "status": f"تم جمع {len(listings)} فرصة مبدئية.",
        "messages": [AIMessage(content="[job_search] اكتمل جمع الوظائف.", name="job_search")],
    }


def job_match_node(state: JobHunterState, llm: BaseChatModel) -> dict[str, Any]:
    # مطابقة حسابية بسيطة (بدون LLM) لتقليل التكلفة ورفع الثبات.
    del llm
    listings = state.get("job_listings") or []
    scored: list[dict[str, Any]] = []
    for item in listings:
        score, reason = score_job_match(
            cv_text=state.get("user_cv_text", ""),
            skills_text=state.get("skills", ""),
            job=item,
            target_job_title=state.get("job_title", ""),
            expected_salary=state.get("expected_salary", ""),
            remote_preference=state.get("remote_preference", "Any"),
        )
        enriched = dict(item)
        enriched["match_score"] = round(score, 2)
        enriched["match_explanation"] = reason
        scored.append(enriched)

    scored.sort(key=lambda x: float(x.get("match_score", 0.0)), reverse=True)
    top_jobs = scored[:3]
    overall_score = float(top_jobs[0].get("match_score", 0.0)) if top_jobs else 0.0
    overall_reason = top_jobs[0].get("match_explanation", "") if top_jobs else "لا توجد فرص كافية."
    return {
        "matched_jobs": scored,
        "top_jobs": top_jobs,
        "match_score": overall_score,
        "match_explanation": overall_reason,
        "status": f"تم تقييم {len(scored)} فرصة وترتيب أفضل 3.",
        "messages": [AIMessage(content="[job_match] اكتملت المطابقة والترتيب.", name="job_match")],
    }


def daily_alert_node(state: JobHunterState, llm: BaseChatModel) -> dict[str, Any]:
    # تجهيز تنبيهات يومية للوظائف الجديدة غير المرسلة سابقًا.
    del llm
    items = build_daily_alert_items(state.get("top_jobs") or [])
    status = "لا توجد فرص جديدة للتنبيه اليوم."
    if items:
        status = f"تم تجهيز {len(items)} تنبيه يومي جديد."
    return {
        "alert_items": items,
        "status": status,
        "messages": [AIMessage(content="[daily_alert] اكتمل تجهيز التنبيهات.", name="daily_alert")],
    }
