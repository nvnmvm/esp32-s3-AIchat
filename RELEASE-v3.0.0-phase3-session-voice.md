# v3.0.0-phase3-session-voice

阶段三 session 文件化语音助手版。本版本把阶段二的测试闭环升级为“录音上传 -> 云端 ASR -> AI API 回答 -> 文本落盘 -> TTS 播放”的可部署流程。

## 主要变化

- 新增 `runtime/session/录音`、`runtime/session/录音转文字`、`runtime/session/ai回答的文本` 三目录。
- 每轮 PCM 录音保存为 WAV，ASR 文本和 AI 回答分别保存为 UTF-8 txt。
- 默认 ASR provider 改为 Vosk small 中文模型，支持首次自动下载模型。
- 默认 TTS provider 改为 edge-tts，优先用 Python `miniaudio` 转为 ESP32 可播放的 16 kHz PCM，`ffmpeg` 仅作为可选兜底。
- AI 调用兼容 DeepSeek/OpenAI-compatible `/chat/completions`。
- 管理菜单新增 session 文件保留时间，默认 1 天，可选 1/3/7/30 天。
- 保留阶段二 WebSocket JSON + PCM 协议，ESP32 固件可继续滚动显示回答并播放 PCM。

## 部署要点

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh
sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

更新已有部署前建议备份：

```bash
sudo cp /opt/esp32-ai-voice-cloud/.env /opt/esp32-ai-voice-cloud/.env.bak
sudo tar -C /opt/esp32-ai-voice-cloud -czf /opt/esp32-ai-voice-cloud-runtime-backup.tgz runtime
```

## 验证

```bash
curl -fsS http://127.0.0.1:8000/health
sudo bash /opt/esp32-ai-voice-cloud/manage.sh
```

触发一轮对话后确认：

```bash
find /opt/esp32-ai-voice-cloud/runtime/session -type f | tail
```

应能看到录音 WAV、转写 txt 和 AI 回答 txt。
