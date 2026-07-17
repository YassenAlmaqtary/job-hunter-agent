from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


SNAPSHOT_PATH = Path(".data/alerts_snapshot.json")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_alert_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    # snapshot يحفظ ids التي تم التنبيه عليها سابقًا.
    if not path.exists():
        return {"date": "", "seen_ids": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"date": "", "seen_ids": []}


def save_alert_snapshot(snapshot: dict[str, Any], path: Path = SNAPSHOT_PATH) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def build_daily_alert_items(top_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # أي وظيفة موجودة مسبقًا في seen_ids لن تُرسل مرة أخرى.
    snapshot = load_alert_snapshot()
    seen = {str(x) for x in snapshot.get("seen_ids", [])}
    items: list[dict[str, Any]] = []
    new_seen = set(seen)
    for job in top_jobs:
        job_id = str(job.get("id") or job.get("apply_url") or "")
        if not job_id or job_id in seen:
            continue
        items.append(
            {
                "id": job_id,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "apply_url": job.get("apply_url", ""),
                "match_score": job.get("match_score", 0),
            }
        )
        new_seen.add(job_id)

    save_alert_snapshot({"date": str(date.today()), "seen_ids": sorted(new_seen)})
    return items
