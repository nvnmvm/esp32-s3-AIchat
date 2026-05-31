# 阶段三云端说明：session 文件化 + Vosk ASR + AI 回答 + edge-tts

阶段三在阶段二 WebSocket + PCM 闭环上继续推进，不推翻 ESP32 端协议。ESP32 仍然上传 16 kHz、16-bit、mono PCM 音频块，云端完成录音落盘、ASR、AI 回复、TTS 合成后，把文本和可播放 PCM 音频发回 ESP32。

## 目标链路

1. ESP32 唤醒后开始录音，并通过 WebSocket 持续上传 PCM。
2. 云端把本轮 PCM 保存为 WAV：`runtime/session/录音/*.wav`。
3. 云端用 Python ASR provider 转写音频，并保存文本：`runtime/session/录音转文字/*.txt`。
4. 云端把转写文本交给 AI API，回答保存为：`runtime/session/ai回答的文本/*.txt`。
5. 云端把回答文本发给 ESP32，OLED 从右向左滚动显示。
6. 云端用 TTS 合成 16 kHz PCM，ESP32 通过 MAX98357A 播放。

## session 目录

默认目录结构：

```text
runtime/session/
├── 录音/
├── 录音转文字/
└── ai回答的文本/
```

默认 `SESSION_RETENTION_DAYS=1`，服务在每轮录音处理前清理超过保留天数的 session 文件。可以通过 `sudo bash manage.sh` 的 `Session file retention` 菜单选择 1、3、7 或 30 天。

## ASR/TTS 方案

当前默认方案按“1 核 1G VPS 优先跑通”的原则选择：

| 模块 | 默认方案 | 原因 |
| --- | --- | --- |
| ASR | Vosk small 中文模型 | 本地离线，资源占用低，适合短语音 |
| TTS | edge-tts + miniaudio 转 PCM | 不占 VPS 推理资源，中文音色自然，镜像体积比内置 ffmpeg 小 |
| AI | DeepSeek/OpenAI-compatible Chat Completions | `.env` 配置 API key 后启用；无 key 时走本地阶段三测试回复 |

可选替代：

- `ASR_PROVIDER=phase2`：不做真实识别，只返回测试文本，适合调试硬件录音和屏幕。
- `ASR_PROVIDER=auto`：优先 Vosk，失败后回退测试文本。
- `TTS_PROVIDER=tone`：返回测试提示音，适合无网络或只想排查 ESP32 播放链路时使用。
- 全本地 TTS 可后续接 Piper；1 核 1G 上先不作为默认值。

## 关键配置

```env
ASR_PROVIDER=vosk
TTS_PROVIDER=edge
LLM_PROVIDER=phase3
AI_API_KEY=
DEEPSEEK_API_KEY=
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-chat

SESSION_DIR=runtime/session
SESSION_RECORDINGS_DIR=runtime/session/录音
SESSION_TRANSCRIPTS_DIR=runtime/session/录音转文字
SESSION_ANSWERS_DIR=runtime/session/ai回答的文本
SESSION_RETENTION_DAYS=1

VOSK_MODEL_DIR=runtime/models/vosk-model-small-cn-0.22
VOSK_MODEL_URL=https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
VOSK_AUTO_DOWNLOAD=true
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
FFMPEG_BIN=ffmpeg
ANSWER_MAX_CHARS=800
TTS_MAX_CHARS=500
```

部署脚本会默认写入这些值。首次使用 Vosk 时，如果模型目录不存在且 `VOSK_AUTO_DOWNLOAD=true`，服务会自动下载 small 中文模型到 `runtime/models/`。TTS 默认用 `miniaudio` 把 edge-tts 的 MP3 转成 ESP32 可播放的 16 kHz PCM；`FFMPEG_BIN` 只作为可选兜底。

## WebSocket 协议

ESP32 到云端保持阶段二协议：

```json
{"type":"start_record"}
```

随后上传二进制 PCM 音频块，录音完成发送：

```json
{"type":"finish_record"}
```

云端返回：

```json
{"type":"status","text":"识别中...","state":"asr","turn_id":1}
{"type":"asr_text","text":"...","turn_id":1,"transcript_file":"...txt"}
{"type":"status","text":"思考中...","state":"thinking","turn_id":1}
{"type":"answer_text","text":"...","turn_id":1,"answer_file":"...txt","answer_chars":120,"truncated":false}
{"type":"status","text":"语音合成中...","state":"tts","turn_id":1}
{"type":"audio_start","sample_rate":16000,"format":"pcm_s16le"}
```

`audio_start` 后发送二进制 PCM 音频块，最后发送：

```json
{"type":"audio_end"}
```

ESP32 阶段二显示逻辑已经能处理 `answer_text` 和 `audio_start/audio_end`，因此当前阶段三不要求修改固件协议。

## 手动 ASR 脚本

如果需要单独把某个 WAV 转写成 txt：

```bash
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav
```

默认输出到 `runtime/session/录音转文字/xxx.txt`。也可以指定 provider：

```bash
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav --provider vosk
```

## 验证

本地测试：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

部署后检查：

```bash
curl -fsS http://127.0.0.1:8000/health
cd /opt/esp32-ai-voice-cloud && docker compose logs -f
```

`/health` 会显示当前 ASR、LLM、TTS provider、session 目录和保留天数。
