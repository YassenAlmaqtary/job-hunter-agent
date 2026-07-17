"""Map raw LLM/provider exceptions to short Arabic guidance for the UI."""

from __future__ import annotations

import re


def format_runtime_error(exc: Exception, provider_id: str) -> str:
    raw = str(exc or "").strip()
    low = raw.lower()

    if (
        "resource_exhausted" in low
        or "quota exceeded" in low
        or "you exceeded your current quota" in low
        or "429" in low
    ):
        wait_hint = ""
        delay_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", low)
        if delay_match:
            try:
                secs = int(float(delay_match.group(1)))
                wait_hint = f"\n- أعد المحاولة بعد حوالي {secs} ثانية."
            except ValueError:
                wait_hint = "\n- أعد المحاولة بعد دقيقة تقريبًا."

        if provider_id == "gemini":
            return (
                "تعذر التشغيل عبر Gemini بسبب تجاوز الحصة (Quota 429).\n"
                "- تحقق أن مشروع Google AI لديه حصة فعالة وفوترة مفعلة.\n"
                "- راجع الاستهلاك والحدود من لوحة Google AI Studio."
                f"{wait_hint}\n"
                "- كحل سريع: بدّل المزود إلى OpenAI أو Grok إن كان المفتاح متاحًا."
            )

        return (
            "تعذر التشغيل بسبب تجاوز الحصة/الحد الأقصى للطلبات (429).\n"
            "- انتظر قليلًا ثم أعد المحاولة.\n"
            "- تحقق من الفوترة وحدود الاستخدام لدى المزود.\n"
            "- أو بدّل إلى مزود آخر مؤقتًا."
        )

    if "api key" in low or "غير مضبوط" in low or "not set" in low:
        if (
            "invalid_api_key" in low
            or "invalid api key" in low
            or "authenticationerror" in low
            or "401" in low
            or "unauthorized" in low
        ):
            provider_name = {
                "gemini": "Gemini",
                "groq": "Groq",
                "grok": "xAI Grok",
                "openai": "OpenAI",
            }.get(provider_id, "المزوّد")
            return (
                f"تعذر التشغيل عبر {provider_name}: الخدمة غير متاحة حاليًا.\n"
                "- جرّب مزودًا آخر من القائمة.\n"
                "- أو أعد المحاولة لاحقًا."
            )

        return (
            "تعذر التشغيل بسبب مشكلة في إعدادات الخدمة.\n"
            "- جرّب مزودًا آخر من القائمة.\n"
            "- أو أعد المحاولة لاحقًا."
        )

    return f"فشل التشغيل: {raw}"
