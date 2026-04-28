from core.graph import create_job_hunter_graph


class DummyLLM:
    pass


def test_graph_flow_with_patched_generation(monkeypatch):
    def fake_cv(state, llm):  # noqa: ARG001
        apps = [{"rank": 1, "job": {"apply_url": "https://example.com"}, "optimized_cv": "CV"}]
        return {"optimized_cv": "CV", "generated_applications": apps, "status": "ok"}

    def fake_cl(state, llm):  # noqa: ARG001
        apps = state.get("generated_applications", [])
        for app in apps:
            app["cover_letter"] = "CL"
        return {"cover_letter": "CL", "generated_applications": apps, "application_links": ["https://example.com"]}

    monkeypatch.setattr("core.graph.cv_optimizer_node", fake_cv)
    monkeypatch.setattr("core.graph.cover_letter_node", fake_cl)

    graph = create_job_hunter_graph(DummyLLM())
    result = graph.invoke(
        {
            "user_cv_text": "Python developer",
            "job_title": "Backend Developer",
            "location": "Riyadh",
            "min_salary": "15000",
            "experience_level": "1–3 سنوات",
            "skills": "Python, FastAPI",
            "target_country": "Saudi Arabia",
            "job_type": "Any",
            "expected_salary": "18000",
            "remote_preference": "Any",
            "job_listings": [],
            "messages": [],
            "human_feedback": "",
            "status": "init",
        },
        config={"configurable": {"thread_id": "test-thread"}},
    )
    assert "top_jobs" in result
    assert "generated_applications" in result
    assert "alert_items" in result
