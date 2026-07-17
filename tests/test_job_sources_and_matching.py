from core.jobs.matching import score_job_match
from core.jobs.sources.aggregator import aggregate_job_listings


def test_aggregate_job_listings_returns_normalized_items(monkeypatch):
    monkeypatch.setattr(
        "core.jobs.sources.aggregator.fetch_remoteok_jobs",
        lambda limit=30: [
            {
                "id": "1",
                "source": "remoteok",
                "title": "AI Engineer",
                "company": "ACME",
                "location": "Remote",
                "country": "Remote",
                "job_type": "Remote",
                "salary": "",
                "remote": True,
                "apply_url": "https://example.com/job/1",
                "description": "Python FastAPI",
            }
        ],
    )
    monkeypatch.setattr(
        "core.jobs.sources.aggregator.fetch_remotive_jobs", lambda query, limit=30: []
    )
    monkeypatch.setattr("core.jobs.sources.aggregator.fetch_arbeitnow_jobs", lambda limit=30: [])
    monkeypatch.setattr(
        "core.jobs.sources.aggregator.fetch_serpapi_google_jobs", lambda **kwargs: []
    )
    jobs = aggregate_job_listings(
        job_title="AI Engineer",
        target_country="",
        job_type="Any",
        remote_preference="Any",
        skills_text="Python, FastAPI, SQL",
        cv_text="AI engineer with machine learning and backend skills",
        limit=10,
    )
    assert isinstance(jobs, list)
    assert jobs
    sample = jobs[0]
    assert "title" in sample
    assert "company" in sample
    assert "apply_url" in sample


def test_score_job_match_range():
    score, reason = score_job_match(
        cv_text="Python FastAPI SQL machine learning",
        skills_text="Python, FastAPI, SQL",
        job={
            "title": "AI Engineer",
            "description": "Build FastAPI and ML services with Python.",
            "job_type": "Remote",
            "remote": True,
            "salary": "20000 SAR",
        },
        target_job_title="AI Engineer",
        expected_salary="18000 SAR",
        remote_preference="Remote preferred",
    )
    assert 0 <= score <= 100
    assert "skills_hits" in reason
    assert "title_fit" in reason
