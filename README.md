# ESP32-S3 AI 对话机器人云端服务

当前版本：`v2.0.0-phase2`，阶段二语音和屏幕双输出闭环版。

本仓库是 VPS 云端服务。阶段二接收 ESP32-S3 上传的 PCM 音频，返回回答文本和可播放 PCM 音频，用于验证 OLED 显示和 MAX98357A 播放闭环。

## 配套仓库

- 固件仓库：https://github.com/nvnmvm/esp32-s3-AIchat-firmware.git
- 云端仓库：https://github.com/nvnmvm/esp32-s3-AIchat.git

## 阶段 README

- 阶段一：`docs/README-phase-1.md`
- 阶段二：`docs/README-phase-2.md`

每个阶段都通过 tag 和 GitHub Release 固定版本，后续阶段不覆盖前一阶段说明。

## VPS 阶段二部署

阶段二测试前需要先删除阶段一旧部署，再部署阶段二代码。推荐使用 `--clean`：

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

部署完成后记录输出的：

- `WS_HOST`
- `WS_PORT`
- `WS_TOKEN`

这些值要填入固件仓库的 `include/config.h`。

## 常用命令

```bash
sudo bash /opt/esp32-ai-voice-cloud/manage.sh
sudo bash /opt/esp32-ai-voice-cloud/scripts/doctor.sh
cd /opt/esp32-ai-voice-cloud && docker compose ps
cd /opt/esp32-ai-voice-cloud && docker compose logs -f
curl -fsS http://127.0.0.1:8000/health
```

如果使用云服务器，还需要在云厂商安全组放行实际 TCP 端口，默认是 `8000`。

## 阶段二 WebSocket 协议

ESP32-S3 到云端：

```json
{"type":"start_record"}
```

随后上传二进制 PCM 音频块：16 kHz、16 bit、mono、little-endian。

录音结束可发送：

```json
{"type":"finish_record"}
```

取消或退出：

```json
{"type":"cancel"}
{"type":"stop"}
```

云端到 ESP32-S3：

```json
{"type":"status","text":"录音中...","state":"recording"}
{"type":"asr_text","text":"阶段二测试音频已收到..."}
{"type":"answer_text","text":"阶段二闭环已完成..."}
{"type":"audio_start","sample_rate":16000,"format":"pcm_s16le"}
```

然后发送二进制 PCM 音频，最后：

```json
{"type":"audio_end"}
```

## 配置

`.env.example` 包含阶段二默认值：

```env
SERVER_PORT=8000
WS_TOKEN=change-this-token
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=
LOG_LEVEL=INFO
LOG_PAYLOADS=false
MAX_WS_MESSAGE_BYTES=1048576
MAX_RECORDING_BYTES=384000
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_SAMPLE_WIDTH_BYTES=2
VAD_MIN_RECORDING_BYTES=32000
VAD_SILENCE_RMS=450
VAD_SILENCE_CHUNKS=12
MOCK_TTS_DURATION_MS=900
MOCK_TTS_TONE_HZ=660
APP_VERSION=v2.0.0-phase2
```

当前阶段二返回本地测试 PCM 提示音，用来验证 MAX98357A 播放链路。正式 ASR、DeepSeek、TTS 接入保留到后续阶段继续替换增强。

## 本地测试

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

Docker 构建：

```bash
docker build -t esp32-ai-voice-cloud:phase2 .
```
