"""Extract plain text from uploaded CV files (PDF / TXT)."""

from __future__ import annotations

import io
from typing import Any


def extract_cv_text(uploaded: Any) -> str:
    """Read TXT or PDF bytes into plain text."""
    name = (uploaded.name or "").lower()
    raw = uploaded.getvalue()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError("تثبيت pypdf مطلوب لقراءة PDF: pip install pypdf") from e
        reader = PdfReader(io.BytesIO(raw))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    return raw.decode("utf-8", errors="ignore").strip()
