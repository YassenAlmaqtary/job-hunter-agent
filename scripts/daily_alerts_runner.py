from __future__ import annotations

import argparse

from core.alerts import build_daily_alert_items
from core.job_sources import aggregate_job_listings
from core.matching import score_job_match


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily alerts runner")
    parser.add_argument("--job-title", required=True)
    parser.add_argument("--country", default="")
    parser.add_argument("--job-type", default="Any")
    parser.add_argument("--remote", default="Any")
    parser.add_argument("--skills", default="")
    parser.add_argument("--cv-text", default="")
    parser.add_argument("--expected-salary", default="")
    args = parser.parse_args()

    listings = aggregate_job_listings(
        job_title=args.job_title,
        target_country=args.country,
        job_type=args.job_type,
        remote_preference=args.remote,
        limit=30,
    )
    scored = []
    for item in listings:
        score, reason = score_job_match(
            cv_text=args.cv_text,
            skills_text=args.skills,
            job=item,
            expected_salary=args.expected_salary,
            remote_preference=args.remote,
        )
        enriched = dict(item)
        enriched["match_score"] = score
        enriched["match_explanation"] = reason
        scored.append(enriched)
    scored.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    top_jobs = scored[:5]
    alerts = build_daily_alert_items(top_jobs)
    print(f"alerts_created={len(alerts)}")
    for item in alerts:
        print(f"- {item['title']} | {item['company']} | {item['apply_url']}")


if __name__ == "__main__":
    main()
