"""Fetch and normalize job listings from multiple sources."""

from core.jobs.sources.aggregator import aggregate_job_listings

__all__ = ["aggregate_job_listings"]
