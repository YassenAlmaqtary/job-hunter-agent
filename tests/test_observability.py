from __future__ import annotations

from types import SimpleNamespace

from core.observability.evaluators import (
    cover_letter_evaluator,
    cv_quality_evaluator,
    pipeline_completeness_evaluator,
)
from core.observability import build_graph_run_config, tracing_enabled, tracing_status_message


def test_build_graph_run_config_includes_metadata():
    config = build_graph_run_config(
        thread_id="t-1",
        provider_id="gemini",
        model_name="gemini-3-flash-preview",
        job_title="Backend Developer",
        cv_text_length=1200,
        extra_tags=["eval"],
    )
    assert config["configurable"]["thread_id"] == "t-1"
    assert config["metadata"]["provider"] == "gemini"
    assert config["metadata"]["model"] == "gemini-3-flash-preview"
    assert config["metadata"]["cv_text_length"] == 1200
    assert "provider:gemini" in config["tags"]
    assert "eval" in config["tags"]


def test_cv_quality_evaluator_scores_structured_cv():
    run = SimpleNamespace(
        outputs={
            "optimized_cv": (
                "Summary\nExperienced engineer.\n"
                "Skills: Python, FastAPI.\n"
                "Experience: 4 years backend.\n"
                "Education: BSc CS."
            )
        }
    )
    example = SimpleNamespace(inputs={"job_title": "Backend Developer"})
    result = cv_quality_evaluator(run, example)
    assert result["key"] == "cv_quality"
    assert result["score"] >= 0.65


def test_cover_letter_evaluator_checks_job_title_relevance():
    run = SimpleNamespace(outputs={"cover_letter": "I am applying for the Backend Developer role in Riyadh."})
    example = SimpleNamespace(inputs={"job_title": "Backend Developer"})
    result = cover_letter_evaluator(run, example)
    assert result["key"] == "cover_letter_quality"
    assert result["score"] >= 0.5


def test_pipeline_completeness_evaluator():
    run = SimpleNamespace(
        outputs={
            "optimized_cv": "CV text",
            "cover_letter": "Letter text",
            "top_jobs": [{"title": "Dev"}],
            "generated_applications": [{"rank": 1}],
            "alert_items": [],
        }
    )
    example = SimpleNamespace(inputs={})
    result = pipeline_completeness_evaluator(run, example)
    assert result["score"] == 1.0


def test_tracing_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    assert tracing_enabled() is False
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    assert tracing_enabled() is True


def test_tracing_status_message_when_key_missing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    msg = tracing_status_message()
    assert "API key" in msg
