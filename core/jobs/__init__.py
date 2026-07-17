"""Job domain: listing sources, match scoring, and daily alerts."""

from core.jobs.alerts import build_daily_alert_items
from core.jobs.matching import score_job_match
from core.jobs.sources import aggregate_job_listings

__all__ = [
    "aggregate_job_listings",
    "build_daily_alert_items",
    "score_job_match",
]
