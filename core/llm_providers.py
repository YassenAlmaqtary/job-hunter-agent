"""
قابلية توسيع لمزودي نماذج الدردشة / Multi-provider LLM factory.

EN: Central registry + `build_chat_llm()` so Streamlit (or APIs) can switch
    OpenAI, Gemini, or xAI Grok without touching graph nodes.
AR: سجل موحّد لإضافة مزودين جدد لاحقاً (أوراق، محلي، …).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq


@dataclass(frozen=True)
class LLMProviderSpec:
    """EN: One row in the provider registry. AR: تعريف مزود واحد."""

    id: str
    label_ar: str
    label_en: str
    default_model: str
    suggested_models: tuple[str, ...]
    env_keys: tuple[str, ...]
    build: Callable[[str, float], BaseChatModel]


def _build_openai(model: str, temperature: float) -> BaseChatModel:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY غير مضبوط في البيئة.")
    return ChatOpenAI(model=model, api_key=key, temperature=temperature)


def _build_grok(model: str, temperature: float) -> BaseChatModel:
    """EN: xAI Grok uses an OpenAI-compatible HTTP API."""
    key = os.getenv("XAI_API_KEY", "").strip()
    if not key:
        raise ValueError("XAI_API_KEY غير مضبوط في البيئة.")
    return ChatOpenAI(
        model=model,
        api_key=key,
        base_url="https://api.x.ai/v1",
        temperature=temperature,
    )


def _build_gemini(model: str, temperature: float) -> BaseChatModel:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        raise ImportError(
            "ثبّت الحزمة: pip install langchain-google-genai"
        ) from e
    key = (
        os.getenv("GOOGLE_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
    )
    if not key:
        raise ValueError("GOOGLE_API_KEY أو GEMINI_API_KEY غير مضبوط في البيئة.")
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=key,
        temperature=temperature,
    )

def _build_groq(model: str, temperature: float) -> BaseChatModel:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError("GROQ_API_KEY غير مضبوط في البيئة.")
    return ChatGroq(
        model=model,
        # Use provider-specific argument for maximum compatibility.
        groq_api_key=key,
        temperature=temperature,
    )


# EN: Append new providers here only — UI reads this dict.
# AR: لإضافة مزود جديد: انسخ نمطاً وأضف دالة build_* ثم سجّلها هنا.
LLM_PROVIDERS: dict[str, LLMProviderSpec] = {
    "openai": LLMProviderSpec(
        id="openai",
        label_ar="OpenAI (ChatGPT)",
        label_en="OpenAI (ChatGPT)",
        default_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        suggested_models=(
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o4-mini",
        ),
        env_keys=("OPENAI_API_KEY",),
        build=_build_openai,
    ),
    "gemini": LLMProviderSpec(
        id="gemini",
        label_ar="Google Gemini",
        label_en="Google Gemini",
        default_model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
        or "gemini-3-flash-preview",
        suggested_models=(
            "gemini-3.1-flash-lite-preview",
            "gemini-3-flash-preview"
        ),
        env_keys=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        build=_build_gemini,
    ),
    "grok": LLMProviderSpec(
        id="grok",
        label_ar="xAI Grok",
        label_en="xAI Grok",
        default_model=os.getenv("XAI_MODEL", "grok-2-latest").strip() or "grok-2-latest",
        suggested_models=("grok-2-latest", "grok-3-latest", "grok-3-mini-fast"),
        env_keys=("XAI_API_KEY",),
        build=_build_grok,
    ),
    
    "groq": LLMProviderSpec(
        id="groq",
        label_ar="Groq",
        label_en="Groq",
        default_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant",
        suggested_models=("llama-3.1-8b-instant", "llama-3.1-70b-instant"),
        env_keys=("GROQ_API_KEY", "GROQ_KEY"),
        build=_build_groq,
    ),
}


def provider_labels_ar() -> list[tuple[str, str]]:
    """EN: (id, Arabic label) for selectbox."""
    return [(spec.id, spec.label_ar) for spec in LLM_PROVIDERS.values()]


def get_provider(provider_id: str) -> LLMProviderSpec:
    pid = (provider_id or "").strip().lower()
    if pid not in LLM_PROVIDERS:
        raise ValueError(f"مزود غير معروف: {provider_id!r}. الخيارات: {list(LLM_PROVIDERS)}")
    return LLM_PROVIDERS[pid]


def provider_key_configured(spec: LLMProviderSpec) -> tuple[bool, str | None]:
    """
    EN: True if any of `env_keys` is non-empty.
    AR: هل يوجد مفتاح صالح لهذا المزود؟
    """
    for k in spec.env_keys:
        if os.getenv(k, "").strip():
            return True, k
    return False, None


def build_chat_llm(
    provider_id: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
) -> BaseChatModel:
    """
    EN: Instantiate the chat model for LangGraph nodes.
    AR: ينشئ نموذج الدردشة حسب المزود واسم النموذج.
    """
    spec = get_provider(provider_id)
    resolved = (model or "").strip() or spec.default_model
    return spec.build(resolved, temperature)
