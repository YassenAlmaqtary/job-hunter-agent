from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


def fetch_remotive_jobs(query: str, limit: int = 30) -> list[dict[str, Any]]:
    """Fetch jobs from Remotive public API."""
    # query يأتي من المسمى الذي حدده المستخدم.
    url = f"https://remotive.com/api/remote-jobs?search={quote_plus(query or '')}"
    req = Request(
        url,
        headers={
            "User-Agent": "job-hunter-agent/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    rows = data.get("jobs", []) if isinstance(data, dict) else []
    # تحويل الاستجابة إلى schema المشروع.
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "id": row.get("id") or row.get("url"),
                "source": "remotive",
                "title": row.get("title") or "",
                "company": row.get("company_name") or "",
                "location": row.get("candidate_required_location") or "Remote",
                "country": row.get("candidate_required_location") or "",
                "job_type": row.get("job_type") or "Remote",
                "salary": row.get("salary") or "",
                "remote": True,
                "apply_url": row.get("url") or row.get("apply_url") or "",
                "description": row.get("description") or "",
            }
        )
        if len(out) >= limit:
            break
    return out
