"""
LangSmith tracing helpers for LangGraph runs.

EN: Centralizes run config (metadata/tags) so Streamlit and eval scripts log
    comparable traces without duplicating env checks.
AR: إعداد موحّد للتتبع عبر LangSmith مع metadata للمزود والنموذج.
"""

from __future__ import annotations

import os
from typing import Any


def _env_truthy(key: str) -> bool:
    return os.getenv(key, "").strip().lower() in {"1", "true", "yes", "on"}


def ensure_tracing_env() -> None:
    """
    EN: Align legacy LANGCHAIN_* vars with LANGSMITH_* so tracing actually sends.
    AR: LangChain يقرأ LANGCHAIN_TRACING_V2 أولاً؛ إن كان false يُعطّل التتبع حتى لو LANGSMITH_TRACING=true.
    """
    smith_on = _env_truthy("LANGSMITH_TRACING") or _env_truthy("LANGSMITH_TRACING_V2")
    chain_on = _env_truthy("LANGCHAIN_TRACING_V2") or _env_truthy("LANGCHAIN_TRACING")

    if smith_on and not chain_on:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"

    api_key = os.getenv("LANGSMITH_API_KEY", "").strip() or os.getenv("LANGCHAIN_API_KEY", "").strip()
    if api_key:
        if not os.getenv("LANGSMITH_API_KEY", "").strip():
            os.environ["LANGSMITH_API_KEY"] = api_key
        if not os.getenv("LANGCHAIN_API_KEY", "").strip():
            os.environ["LANGCHAIN_API_KEY"] = api_key

    project = os.getenv("LANGSMITH_PROJECT", "").strip().strip('"').strip("'")
    if project:
        os.environ["LANGSMITH_PROJECT"] = project
        if not os.getenv("LANGCHAIN_PROJECT", "").strip():
            os.environ["LANGCHAIN_PROJECT"] = project


def tracing_enabled() -> bool:
    """EN: True when LangSmith / legacy LangChain tracing is on."""
    ensure_tracing_env()
    for key in ("LANGSMITH_TRACING_V2", "LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"):
        if _env_truthy(key):
            return True
    return False


def tracing_api_key_configured() -> bool:
    ensure_tracing_env()
    return bool(
        os.getenv("LANGSMITH_API_KEY", "").strip()
        or os.getenv("LANGCHAIN_API_KEY", "").strip()
    )


def tracing_project() -> str:
    ensure_tracing_env()
    return (
        os.getenv("LANGSMITH_PROJECT", "").strip().strip('"').strip("'")
        or os.getenv("LANGCHAIN_PROJECT", "").strip()
        or "job-hunter-agent"
    )


def tracing_status_message() -> str:
    """EN: Human-readable status for Streamlit sidebar."""
    ensure_tracing_env()
    if not tracing_enabled():
        return "LangSmith: غير مفعّل — اضبط LANGSMITH_TRACING=true في `.env`"
    if not tracing_api_key_configured():
        return "LangSmith: مفعّل لكن بدون API key — أضف LANGSMITH_API_KEY"
    return f"LangSmith: مفعّل — مشروع `{tracing_project()}`"

def build_graph_run_config(
    *,
    thread_id: str,
    provider_id: str = "",
    model_name: str = "",
    job_title: str = "",
    cv_text_length: int = 0,
    run_name: str = "job_hunter_graph",
    extra_metadata: dict[str, Any] | None = None,
    extra_tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    EN: RunnableConfig for graph.invoke/stream with LangSmith metadata.
    AR: يُمرَّر لـ invoke/stream لتسجيل المزود والنموذج دون إرسال نص السيرة كاملاً.
    """
    metadata: dict[str, Any] = {
        "provider": provider_id,
        "model": model_name,
        "job_title": job_title,
        "cv_text_length": cv_text_length,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    tags = ["job-hunter", "langgraph"]
    if provider_id:
        tags.append(f"provider:{provider_id}")
    if model_name:
        tags.append(f"model:{model_name}")
    if extra_tags:
        tags.extend(extra_tags)

    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "metadata": metadata,
        "tags": tags,
        "run_name": run_name,
    }
    if tracing_enabled():
        config["metadata"]["langsmith_project"] = tracing_project()
    return config
