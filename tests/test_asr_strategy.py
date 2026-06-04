from types import SimpleNamespace

from app.providers.asr.factory import provider_chain


def settings(strategy, *, provider="auto", configured_provider="qwen_dashscope", api_key="sk-test-asr"):
    return SimpleNamespace(
        asr_provider=provider,
        asr_primary="configured_asr",
        asr_fallback="vosk",
        asr_strategy=strategy,
        dashscope_api_key="",
        ai_api_key="",
        model_config={
            "active_asr_id": "asr-001",
            "asr_models": [
                {
                    "id": "asr-001",
                    "provider": configured_provider,
                    "api_key": api_key,
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
        "vosk",
        "phase2",
    ]


def test_multimodal_strategy_uses_qwen_fallback_when_dashscope_key_exists():
    qwen_fallback_settings = settings("llm_audio", configured_provider="openai_multimodal")
    qwen_fallback_settings.dashscope_api_key = "sk-dashscope"

    assert provider_chain(qwen_fallback_settings) == [
        "openai_multimodal",
        "qwen_dashscope",
        "vosk",
        "phase2",
    ]


def test_offline_strategy_skips_cloud():
    assert provider_chain(settings("offline")) == ["vosk", "phase2"]


def test_cloud_first_skips_unconfigured_cloud_asr():
    empty_settings = SimpleNamespace(
        asr_provider="auto",
        asr_primary="configured_asr",
        asr_fallback="vosk",
        asr_strategy="cloud_first",
        dashscope_api_key="",
        ai_api_key="",
        model_config={"active_asr_id": "", "asr_models": []},
    )

    assert provider_chain(empty_settings) == ["vosk", "phase2"]


def test_dashscope_env_key_enables_qwen_without_models_json():
    env_settings = SimpleNamespace(
        asr_provider="auto",
        asr_primary="qwen_dashscope",
        asr_fallback="vosk",
        asr_strategy="cloud_first",
        dashscope_api_key="sk-dashscope",
        ai_api_key="",
        model_config={"active_asr_id": "", "asr_models": []},
    )

    assert provider_chain(env_settings) == ["qwen_dashscope", "vosk", "phase2"]
