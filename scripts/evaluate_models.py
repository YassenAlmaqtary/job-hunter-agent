"""
مقارنة مزودي/نماذج LLM على pipeline الوكيل عبر LangSmith.

الفكرة: نفس أمثلة الاختبار تُشغَّل على نماذج مختلفة، ثم تُقارن الدرجات.

تشغيل محلي:
    python scripts/evaluate_models.py
    python scripts/evaluate_models.py --providers gemini groq
    python scripts/evaluate_models.py --upload-dataset
"""

#لتشغيل السكربت محلياً: python scripts/evaluate_models.py
#لتشغيل السكربت داخل Docker: docker run --rm -it -v $(pwd)/data:/app/data -v $(pwd)/.env:/app/.env job-hunter-eval python scripts/evaluate_models.py
#لتشغيل السكربت باستخدام --upload-dataset: python scripts/evaluate_models.py --upload-dataset
#لتشغيل السكربت باستخدام --providers و --models: python scripts/evaluate_models.py --providers gemini groq --models gemini-3-flash-preview llama-3.1-8b-instant

from __future__ import annotations

import argparse  # لقراءة خيارات سطر الأوامر (--providers وغيرها)
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv  # لتحميل مفاتيح API من ملف .env

# جذر المشروع — حتى يعمل السكربت من أي مجلد: python scripts/evaluate_models.py
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")  # يقرأ .env قبل أي استيراد يحتاج مفاتيح

from core.observability import ensure_tracing_env, tracing_enabled, tracing_project  # noqa: E402

ensure_tracing_env()  # يزامن LANGSMITH_* مع LANGCHAIN_* حتى يعمل التتبع

from core.agent.runner import run_job_hunter_from_inputs  # noqa: E402
from core.llm.providers import LLM_PROVIDERS, get_provider, provider_key_configured  # noqa: E402
from core.observability.evaluators import DEFAULT_EVALUATORS  # noqa: E402

# ملف الأمثلة الافتراضي: سيرة + وظيفة + مهارات لكل حالة اختبار
DEFAULT_DATASET_PATH = _ROOT / "data" / "eval_examples.json"


def _load_examples(path: Path) -> list[dict[str, Any]]:
    """يقرأ ملف JSON المحلي ويحوّله لصيغة LangSmith: [{"inputs": {...}}, ...]"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Dataset must be a JSON array: {path}")
    examples: list[dict[str, Any]] = []
    for idx, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValueError(f"Row {idx} must be an object.")
        # إن وُجد مفتاح inputs نأخذه؛ وإلا الصف كله يُعتبر مدخلات
        if "inputs" in row:
            examples.append({"inputs": row["inputs"]})
        else:
            examples.append({"inputs": row})
    return examples


def _ensure_langsmith_dataset(
    client: Any,
    dataset_name: str,
    examples: list[dict[str, Any]],
    *,
    sync: bool = False,
) -> str:
    """
    LangSmith يحتاج dataset مرفوعاً على السحابة (ليس ملف JSON محلياً فقط).
    تُنشئ المجموعة إن لم تكن موجودة، أو تُحدّثها عند sync=True.
    """
    existing = list(client.list_datasets(dataset_name=dataset_name))
    if not existing:
        # أول مرة: إنشاء dataset جديد ورفع كل الأمثلة
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="Job Hunter Agent evaluation examples (CV + job context).",
        )
        for row in examples:
            client.create_example(
                inputs=row["inputs"],
                outputs=row.get("outputs"),
                dataset_id=dataset.id,
            )
        print(f"Created LangSmith dataset: {dataset_name} ({len(examples)} examples)")
        return dataset_name

    dataset = existing[0]
    current = list(client.list_examples(dataset_id=dataset.id))
    if sync:
        # --upload-dataset: حذف الأمثلة القديمة واستبدالها بمحتوى الملف المحلي
        for example in current:
            client.delete_example(example.id)
        for row in examples:
            client.create_example(
                inputs=row["inputs"],
                outputs=row.get("outputs"),
                dataset_id=dataset.id,
            )
        print(f"Synced LangSmith dataset: {dataset_name} ({len(examples)} examples)")
    elif not current:
        # dataset موجود لكنه فارغ — نملؤه
        for row in examples:
            client.create_example(
                inputs=row["inputs"],
                outputs=row.get("outputs"),
                dataset_id=dataset.id,
            )
        print(f"Populated empty dataset: {dataset_name} ({len(examples)} examples)")
    else:
        # dataset موجود وفيه أمثلة — نستخدمه كما هو
        print(f"Using LangSmith dataset: {dataset_name} ({len(current)} examples)")
    return dataset_name


def _parse_provider_model_pairs(
    providers: list[str],
    models: list[str],
) -> list[tuple[str, str]]:
    """
    يبني أزواج (مزود، نموذج) للمقارنة.
    مثال: providers=[gemini, groq] و models=[gemini-3-flash, llama-3.1-8b]
    """
    pairs: list[tuple[str, str]] = []
    if models:
        if len(models) != len(providers):
            raise ValueError("When --models is set, it must have the same length as --providers.")
        pairs = list(zip(providers, models, strict=True))
    else:
        # لم تُحدَّد نماذج — نأخذ الافتراضي لكل مزود من llm_providers.py
        for provider_id in providers:
            spec = get_provider(provider_id)
            pairs.append((provider_id, spec.default_model))
    return pairs


def _ensure_api_key() -> None:
    """يتأكد أن مفتاح LangSmith موجود قبل بدء التقييم."""
    if not tracing_enabled():
        print(
            "Warning: LANGSMITH_TRACING is off. Traces may not appear in LangSmith.\n"
            "Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY in .env"
        )
    api_key = os.getenv("LANGSMITH_API_KEY", "").strip() or os.getenv("LANGCHAIN_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "LANGSMITH_API_KEY (or LANGCHAIN_API_KEY) is required for evaluation.\n"
            "Create a key at https://smith.langchain.com/settings"
        )


def main() -> None:
    # --- خيارات سطر الأوامر ---
    parser = argparse.ArgumentParser(description="Evaluate Job Hunter models via LangSmith")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="ملف JSON المحلي لأمثلة الاختبار",
    )
    parser.add_argument(
        "--dataset-name",
        default="job-hunter-eval",
        help="اسم dataset في LangSmith",
    )
    parser.add_argument(
        "--upload-dataset",
        action="store_true",
        help="مزامنة الأمثلة المحلية مع LangSmith (يستبدل القديم)",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=list(LLM_PROVIDERS.keys()),
        help="المزودون المراد مقارنتهم (مثلاً gemini groq)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="نموذج لكل مزود بنفس الترتيب؛ الافتراضي = النموذج الافتراضي للمزود",
    )
    parser.add_argument(
        "--experiment-prefix",
        default="job-hunter",
        help="بادئة اسم التجربة في LangSmith",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="درجة الإبداع لكل التشغيلات",
    )
    args = parser.parse_args()

    _ensure_api_key()
    examples = _load_examples(args.dataset)
    if not examples:
        raise SystemExit(f"No examples found in {args.dataset}")

    try:
        from langsmith import Client
        from langsmith.evaluation import evaluate  # الدالة الرئيسية للتقييم في LangSmith
    except ImportError as e:
        raise SystemExit("Install langsmith: pip install langsmith") from e

    client = Client()  # اتصال بـ LangSmith API
    dataset_name = _ensure_langsmith_dataset(
        client,
        args.dataset_name,
        examples,
        sync=args.upload_dataset,
    )
    data = dataset_name  # اسم dataset وليس القائمة المحلية

    pairs = _parse_provider_model_pairs(args.providers, args.models or [])
    project = tracing_project()
    print(f"Project: {project} | Examples: {len(examples)} | Experiments: {len(pairs)}")

    # حلقة المقارنة: لكل (مزود + نموذج) نشغّل تجربة مستقلة
    for provider_id, model_name in pairs:
        spec = get_provider(provider_id)
        ok, _ = provider_key_configured(spec)
        if not ok:
            print(f"Skipping {provider_id}: API key not configured ({spec.env_keys})")
            continue

        experiment = f"{args.experiment_prefix}-{provider_id}-{model_name}"

        def target(
            inputs: dict[str, Any],
            *,
            _provider: str = provider_id,
            _model: str = model_name,
            _temperature: float = args.temperature,
        ) -> dict[str, Any]:
            """
            الدالة التي يستدعيها LangSmith لكل مثال في dataset.
            inputs = سيرة + وظيفة + مهارات...
            المخرج = حالة الوكيل الكاملة بعد التشغيل.
            """
            return run_job_hunter_from_inputs(
                inputs,
                provider_id=_provider,
                model_name=_model,
                temperature=_temperature,
                run_tags=["eval", f"eval:{_provider}", f"eval:{_model}"],
            )

        print(f"\nRunning experiment: {experiment}")
        results = evaluate(
            target,  # ماذا نشغّل؟ الوكيل
            data=data,  # على أي بيانات؟ dataset في LangSmith
            evaluators=DEFAULT_EVALUATORS,  # كيف نقيّم؟ جودة السيرة والخطاب...
            experiment_prefix=experiment,  # اسم التجربة في اللوحة
            metadata={"provider": provider_id, "model": model_name, "project": project},
            client=client,
        )
        print(f"Done: {experiment} → {results.experiment_name}")


if __name__ == "__main__":
    main()  # نقطة الدخول عند: python scripts/evaluate_models.py
