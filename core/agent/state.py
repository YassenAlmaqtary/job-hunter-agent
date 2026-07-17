"""
Job Hunter graph state schema.

EN: Central TypedDict for LangGraph `StateGraph`. The `messages` channel uses
    `add_messages` for Human-in-the-loop (HITL) and supervisor patterns later.
AR: مخطط الحالة المركزي؛ حقل الرسائل يدعم إضافة رسائل متتابعة (مشرف / مراجع بشري).
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class JobHunterState(TypedDict, total=False):
    """Full agent state. Optional keys use total=False for incremental updates."""

    # --- User & job context (inputs) ---
    user_cv_text: str
    job_title: str
    location: str
    min_salary: str
    experience_level: str
    skills: str
    target_country: str
    job_type: str
    expected_salary: str
    remote_preference: str

    # --- Research phase (future: Job Researcher node) ---
    job_listings: list[dict[str, Any]]
    matched_jobs: list[dict[str, Any]]
    top_jobs: list[dict[str, Any]]

    # --- Generation outputs ---
    optimized_cv: str
    cover_letter: str
    generated_applications: list[dict[str, Any]]
    application_links: list[str]
    match_score: float
    match_explanation: str
    alert_items: list[dict[str, Any]]

    # --- Orchestration & HITL (future: Supervisor + interrupts) ---
    messages: Annotated[list[BaseMessage], add_messages]
    status: str
    human_feedback: str
