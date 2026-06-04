# Phase 3.0.3 云端说明

版本：`v3.0.3-config-readiness`

3.0.3 是部署与配置体验修正版，目标是让用户先把云端服务跑起来，再通过快捷菜单配置 ASR/LLM 模型。它不引入流式 ASR、Opus、AFE 或 OTA。

## 重点变化

- 一键部署默认只询问 WebSocket token、服务端口和是否立即打开模型向导。
- 默认不再询问 legacy DeepSeek/OpenAI-compatible API key。
- 模型配置入口移动到 `manage.sh > 模型与语音 > 首次配置向导`。
- 未配置云端 ASR key 时，`cloud_first` 会跳过无效的 Qwen/DashScope 尝试，直接使用 `Vosk -> phase2`。
- `/health` 新增 `model_readiness`，用于说明当前是否已配置 ASR/LLM、是否正在使用本地兜底链路和需要处理的 warning。
- 模型相关菜单补齐主要中英文 i18n 文案。

## 部署后下一步

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

进入：

```text
模型与语音 -> 首次配置向导
```

如果暂时不配置任何模型，系统仍可用于验证 ESP32 录音、OLED 显示、喇叭播放和 WebSocket 会话链路。

## 验收

- 一键部署不强制填写 ASR/LLM API。
- `/health` 返回 `model_readiness`。
- 空 `runtime/config/models.json` 且没有 ASR key 时，ASR chain 为 `["vosk", "phase2"]`。
- 有 DashScope 或 active ASR key 时，云端 ASR 仍可进入 ASR chain。
- `scripts/smoke_manage.sh` 检查模型配置 CLI 和中英文 i18n 基础键。
