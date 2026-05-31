# ESP32-S3 AI 对话机器人云端服务

当前版本：`v3.0.0-phase3-session-voice`，阶段三 session 文件化语音助手版。

本仓库是 VPS 云端服务。阶段三接收 ESP32-S3 上传的 PCM 音频，保存录音到 session 文件夹，使用 ASR 转文字，调用 AI API 生成回答并保存文本，再把回答文本和 TTS PCM 音频返回给 ESP32，用于 OLED 右向左滚动显示和 MAX98357A 播放。

## 配套仓库

- 固件仓库：https://github.com/nvnmvm/esp32-s3-AIchat-firmware.git
- 云端仓库：https://github.com/nvnmvm/esp32-s3-AIchat.git

## 阶段 README

- 阶段一：`docs/README-phase-1.md`
- 阶段二：`docs/README-phase-2.md`
- 阶段三：`docs/README-phase-3.md`

每个阶段都通过 tag 和 GitHub Release 固定版本，后续阶段不覆盖前一阶段说明。

## VPS 阶段三部署

阶段三测试前建议先备份旧 `.env` 和 `runtime/`，再部署阶段三代码。首次完整重装可使用 `--clean`：

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
- `Configured APP_VERSION`
- `Git code version`
- `Running /health version`

这些值要填入固件仓库的 `include/config.h`。

## 常用命令

```bash
sudo bash /opt/esp32-ai-voice-cloud/manage.sh
sudo bash /opt/esp32-ai-voice-cloud/scripts/doctor.sh
cd /opt/esp32-ai-voice-cloud && docker compose ps
cd /opt/esp32-ai-voice-cloud && docker compose logs -f
curl -fsS http://127.0.0.1:8000/health
```

注意：`docker compose logs -f` 是实时日志命令，会一直占用当前终端。要先按 `Ctrl+C` 退出日志，再执行安装或更新命令。不要把日志命令和安装命令粘在同一行，例如下面这种是错误的：

```bash
docker compose logs -fcurl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh
```

这样 Docker 会把 `curl` 误读成 `logs -f` 后面的参数，并报出 `unknown shorthand flag: 'c' in -curl`。

正确做法是分开执行：

```bash
cd /opt/esp32-ai-voice-cloud
docker compose logs -f
# 看完日志后按 Ctrl+C 退出，再执行下面的更新/安装命令
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh
sudo bash install-ubuntu.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

如果使用云服务器，还需要在云厂商安全组放行实际 TCP 端口，默认是 `8000`。

快捷管理界面调出方法：

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

菜单支持查看配置、随机或手动修改 WebSocket 令牌、修改 WebSocket 端口、修改 AI API Key、查看状态、日志二级菜单、session 文件保留时间、停止/启动/重启 WebSocket 服务、卸载服务、一键更新。更新分为“保留数据更新”和“不保留运行数据更新”；当前 `v3.0.0-phase3-session-voice` 支持从 `v2.0.1-phase2`、`v2.0.2-phase2`、`v2.1.x` 和 `v3.x` 保留 `.env` 与 `runtime/` 更新，其他跨度会在菜单中提示先备份或改用不保留运行数据更新。

日志二级菜单包含：日志保留时间、实时日志、关闭日志、开启日志。日志保留时间里可以选择保留 7 天、3 天或 1 天；默认保留 7 天，旧日志会自动清理，避免长期占用 VPS 空间。

session 文件保留菜单可以选择保留 1 天、3 天、7 天或 30 天；默认 1 天，旧录音、转写文本和 AI 回答文本会自动清理。

## 阶段三 WebSocket 协议

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
{"type":"asr_text","text":"今天上海天气怎么样","transcript_file":"...txt"}
{"type":"answer_text","text":"今天上海天气...","answer_file":"...txt","answer_chars":120,"truncated":false}
{"type":"audio_start","sample_rate":16000,"format":"pcm_s16le"}
```

然后发送二进制 PCM 音频，最后：

```json
{"type":"audio_end"}
```

## 配置

`.env.example` 包含阶段三默认值：

```env
SERVER_PORT=8000
WS_TOKEN=change-this-token
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=
LOG_LEVEL=INFO
LOG_PAYLOADS=false
LOG_TO_FILE=true
LOG_RETENTION_DAYS=7
LOG_DIR=runtime/logs
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
ASR_PROVIDER=vosk
LLM_PROVIDER=phase3
TTS_PROVIDER=edge
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=30
TTS_TIMEOUT_SECONDS=45
SAVE_DEBUG_WAV=false
DEBUG_AUDIO_DIR=runtime/audio
SESSION_DIR=runtime/session
SESSION_RECORDINGS_DIR=runtime/session/录音
SESSION_TRANSCRIPTS_DIR=runtime/session/录音转文字
SESSION_ANSWERS_DIR=runtime/session/ai回答的文本
SESSION_RETENTION_DAYS=1
CONVERSATION_DIR=runtime/session/录音转文字
VOSK_MODEL_DIR=runtime/models/vosk-model-small-cn-0.22
VOSK_MODEL_URL=https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
VOSK_AUTO_DOWNLOAD=true
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
FFMPEG_BIN=ffmpeg
ANSWER_MAX_CHARS=800
TTS_MAX_CHARS=500
APP_VERSION=v3.0.0-phase3-session-voice
```

阶段三会把本轮录音、语音转文字和 AI 回答分别写入 session 的三个子目录，并按 `SESSION_RETENTION_DAYS` 自动清理。默认 ASR 是 Vosk small 中文模型，默认 TTS 是 edge-tts + miniaudio 转 PCM；`LLM_PROVIDER=deepseek` 且配置 `DEEPSEEK_API_KEY` 或 `AI_API_KEY` 后会调用 DeepSeek/OpenAI-compatible 普通非流式接口。

## 配套固件

推荐使用配套固件版本：[v2.1.2-display-stable](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.2-display-stable) 或本仓库同步阶段三固件。阶段三保持原 JSON + PCM WebSocket 协议，固件已能滚动显示 `answer_text` 并播放 `audio_start` 后的 PCM 音频。

## 本地测试

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

Docker 构建：

```bash
docker build -t esp32-ai-voice-cloud:phase3 .
```
