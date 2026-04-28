from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


def fetch_serpapi_google_jobs(
    *,
    api_key: str,
    job_title: str,
    location: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """
    Fetch jobs using SerpAPI Google Jobs engine.
    This may include listings from LinkedIn / Indeed / Glassdoor and others.
    """
    if not api_key.strip():
        return []

    # query مبني مباشرة من مدخلات المستخدم.
    query = " ".join(x for x in [job_title.strip(), location.strip()] if x).strip()
    if not query:
        return []

    url = (
        "https://serpapi.com/search.json"
        f"?engine=google_jobs&q={quote_plus(query)}"
        f"&api_key={quote_plus(api_key.strip())}"
    )
    req = Request(
        url,
        headers={
            "User-Agent": "job-hunter-agent/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    rows = payload.get("jobs_results", []) if isinstance(payload, dict) else []
    # تحويل نتائج Google Jobs إلى الصيغة الداخلية الموحّدة.
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        sources = row.get("related_links") or row.get("job_highlights") or []
        source_name = str(row.get("via") or "google_jobs").strip()
        if source_name:
            source_name = source_name.lower().replace(" ", "_")

        apply_url = ""
        if isinstance(row.get("apply_options"), list):
            for opt in row["apply_options"]:
                if isinstance(opt, dict) and opt.get("link"):
                    apply_url = str(opt["link"])
                    break
        if not apply_url:
            share_link = row.get("share_link")
            if share_link:
                apply_url = str(share_link)

        out.append(
            {
                "id": row.get("job_id") or apply_url or row.get("title"),
                "source": source_name or "google_jobs",
                "title": row.get("title") or "",
                "company": row.get("company_name") or "",
                "location": row.get("location") or "",
                "country": row.get("location") or "",
                "job_type": str((row.get("detected_extensions") or {}).get("schedule_type") or ""),
                "salary": str((row.get("detected_extensions") or {}).get("salary") or ""),
                "remote": "remote" in str(row.get("location") or "").lower(),
                "apply_url": apply_url,
                "description": str(row.get("description") or ""),
                "raw_sources": sources,
            }
        )
        if len(out) >= limit:
            break

    return out
