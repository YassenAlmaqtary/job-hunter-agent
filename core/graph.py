"""
Job Hunter LangGraph definition.

EN: Linear pipeline for now: START → cv_optimizer → cover_letter → END.
    `MemorySaver` enables thread-scoped memory (HITL / multi-turn later).
AR: تدفق خطي حالياً؛ الذاكرة مرتبطة بـ thread_id في الإعدادات.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.nodes import (
    cover_letter_node,
    cv_optimizer_node,
    daily_alert_node,
    job_match_node,
    job_search_node,
)
from core.state import JobHunterState


def create_job_hunter_graph(llm: BaseChatModel) -> Any:
    """
    EN: Build and compile the StateGraph with in-memory checkpointing.
    AR: يبني الرسم البياني ويُجمّعه مع حفظ جلسات في الذاكرة.

    Future (HITL / Supervisor):
        workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["some_review_node"],
        )
    """

    # لفّ العقد closures يسمح بتمرير llm مرة واحدة فقط من المصنع.
    def _job_search(state: JobHunterState) -> dict[str, Any]:
        return job_search_node(state, llm)

    def _job_match(state: JobHunterState) -> dict[str, Any]:
        return job_match_node(state, llm)

    def _cv_optimizer(state: JobHunterState) -> dict[str, Any]:
        return cv_optimizer_node(state, llm)

    def _cover_letter(state: JobHunterState) -> dict[str, Any]:
        return cover_letter_node(state, llm)

    def _daily_alert(state: JobHunterState) -> dict[str, Any]:
        return daily_alert_node(state, llm)

    # تعريف العقد ثم ربطها كسير عمل end-to-end.
    workflow = StateGraph(JobHunterState)
    workflow.add_node("job_search", _job_search)
    workflow.add_node("job_match", _job_match)
    workflow.add_node("cv_optimizer", _cv_optimizer)
    workflow.add_node("cover_letter", _cover_letter)
    workflow.add_node("daily_alert", _daily_alert)

    workflow.add_edge(START, "job_search")
    workflow.add_edge("job_search", "job_match")
    workflow.add_edge("job_match", "cv_optimizer")
    workflow.add_edge("cv_optimizer", "cover_letter")
    workflow.add_edge("cover_letter", "daily_alert")
    workflow.add_edge("daily_alert", END)

    # MemorySaver يحفظ سياق كل thread داخل الجلسة الحالية.
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
