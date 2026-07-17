from __future__ import annotations

import os
from typing import Any

from core.jobs.sources.arbeitnow import fetch_arbeitnow_jobs
from core.jobs.sources.local_seed import local_seed_jobs
from core.jobs.sources.remotive import fetch_remotive_jobs
from core.jobs.sources.remoteok import fetch_remoteok_jobs
from core.jobs.sources.schemas import listing_key, normalize_listing
from core.jobs.sources.serpapi_jobs import fetch_serpapi_google_jobs


# هذا الملف هو نقطة الدمج المركزية لكل مصادر الوظائف.
# الهدف: إنتاج قائمة وظائف موحّدة وقابلة للتصفية حسب مدخلات المستخدم.

def _extract_dynamic_keywords(
    *,
    job_title_hint: str,
    skills_text: str,
    cv_text: str,
) -> list[str]:
    """
    Build dynamic keywords only from user inputs (no static dictionaries).
    """
    raw = f"{job_title_hint} {skills_text}".strip().lower()
    base_tokens = [t.strip(".,;:()[]{}!?'\"") for t in raw.replace("/", " ").split() if t.strip()]

    # Also harvest longer tokens from CV, but keep only meaningful words.
    cv_tokens = [
        t.strip(".,;:()[]{}!?'\"")
        for t in cv_text.lower().replace("/", " ").split()
        if len(t.strip()) >= 4
    ]
    candidates = base_tokens + cv_tokens[:80]
    stop = {
        "and",
        "the",
        "for",
        "with",
        "from",
        "الى",
        "في",
        "على",
        "من",
        "عن",
        "وظيفة",
        "job",
    }
    seen: set[str] = set()
    out: list[str] = []
    for tok in candidates:
        tok = tok.strip()
        if len(tok) < 3 or tok in stop or tok.isdigit():
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out[:40]


def _matches_preferences(
    item: dict[str, Any],
    *,
    target_country: str,
    job_type: str,
    remote_preference: str,
    user_keywords: list[str],
) -> bool:
    title = str(item.get("title") or "").lower()
    location = str(item.get("location") or "").lower()
    country = str(item.get("country") or "").lower()
    item_job_type = str(item.get("job_type") or "").lower()
    remote = bool(item.get("remote", False))

    if target_country and target_country.lower() not in f"{location} {country}":
        return False

    if job_type and job_type.lower() not in ("any", "all"):
        if job_type.lower() not in item_job_type:
            return False

    pref = remote_preference.lower().strip()
    if pref == "remote only" and not remote:
        return False
    if pref == "onsite only" and remote:
        return False

    if user_keywords:
        job_surface = f"{title} {str(item.get('description') or '').lower()}"
        # Require at least one meaningful overlap to keep strong relevance.
        if not any(tok in job_surface for tok in user_keywords):
            return False

    return True


def aggregate_job_listings(
    *,
    job_title: str,
    target_country: str,
    job_type: str,
    remote_preference: str,
    skills_text: str = "",
    cv_text: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Collect, normalize, deduplicate, and filter job listings."""
    # نجمع البيانات الخام أولاً من كل مصدر.
    raw: list[dict[str, Any]] = []
    per_source = max(10, min(40, limit))
    raw.extend(fetch_remoteok_jobs(limit=per_source))
    raw.extend(fetch_remotive_jobs(job_title, limit=per_source))
    raw.extend(fetch_arbeitnow_jobs(limit=per_source))
    serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if serpapi_key:
        raw.extend(
            fetch_serpapi_google_jobs(
                api_key=serpapi_key,
                job_title=job_title,
                location=target_country,
                limit=per_source,
            )
        )
    # الكلمات المفتاحية تُستخرج ديناميكيًا من المسمى + المهارات + CV.
    user_keywords = _extract_dynamic_keywords(
        job_title_hint=job_title,
        skills_text=skills_text,
        cv_text=cv_text,
    )

    # Use local seed only when explicitly enabled for offline demos.
    if os.getenv("USE_SEED_JOBS", "").strip().lower() in {"1", "true", "yes"}:
        raw.extend(local_seed_jobs())

    # إزالة التكرار بعد التطبيع لأن نفس الوظيفة قد تأتي من أكثر من مصدر.
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for row in raw:
        normalized = normalize_listing(row)
        key = listing_key(normalized)
        if not key or key in seen:
            continue
        seen.add(key)
        if _matches_preferences(
            normalized,
            target_country=target_country,
            job_type=job_type,
            remote_preference=remote_preference,
            user_keywords=user_keywords,
        ):
            merged.append(normalized)

    return merged[:limit]
