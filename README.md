# ESP32-S3 AI 对话机器人云端服务

当前版本：`v3.0.1-phase3-asr-quality`。本版本重点把 3.0.0 的“能跑通语音链路”升级为“录音质量可诊断、ASR 可切换、模型配置可管理、故障可定位”的成熟对话基础版。

## 3.0.1 核心变化

- ASR 默认进入 `auto` 链路：已配置云端 ASR / 多模态大模型优先，Vosk 本地兜底，phase2 仅用于硬件调试。
- 每轮录音生成 `runtime/session/audio_report/*.audio_report.json`，记录时长、RMS、peak、削波比例、零值比例、直流偏移、有效语音占比和诊断结论。
- 每轮生成 `*.turn_meta.json`，记录 ASR provider、fallback 来源和音频诊断，便于定位“不准”到底是麦克风、VAD 还是模型问题。
- `runtime/config/models.json` 支持多个 LLM/ASR 模型配置，可通过 `manage.sh` 菜单新增、切换、删除。该文件在 `runtime/` 下，不提交到 Git。
- OLED 默认不再显示识别文本页面；回答文本直接进入滚动显示。云端默认 `SEND_ASR_TEXT=false`。
- 3.0.1 仍使用一问一答文件级 ASR，不要求流式传输。流式 ASR / Opus / MCP 留到 3.1。

## 一键部署

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh && sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

部署脚本会询问：

- WebSocket token
- 服务端口
- 是否添加一个或多个模型
- 模型用途：LLM 对话模型或 ASR 转写模型
- 品牌、API key、模型名

模型配置写入：

```text
runtime/config/models.json
```

示例结构见：

```text
config/model_config.example.json
```

## 快捷菜单

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

菜单中的 `Large model brands` 支持：

- 查看已部署模型
- 添加 LLM 对话模型
- 添加 ASR 转写模型
- 按 ID 切换当前模型
- 删除已部署模型

当前实现支持：

- LLM：DeepSeek、Qwen / 阿里百炼、豆包 / 火山 Ark、任意 OpenAI-compatible 地址
- ASR：Qwen DashScope ASR、OpenAI-compatible 多模态模型转写
- 本地兜底：Vosk small 中文模型

## 关键配置

```env
ASR_PROVIDER=auto
ASR_PRIMARY=configured_asr
ASR_FALLBACK=vosk
MODEL_CONFIG_PATH=runtime/config/models.json
SEND_ASR_TEXT=false
SEND_ANSWER_TEXT=true
APP_VERSION=v3.0.1-phase3-asr-quality
```

`.env` 适合存放部署级开关；`runtime/config/models.json` 适合存放多个模型条目。真实 API key 不要提交到仓库。

## 音频诊断

查看最近录音：

```bash
ls runtime/session/录音
ls runtime/session/audio_report
```

单独诊断一个 WAV：

```bash
python scripts/inspect_wav.py runtime/session/录音/xxx.wav
```

对同一 WAV 重新跑 ASR：

```bash
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav --provider phase2
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav --provider vosk
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav --provider auto
```

## Health

```bash
curl -fsS http://127.0.0.1:8000/health
```

`/health` 会返回：

- `asr_provider_chain`
- `vosk_model_exists`
- `model_config_exists`
- `session_dirs.audio_report`
- VAD 阈值和录音限制
- 当前已配置模型的脱敏摘要

## 故障定位顺序

1. 先看 `audio_report.json`：如果 `too_quiet`、`mostly_zero`、`clipped`，优先检查麦克风声道、接线、供电、增益。
2. 再用 `scripts/asr_transcribe.py` 对同一个 WAV 分别跑 `phase2`、`vosk`、`auto`。
3. 如果 `auto` 不准但 `audio_report.verdict=ok`，优先换云端 ASR 或多模态 ASR 模型。
4. 如果云端 ASR key 失效，`auto` 会回退到 Vosk，保证整轮对话不断。

## 本地测试

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

Docker 构建：

```bash
docker build -t esp32-ai-voice-cloud:3.0.1 .
```
