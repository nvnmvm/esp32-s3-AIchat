# ESP32-S3 AI 对话机器人云端服务

当前版本：`v2.1.3-phase2-stable`，阶段二稳定收尾版。

本仓库是 VPS 云端服务。阶段二接收 ESP32-S3 上传的 PCM 音频，返回识别文本、回答文本和可播放 PCM 音频，用于验证 OLED 显示和 MAX98357A 播放闭环。

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

菜单支持查看配置、随机或手动修改 WebSocket 令牌、修改 WebSocket 端口、修改 AI API Key、查看状态、日志二级菜单、停止/启动/重启 WebSocket 服务、卸载服务、一键更新。更新分为“保留数据更新”和“不保留运行数据更新”；当前 `v2.1.3-phase2-stable` 支持从 `v2.0.1-phase2`、`v2.0.2-phase2` 和 `v2.1.x` 保留 `.env` 与 `runtime/` 更新，其他跨度会在菜单中提示先备份或改用不保留运行数据更新。

日志二级菜单包含：日志保留时间、实时日志、关闭日志、开启日志。日志保留时间里可以选择保留 7 天、3 天或 1 天；默认保留 7 天，旧日志会自动清理，避免长期占用 VPS 空间。

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
APP_VERSION=v2.1.3-phase2-stable
```

阶段二会把本轮语音解析文本写入 `CONVERSATION_DIR` 下的临时文本文件，回复逻辑读取该文件后立即删除，不保留历史上下文。`SAVE_DEBUG_WAV=true` 时会把每轮录音保存到 `DEBUG_AUDIO_DIR`，用于排查麦克风/I2S 问题。默认 ASR/TTS 是阶段二测试实现；`LLM_PROVIDER=deepseek` 且配置 `DEEPSEEK_API_KEY` 后会调用 DeepSeek 普通非流式接口。

## 配套固件

推荐使用配套固件版本：[v2.1.2-display-stable](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.2-display-stable)。本次 `v2.1.3` 会忽略录音结束后的残余 PCM 包，避免把无害尾包发成云端错误；固件 `v2.1.2` 同步加入兼容保护，避免旧云端错误卡住 OLED。

## 本地测试

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

Docker 构建：

```bash
docker build -t esp32-ai-voice-cloud:phase2 .
```
