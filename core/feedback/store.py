"""
تخزين تعليقات آراء المستخدمين حول فكرة المشروع / Persisted idea feedback comments.

EN: JSON file store under `.data/` (gitignored). Used by the Streamlit feedback page.
AR: ملف محلي بسيط — مناسب للتجربة والمشاركة دون قاعدة بيانات.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict


class FeedbackComment(TypedDict):
    id: str
    author: str
    comment: str
    sentiment: str
    created_at: str


DEFAULT_DATA_DIR = Path(".data")
FEEDBACK_FILENAME = "idea_comments.json"

VALID_SENTIMENTS = frozenset({"positive", "neutral", "negative"})

SENTIMENT_LABELS_AR: dict[str, str] = {
    "positive": "مؤيد",
    "neutral": "محايد",
    "negative": "غير مؤيد",
}


def feedback_file_path(data_dir: Path | None = None) -> Path:
    root = data_dir or Path(os.getenv("FEEDBACK_DATA_DIR", DEFAULT_DATA_DIR))
    return root / FEEDBACK_FILENAME


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_comments(*, data_dir: Path | None = None) -> list[FeedbackComment]:
    path = feedback_file_path(data_dir)
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return [c for c in data if isinstance(c, dict) and c.get("comment")]


def save_comments(comments: list[FeedbackComment], *, data_dir: Path | None = None) -> None:
    path = feedback_file_path(data_dir)
    _ensure_parent(path)
    path.write_text(
        json.dumps(comments, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_comment(
    *,
    author: str,
    comment: str,
    sentiment: str = "neutral",
    data_dir: Path | None = None,
) -> FeedbackComment:
    author_clean = (author or "").strip() or "مجهول"
    comment_clean = (comment or "").strip()
    if not comment_clean:
        raise ValueError("نص التعليق مطلوب.")
    sentiment_clean = (sentiment or "neutral").strip().lower()
    if sentiment_clean not in VALID_SENTIMENTS:
        raise ValueError(f"تصنيف غير صالح: {sentiment!r}")

    entry: FeedbackComment = {
        "id": str(uuid.uuid4()),
        "author": author_clean,
        "comment": comment_clean,
        "sentiment": sentiment_clean,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    comments = load_comments(data_dir=data_dir)
    comments.insert(0, entry)
    save_comments(comments, data_dir=data_dir)
    return entry


def comment_counts(comments: list[FeedbackComment]) -> dict[str, int]:
    counts: dict[str, int] = {k: 0 for k in VALID_SENTIMENTS}
    for c in comments:
        s = c.get("sentiment", "neutral")
        if s in counts:
            counts[s] += 1
    return counts


def format_created_at(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return iso or ""
