# 阶段二 README：语音和屏幕双输出闭环版

阶段二验证从 ESP32-S3 到 VPS 再回到 ESP32-S3 的语音/屏幕闭环。

## 云端功能

- WebSocket token 鉴权。
- 接收 ESP32-S3 的 JSON 控制消息：
  - `start_record`
  - `finish_record`
  - `cancel`
  - `stop`
- 接收 16 kHz、16 bit、mono、PCM little-endian 音频块。
- 用轻量 RMS/VAD 判断录音结束。
- 可选保存每轮 debug WAV 到 `runtime/audio`。
- 将本轮语音解析文本写入 `runtime/conversations` 临时文本文件。
- 回复逻辑读取本轮文本文件后自动删除，不保留历史上下文。
- 返回 JSON 状态消息：
  - `status`
  - `asr_text`
  - `answer_text`
  - `audio_start`
  - `audio_end`
  - `error`
- 返回可由 ESP32-S3 直接播放的 PCM 测试音频。

当前版本重点是闭环验证和阶段三前的工程化过渡。阶段二默认测试解析不消耗大模型 token；配置 `LLM_PROVIDER=deepseek` 和 `DEEPSEEK_API_KEY` 后可走 DeepSeek 普通非流式问答。正式流式 ASR、流式 LLM、分句 TTS 保留到阶段三。

## VPS 阶段二测试部署

测试阶段二前，先删除阶段一旧目录和容器，再部署新代码。推荐直接使用 `--clean`：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh && sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

Debian：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-debian.sh -o install-debian.sh && sudo bash install-debian.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

Ubuntu：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh && sudo bash install-ubuntu.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

安装脚本拉取代码后会输出 `Downloaded cloud code version`，部署完成后会输出 `Configured APP_VERSION`、`Git code version` 和 `/health` 实际运行版本，方便确认 VPS 当前运行的云端版本。

## 云端配置

`.env` 关键项：

```env
SERVER_PORT=8000
WS_TOKEN=change-this-token
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=
MAX_WS_MESSAGE_BYTES=1048576
MAX_RECORDING_BYTES=384000
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_SAMPLE_WIDTH_BYTES=2
VAD_MIN_RECORDING_BYTES=32000
VAD_SILENCE_RMS=450
VAD_SILENCE_CHUNKS=12
ASR_PROVIDER=phase2
LLM_PROVIDER=phase2
TTS_PROVIDER=tone
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=30
SAVE_DEBUG_WAV=false
DEBUG_AUDIO_DIR=runtime/audio
CONVERSATION_DIR=runtime/conversations
APP_VERSION=v2.1.1-phase2-complete
```

## 快捷管理界面

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

菜单包含：

- 随机重新生成或手动修改 WebSocket 令牌。
- 修改 WebSocket 端口，并尝试放行本机防火墙。
- 修改 AI API Key。
- 查看容器状态、健康检查、最近日志和实时日志。
- 启动、关闭、重启 WebSocket 服务。
- 一键更新：保留数据更新或不保留运行数据更新。
- 卸载 WebSocket 服务。

`v2.1.1-phase2-complete` 支持从 `v2.0.1-phase2`、`v2.0.2-phase2` 和 `v2.1.x` 保留 `.env` 与 `runtime/` 更新。其他旧版本或未知版本会在更新菜单中提示先备份，或选择不保留运行数据更新。

## 验收标准

- `/health` 返回 `phase=voice-screen-loopback`。
- ESP32-S3 连接后收到 `status` JSON。
- ESP32-S3 发送 `start_record` 后，云端进入录音状态。
- 云端收到 PCM 音频后返回 `asr_text` 和 `answer_text`。
- `SAVE_DEBUG_WAV=true` 时，VPS 的 `runtime/audio` 下能看到 WAV。
- 本轮语音解析文本文件在回复完成后自动删除。
- 云端返回 `audio_start`、二进制 PCM 音频、`audio_end`。
- ESP32-S3 OLED 显示回答文本，MAX98357A 播放测试音频。

## 发布版本

- 云端 tag/release：`v2.1.1-phase2-complete`
- 配套固件 tag/release：`v2.1.0-phase2-complete`
