"""
Job Hunter Agent — domain & infrastructure package.

Package map (read this first when navigating the codebase):

    core/
      agent/          LangGraph pipeline (state → nodes → graph → runner)
      auth/           Authentication & sessions (no Streamlit UI)
      db/             PostgreSQL helpers
      jobs/           Matching, alerts, and job listing sources
      llm/            Multi-provider chat model factory
      observability/  LangSmith tracing + evaluators
      feedback/       Idea-feedback JSON store

UI lives under ``app/``. Entry point: ``streamlit_app.py``.
"""

from core.agent.graph import create_job_hunter_graph
from core.agent.state import JobHunterState
from core.llm.providers import LLM_PROVIDERS, build_chat_llm, get_provider, provider_labels_ar

__all__ = [
    "JobHunterState",
    "create_job_hunter_graph",
    "LLM_PROVIDERS",
    "build_chat_llm",
    "get_provider",
    "provider_labels_ar",
]
