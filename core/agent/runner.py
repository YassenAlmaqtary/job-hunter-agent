"""
Shared Job Hunter graph runner for UI and evaluation scripts.

EN: Single entry point to build state, attach tracing config, and execute the graph.
AR: نقطة تشغيل موحّدة للواجهة وسكربتات التقييم.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from core.agent.graph import create_job_hunter_graph
from core.agent.state import JobHunterState
from core.llm.providers import build_chat_llm
from core.observability.tracing import build_graph_run_config


def build_initial_state(
    *,
    cv_text: str,
    job_title: str,
    location: str,
    min_salary: str = "",
    experience_level: str = "1–3 سنوات",
    skills: str = "",
    target_country: str = "",
    job_type: str = "Any",
    expected_salary: str = "",
    remote_preference: str = "Any",
    human_feedback: str = "",
) -> JobHunterState:
    """EN: Default graph inputs from user form or eval dataset."""
    return {
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


def state_from_eval_inputs(inputs: dict[str, Any]) -> JobHunterState:
    """EN: Map dataset row to graph state (missing keys use safe defaults)."""
    return build_initial_state(
        cv_text=str(inputs.get("user_cv_text", "")),
        job_title=str(inputs.get("job_title", "")),
        location=str(inputs.get("location", "")),
        min_salary=str(inputs.get("min_salary", "")),
        experience_level=str(inputs.get("experience_level", "1–3 سنوات")),
        skills=str(inputs.get("skills", "")),
        target_country=str(inputs.get("target_country", "")),
        job_type=str(inputs.get("job_type", "Any")),
        expected_salary=str(inputs.get("expected_salary", "")),
        remote_preference=str(inputs.get("remote_preference", "Any")),
        human_feedback=str(inputs.get("human_feedback", "")),
    )


def run_job_hunter_graph(
    *,
    provider_id: str,
    model_name: str,
    cv_text: str,
    job_title: str,
    location: str,
    min_salary: str = "",
    experience_level: str = "1–3 سنوات",
    skills: str = "",
    target_country: str = "",
    job_type: str = "Any",
    expected_salary: str = "",
    remote_preference: str = "Any",
    human_feedback: str = "",
    thread_id: str | None = None,
    temperature: float = 0.2,
    on_progress: Callable[[str], None] | None = None,
    run_tags: list[str] | None = None,
) -> JobHunterState:
    """EN: Execute full pipeline once; streams when supported."""
    tags = list(run_tags or [])
    if "streamlit" in tags:
        from core.auth.service import assert_streamlit_agent_allowed

        assert_streamlit_agent_allowed()

    llm = build_chat_llm(provider_id, model=model_name or None, temperature=temperature)
    graph = create_job_hunter_graph(llm)

    initial = build_initial_state(
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
    )

    resolved_thread = thread_id or str(uuid.uuid4())
    config = build_graph_run_config(
        thread_id=resolved_thread,
        provider_id=provider_id,
        model_name=model_name,
        job_title=job_title,
        cv_text_length=len(cv_text),
        extra_tags=run_tags,
    )

    final_state: JobHunterState | None = None
    try:
        for state_value in graph.stream(initial, config=config, stream_mode="values"):
            if isinstance(state_value, dict):
                final_state = state_value
                status_msg = str(state_value.get("status") or "").strip()
                if on_progress and status_msg:
                    on_progress(status_msg)
    except Exception:
        return graph.invoke(initial, config=config)

    if final_state is None:
        return graph.invoke(initial, config=config)
    return final_state


def run_job_hunter_from_inputs(
    inputs: dict[str, Any],
    *,
    provider_id: str,
    model_name: str,
    temperature: float = 0.2,
    run_tags: list[str] | None = None,
) -> dict[str, Any]:
    """EN: Eval-friendly wrapper: dataset inputs dict → graph outputs dict."""
    state = state_from_eval_inputs(inputs)
    result = run_job_hunter_graph(
        provider_id=provider_id,
        model_name=model_name,
        cv_text=state.get("user_cv_text", ""),
        job_title=state.get("job_title", ""),
        location=state.get("location", ""),
        min_salary=state.get("min_salary", ""),
        experience_level=state.get("experience_level", "1–3 سنوات"),
        skills=state.get("skills", ""),
        target_country=state.get("target_country", ""),
        job_type=state.get("job_type", "Any"),
        expected_salary=state.get("expected_salary", ""),
        remote_preference=state.get("remote_preference", "Any"),
        human_feedback=state.get("human_feedback", ""),
        temperature=temperature,
        run_tags=run_tags,
    )
    return dict(result)
