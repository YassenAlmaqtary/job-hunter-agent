from __future__ import annotations

from typing import Any


def _tokenize(text: str) -> set[str]:
    # tokenization بسيطة لتقدير التطابق بدون اعتماد NLP ثقيل.
    return {t.strip().lower() for t in text.replace("/", " ").replace(",", " ").split() if t.strip()}


def score_job_match(
    *,
    cv_text: str,
    skills_text: str,
    job: dict[str, Any],
    target_job_title: str,
    expected_salary: str,
    remote_preference: str,
) -> tuple[float, str]:
    """Simple deterministic scorer for job matching."""
    haystack = f"{cv_text}\n{skills_text}".lower()
    job_text = f"{job.get('title','')} {job.get('description','')} {job.get('job_type','')}".lower()

    # 1) وزن المهارات.
    skill_tokens = _tokenize(skills_text)
    hit_count = sum(1 for token in skill_tokens if token and token in job_text)
    skill_score = min(50.0, hit_count * 8.0)

    # 2) وزن تطابق المسمى الوظيفي المطلوب.
    target_title = target_job_title.lower().strip()
    job_title = str(job.get("title", "")).lower().strip()
    title_bonus = 0.0
    if target_title and job_title:
        target_tokens = [t for t in target_title.split() if t]
        overlap = sum(1 for t in target_tokens if t in job_title)
        if overlap:
            title_bonus = min(25.0, 10.0 + overlap * 6.0)
        else:
            title_bonus = -25.0
    else:
        title_bonus = 5.0
    # 3) وزن تفضيل remote / onsite.
    remote_bonus = 0.0
    is_remote = bool(job.get("remote", False))
    pref = remote_preference.lower().strip()
    if pref == "remote only":
        remote_bonus = 15.0 if is_remote else -10.0
    elif pref == "onsite only":
        remote_bonus = 10.0 if not is_remote else -8.0
    elif pref in ("hybrid preferred", "remote preferred"):
        remote_bonus = 8.0 if is_remote else 2.0
    else:
        remote_bonus = 3.0

    # 4) وزن بسيط لوجود معلومة راتب.
    salary_bonus = 0.0
    if expected_salary and str(job.get("salary") or "").strip():
        salary_bonus = 5.0

    score = max(0.0, min(100.0, skill_score + title_bonus + remote_bonus + salary_bonus))
    reason = (
        f"skills_hits={hit_count}, title_fit={title_bonus:.1f}, "
        f"remote_fit={is_remote}, salary_info={'yes' if salary_bonus else 'no'}"
    )
    return score, reason
