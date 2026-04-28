from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


REMOTEOK_URL = "https://remoteok.com/api"


def fetch_remoteok_jobs(limit: int = 30) -> list[dict[str, Any]]:
    """
    Fetch job listings from RemoteOK public API.
    Returns an empty list on network or response errors.
    """
    # نبني الطلب مع headers بسيطة لتقليل رفض السيرفر للطلب.
    req = Request(
        REMOTEOK_URL,
        headers={
            "User-Agent": "job-hunter-agent/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    # تحويل صيغة RemoteOK إلى الصيغة القياسية داخل المشروع.
    jobs: list[dict[str, Any]] = []
    if not isinstance(data, list):
        return jobs

    # First item is API metadata in RemoteOK.
    for row in data[1:]:
        if not isinstance(row, dict):
            continue
        jobs.append(
            {
                "id": row.get("id") or row.get("url"),
                "source": "remoteok",
                "title": row.get("position") or row.get("title") or "",
                "company": row.get("company") or "",
                "location": row.get("location") or "Remote",
                "country": row.get("location") or "",
                "job_type": "Remote",
                "salary": row.get("salary") or "",
                "remote": True,
                "apply_url": row.get("url") or "",
                "description": row.get("description") or "",
            }
        )
        if len(jobs) >= limit:
            break
    return jobs
