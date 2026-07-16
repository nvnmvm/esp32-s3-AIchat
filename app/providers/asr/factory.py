from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.audio_utils import AudioReport
from app.core.model_config import active_item
from app.providers.asr.base import ASRProvider, AsrResult
from app.providers.asr.openai_multimodal import OpenAIMultimodalASRProvider
from app.providers.asr.phase2 import Phase2ASRProvider
from app.providers.asr.qwen_dashscope import QwenDashScopeASRProvider
from app.providers.asr.vosk_local import VoskLocalASRProvider


def provider_chain(settings: Any) -> list[str]:
    configured_asr = active_item(getattr(settings, "model_config", {}), "asr_models")
    provider = getattr(settings, "asr_provider", "auto")
    primary = getattr(settings, "asr_primary", "qwen_dashscope")
    fallback = getattr(settings, "asr_fallback", "vosk")
    strategy = getattr(settings, "asr_strategy", "cloud_first")

    if provider == "auto":
        if strategy in {"cloud_first", "cloud", "cost_first"}:
            chain = [primary, fallback, "phase2"]
        elif strategy in {"local_first", "local"}:
            chain = ["vosk", primary, fallback, "phase2"]
        elif strategy in {"llm_audio", "multimodal_first", "ai_audio"}:
            chain = ["configured_asr", "qwen_dashscope", "vosk", "phase2"]
        elif strategy in {"offline", "vosk_only"}:
            chain = ["vosk", "phase2"]
        elif strategy in {"accuracy_first", "accuracy"}:
            chain = ["configured_asr", "qwen_dashscope", "openai_multimodal", "vosk", "phase2"]
        else:
            chain = [primary, fallback, "phase2"]
    elif provider == "cloud":
        chain = [primary, fallback]
    elif provider == "local":
        chain = ["vosk", "phase2"]
    else:
        chain = [provider]

    resolved: list[str] = []
    for name in chain:
        if name in {"configured", "configured_asr"}:
            if configured_asr:
                provider_name = str(configured_asr.get("provider", "openai_multimodal"))
                if _cloud_provider_ready(provider_name, settings, configured_asr):
                    resolved.append(provider_name)
            continue
        if provider == "auto" and _is_cloud_provider(str(name)) and not _cloud_provider_ready(str(name), settings, configured_asr):
            continue
        resolved.append(str(name))

    return _dedupe([name for name in resolved if name])


def build_provider(name: str, settings: Any) -> ASRProvider:
    normalized = name.lower().replace("-", "_")
    configured_asr = active_item(getattr(settings, "model_config", {}), "asr_models")

    if normalized in {"phase2", "debug"}:
        return Phase2ASRProvider()
    if normalized in {"vosk", "vosk_local"}:
        return VoskLocalASRProvider(
            model_dir=Path(getattr(settings, "vosk_model_dir")),
            model_url=getattr(settings, "vosk_model_url"),
            auto_download=getattr(settings, "vosk_auto_download"),
            sample_rate=getattr(settings, "audio_sample_rate"),
        )
    if normalized in {"qwen", "qwen_dashscope", "dashscope"}:
        item = configured_asr if configured_asr and configured_asr.get("provider") in {"qwen", "qwen_dashscope"} else {}
        return QwenDashScopeASRProvider(
            api_key=str(item.get("api_key") or getattr(settings, "dashscope_api_key", "")),
            model=str(item.get("model") or getattr(settings, "dashscope_asr_model", "qwen3-asr-flash")),
            base_http_api_url=str(
                item.get("base_http_api_url")
                or getattr(settings, "dashscope_base_http_api_url", "https://dashscope.aliyuncs.com/api/v1")
            ),
            language=str(item.get("language") or getattr(settings, "asr_language", "zh")),
            enable_itn=bool(item.get("enable_itn", True)),
        )
    if normalized in {"openai_audio", "openai_multimodal", "multimodal_llm", "custom_http"}:
        item = configured_asr if configured_asr and configured_asr.get("provider") in {"openai_multimodal", "custom_http"} else {}
        return OpenAIMultimodalASRProvider(
            api_key=str(item.get("api_key") or getattr(settings, "ai_api_key", "")),
            base_url=str(item.get("base_url") or getattr(settings, "ai_api_base", "https://api.deepseek.com")),
            model=str(item.get("model") or getattr(settings, "ai_model", "deepseek-v4-flash")),
            timeout_seconds=int(getattr(settings, "asr_timeout_seconds", 60)),
            brand=str(item.get("brand") or "openai-compatible"),
        )

    raise RuntimeError(f"Unknown ASR provider: {name}")


def transcribe_with_fallback(wav_path: Path, audio_report: AudioReport, settings: Any) -> AsrResult:
    if audio_report.verdict in {"too_short", "mostly_zero"}:
        return AsrResult(
            text=audio_report.human_message,
            provider="audio_gate",
            raw={"audio_report": audio_report.to_dict()},
        )

    errors: list[str] = []
    for provider_name in provider_chain(settings):
        try:
            provider = build_provider(provider_name, settings)
            result = provider.transcribe(wav_path, audio_report, context=getattr(settings, "asr_context", ""))
            if errors:
                result.fallback_from = ",".join(errors)
            return result
        except Exception as exc:
            errors.append(f"{provider_name}:{type(exc).__name__}")

    if errors:
        fallback = Phase2ASRProvider().transcribe(wav_path, audio_report)
        fallback.fallback_from = ",".join(errors)
        return fallback
    raise RuntimeError("No ASR provider configured.")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _is_cloud_provider(name: str) -> bool:
    normalized = name.lower().replace("-", "_")
    return normalized in {
        "qwen",
        "qwen_dashscope",
        "dashscope",
        "openai_audio",
        "openai_multimodal",
        "multimodal_llm",
        "custom_http",
    }


def _cloud_provider_ready(name: str, settings: Any, configured_asr: dict[str, Any] | None) -> bool:
    normalized = name.lower().replace("-", "_")
    configured_provider = str((configured_asr or {}).get("provider") or "").lower().replace("-", "_")

    if normalized in {"qwen", "qwen_dashscope", "dashscope"}:
        configured_key = ""
        if configured_provider in {"qwen", "qwen_dashscope", "dashscope"}:
            configured_key = str((configured_asr or {}).get("api_key") or "")
        return bool(configured_key or getattr(settings, "dashscope_api_key", ""))

    if normalized in {"openai_audio", "openai_multimodal", "multimodal_llm", "custom_http"}:
        configured_key = ""
        if configured_provider in {"openai_audio", "openai_multimodal", "multimodal_llm", "custom_http"}:
            configured_key = str((configured_asr or {}).get("api_key") or "")
        return bool(configured_key or getattr(settings, "ai_api_key", ""))

    return True
