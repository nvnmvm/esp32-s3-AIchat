from types import SimpleNamespace

from app.providers.asr.factory import provider_chain


def settings(strategy, *, provider="auto", configured_provider="qwen_dashscope"):
    return SimpleNamespace(
        asr_provider=provider,
        asr_primary="configured_asr",
        asr_fallback="vosk",
        asr_strategy=strategy,
        model_config={
            "active_asr_id": "asr-001",
            "asr_models": [
                {
                    "id": "asr-001",
                    "provider": configured_provider,
                    "enabled": True,
                }
            ],
        },
    )


def test_cloud_first_uses_configured_then_local_fallback():
    assert provider_chain(settings("cloud_first")) == ["qwen_dashscope", "vosk", "phase2"]


def test_local_first_prefers_vosk_before_cloud():
    assert provider_chain(settings("local_first")) == ["vosk", "qwen_dashscope", "phase2"]


def test_multimodal_strategy_can_route_to_configured_llm_audio_provider():
    assert provider_chain(settings("llm_audio", configured_provider="openai_multimodal")) == [
        "openai_multimodal",
        "qwen_dashscope",
        "vosk",
        "phase2",
    ]


def test_offline_strategy_skips_cloud():
    assert provider_chain(settings("offline")) == ["vosk", "phase2"]
