"""
LangSmith evaluators for Job Hunter graph outputs.

EN: Code-based scorers (no extra LLM cost). Used by scripts/evaluate_models.py.
AR: مقيّمات جودة السيرة والخطاب واكتمال الـ pipeline.
"""

from __future__ import annotations

from typing import Any

from langsmith.schemas import Example, Run

_MIN_CV_CHARS = 200
_MIN_COVER_LETTER_CHARS = 120
_CV_SECTION_HINTS = (
    "experience",#الخبرة العملية
    "خبرة",
    "skills",#المهارات
    "مهارات",
    "education",#التعليم
    "تعليم",
    "summary",#الملخص
    "ملخص",
)


def _outputs_dict(run: Run) -> dict[str, Any]:
    raw = run.outputs or {}
    return raw if isinstance(raw, dict) else {}


def _inputs_dict(example: Example | None) -> dict[str, Any]:
    if example is None:
        return {}
    raw = example.inputs or {}
    return raw if isinstance(raw, dict) else {}


def _score_result(*, key: str, score: float, comment: str) -> dict[str, Any]:
    return {"key": key, "score": max(0.0, min(1.0, score)), "comment": comment}


def cv_quality_evaluator(run: Run, example: Example) -> dict[str, Any]:
    """EN: Checks optimized CV length and basic structure."""
    outputs = _outputs_dict(run)
    cv_text = str(outputs.get("optimized_cv", "")).strip()
    if not cv_text:
        return _score_result(key="cv_quality", score=0.0, comment="optimized_cv فارغ.")

    length_score = min(1.0, len(cv_text) / _MIN_CV_CHARS)
    lowered = cv_text.lower()
    section_hits = sum(1 for hint in _CV_SECTION_HINTS if hint in lowered)
    structure_score = min(1.0, section_hits / 2.0)
    score = (length_score * 0.6) + (structure_score * 0.4)
    return _score_result(
        key="cv_quality",
        score=score,
        comment=f"طول السيرة {len(cv_text)} حرف؛ أقسام مكتشفة: {section_hits}.",
    )


def cover_letter_evaluator(run: Run, example: Example) -> dict[str, Any]:
    """EN: Checks cover letter length and relevance to target job title."""
    outputs = _outputs_dict(run)
    inputs = _inputs_dict(example)
    letter = str(outputs.get("cover_letter", "")).strip()
    job_title = str(inputs.get("job_title", "")).strip()

    if not letter:
        return _score_result(key="cover_letter_quality", score=0.0, comment="cover_letter فارغ.")

    length_score = min(1.0, len(letter) / _MIN_COVER_LETTER_CHARS)
    relevance_score = 1.0
    if job_title:
        title_tokens = [t for t in job_title.lower().split() if len(t) > 2]
        if title_tokens:
            hits = sum(1 for token in title_tokens if token in letter.lower())
            relevance_score = hits / len(title_tokens)

    score = (length_score * 0.5) + (relevance_score * 0.5)
    return _score_result(
        key="cover_letter_quality",
        score=score,
        comment=f"طول الخطاب {len(letter)} حرف؛ ملاءمة المسمى: {relevance_score:.0%}.",
    )


def pipeline_completeness_evaluator(run: Run, example: Example) -> dict[str, Any]:
    """EN: Ensures key pipeline artifacts exist."""
    del example
    outputs = _outputs_dict(run)
    checks = {
        "optimized_cv": bool(str(outputs.get("optimized_cv", "")).strip()),
        "cover_letter": bool(str(outputs.get("cover_letter", "")).strip()),
        "top_jobs": bool(outputs.get("top_jobs")),
        "generated_applications": bool(outputs.get("generated_applications")),
        "alert_items_present": "alert_items" in outputs,
    }
    passed = sum(1 for ok in checks.values() if ok)
    score = passed / len(checks)
    missing = [name for name, ok in checks.items() if not ok]
    comment = "اكتمل الـ pipeline." if not missing else f"ناقص: {', '.join(missing)}"
    return _score_result(key="pipeline_completeness", score=score, comment=comment)


DEFAULT_EVALUATORS = [
    cv_quality_evaluator,
    cover_letter_evaluator,
    pipeline_completeness_evaluator,
]
