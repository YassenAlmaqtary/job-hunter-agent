from __future__ import annotations

from typing import Any


def normalize_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize listing fields into the project schema."""
    # أي مصدر جديد يجب أن يمر من هنا لضمان تناسق الحقول.
    return {
        "id": str(raw.get("id") or raw.get("url") or raw.get("title") or ""),
        "source": str(raw.get("source") or "unknown"),
        "title": str(raw.get("title") or "").strip(),
        "company": str(raw.get("company") or "").strip(),
        "location": str(raw.get("location") or "").strip(),
        "country": str(raw.get("country") or "").strip(),
        "job_type": str(raw.get("job_type") or "").strip(),
        "salary": str(raw.get("salary") or "").strip(),
        "remote": bool(raw.get("remote", False)),
        "apply_url": str(raw.get("apply_url") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
    }


def listing_key(item: dict[str, Any]) -> str:
    """Build a deduplication key for listings."""
    # الأفضلية لـ apply_url لأنه غالبًا معرف فريد للفرصة.
    title = str(item.get("title") or "").strip().lower()
    company = str(item.get("company") or "").strip().lower()
    location = str(item.get("location") or "").strip().lower()
    apply_url = str(item.get("apply_url") or "").strip().lower()
    if apply_url:
        return apply_url
    return f"{title}|{company}|{location}"
