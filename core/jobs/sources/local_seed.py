from __future__ import annotations

from typing import Any


def local_seed_jobs() -> list[dict[str, Any]]:
    """
    Seed fallback jobs when external sources are unavailable.
    These are generic templates to keep the agent useful offline.
    """
    return [
        {
            "id": "seed-laravel-001",
            "source": "local_seed",
            "title": "Laravel Backend Developer",
            "company": "Gulf Tech Solutions",
            "location": "Riyadh",
            "country": "Saudi Arabia",
            "job_type": "Full-time",
            "salary": "15000-22000 SAR",
            "remote": False,
            "apply_url": "https://example.com/jobs/laravel-backend",
            "description": "Build Laravel APIs, optimize SQL, and ship scalable backend services.",
        },
        {
            "id": "seed-ai-001",
            "source": "local_seed",
            "title": "AI Engineer (Python/FastAPI)",
            "company": "Desert AI Labs",
            "location": "Dubai",
            "country": "UAE",
            "job_type": "Hybrid",
            "salary": "22000-32000 AED",
            "remote": True,
            "apply_url": "https://example.com/jobs/ai-engineer",
            "description": "Develop ML-enabled services with Python, FastAPI, and production MLOps practices.",
        },
        {
            "id": "seed-frontend-001",
            "source": "local_seed",
            "title": "Frontend Engineer (React)",
            "company": "Qatar Digital Ventures",
            "location": "Doha",
            "country": "Qatar",
            "job_type": "Full-time",
            "salary": "16000-24000 QAR",
            "remote": False,
            "apply_url": "https://example.com/jobs/frontend-react",
            "description": "Build modern React interfaces, collaborate with backend teams, and improve UX quality.",
        },
    ]
