from core import alerts


def test_daily_alert_items_only_new(monkeypatch):
    monkeypatch.setattr(alerts, "load_alert_snapshot", lambda: {"date": "", "seen_ids": ["a1"]})
    saved = {}

    def _save(snapshot):
        saved.update(snapshot)

    monkeypatch.setattr(alerts, "save_alert_snapshot", _save)
    top_jobs = [
        {"id": "a1", "title": "Seen Job", "company": "X", "location": "Riyadh", "apply_url": "u1"},
        {"id": "a2", "title": "New Job", "company": "Y", "location": "Dubai", "apply_url": "u2"},
    ]
    items = alerts.build_daily_alert_items(top_jobs)
    assert len(items) == 1
    assert items[0]["id"] == "a2"
    assert "a2" in saved.get("seen_ids", [])
