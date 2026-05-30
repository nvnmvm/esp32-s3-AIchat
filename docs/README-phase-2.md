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
- 返回 JSON 状态消息：
  - `status`
  - `asr_text`
  - `answer_text`
  - `audio_start`
  - `audio_end`
  - `error`
- 返回可由 ESP32-S3 直接播放的 PCM 测试音频。

当前版本重点是闭环验证。正式 ASR、DeepSeek 和 TTS 的生产级接入会在后续阶段继续增强；阶段二保留 `AI_API_KEY` 和协议字段，便于后续替换实现。

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
APP_VERSION=v2.0.0-phase2
```

## 验收标准

- `/health` 返回 `phase=voice-screen-loopback`。
- ESP32-S3 连接后收到 `status` JSON。
- ESP32-S3 发送 `start_record` 后，云端进入录音状态。
- 云端收到 PCM 音频后返回 `asr_text` 和 `answer_text`。
- 云端返回 `audio_start`、二进制 PCM 音频、`audio_end`。
- ESP32-S3 OLED 显示回答文本，MAX98357A 播放测试音频。

## 发布版本

- 云端 tag/release：`v2.0.0-phase2`
- 配套固件 tag/release：`v2.0.0-phase2`
