import json
from pathlib import Path

from core.agent.runner import build_initial_state, state_from_eval_inputs


def test_build_initial_state_defaults():
    state = build_initial_state(
        cv_text="CV",
        job_title="Engineer",
        location="Riyadh",
        skills="Python",
    )
    assert state["user_cv_text"] == "CV"
    assert state["job_listings"] == []
    assert state["status"] == "جاري التنفيذ…"


def test_state_from_eval_inputs_reads_dataset_row():
    row = {
        "user_cv_text": "Ahmed",
        "job_title": "Data Engineer",
        "location": "Dubai",
        "skills": "SQL",
    }
    state = state_from_eval_inputs(row)
    assert state["job_title"] == "Data Engineer"
    assert state["remote_preference"] == "Any"


def test_eval_dataset_file_is_valid_json_array():
    path = Path(__file__).resolve().parents[1] / "data" / "eval_examples.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "inputs" in rows[0] or "job_title" in rows[0]
