from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"


def fetch_arbeitnow_jobs(limit: int = 30) -> list[dict[str, Any]]:
    """Fetch jobs from Arbeitnow public API."""
    # هذا المصدر مفيد كرافد إضافي خصوصاً للوظائف الدولية.
    req = Request(
        ARBEITNOW_URL,
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

    rows = data.get("data", []) if isinstance(data, dict) else []
    # map الحقول إلى schema القياسية للمشروع.
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "id": row.get("slug") or row.get("url"),
                "source": "arbeitnow",
                "title": row.get("title") or "",
                "company": row.get("company_name") or "",
                "location": row.get("location") or "",
                "country": row.get("location") or "",
                "job_type": "Remote" if row.get("remote", False) else "Full-time",
                "salary": "",
                "remote": bool(row.get("remote", False)),
                "apply_url": row.get("url") or "",
                "description": row.get("description") or "",
            }
        )
        if len(out) >= limit:
            break
    return out
