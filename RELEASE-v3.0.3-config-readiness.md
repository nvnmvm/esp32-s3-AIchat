# v3.0.3-config-readiness

3.0.3 聚焦部署与配置体验，不引入流式传输或新的音频协议。

## 云端变化

- 一键部署默认不再强制配置 ASR/LLM API，只询问 WebSocket token、端口和是否立即打开首次配置向导。
- 新增 `模型与语音 -> 首次配置向导`，按 ASR、LLM、ASR 策略和状态查看的顺序引导配置。
- `cloud_first` 在未配置 active ASR 或 DashScope key 时跳过无效云端 provider，直接使用 `Vosk -> phase2`。
- `/health` 新增 `model_readiness`，包含 `asr_configured`、`llm_configured`、`using_local_fallback` 和 warnings。
- dashboard、doctor 和模型菜单会显示 readiness 状态，帮助区分无模型测试和真实模型模式。
- 模型相关菜单补齐主要中英文 i18n 文案。

## 验证

```bash
python -m pip install -r requirements-dev.txt
pytest -q
bash scripts/smoke_manage.sh
```

## 兼容性

- 保持 Phase 3 JSON + PCM WebSocket 协议。
- `SEND_ASR_TEXT=false` 仍为默认，ESP32 OLED 不显示中间识别页。
- 没有配置模型时仍可验证 ESP32 录音、OLED、喇叭和云端会话链路。
