# v2.0.0-phase2

阶段二语音和屏幕双输出闭环版。

## 新增

- WebSocket 阶段二 JSON + PCM 协议。
- 接收 ESP32-S3 上传的 16 kHz / 16 bit / mono PCM 音频。
- 返回 `status`、`asr_text`、`answer_text`、`audio_start`、`audio_end`。
- 返回本地测试 PCM 音频，用于验证 ESP32-S3 + MAX98357A 播放链路。
- `.env.example` 增加阶段二音频、VAD 和版本配置。
- Debian/Ubuntu 安装脚本增加 `--clean`，用于 VPS 测试前删除阶段一旧部署。
- 增加阶段一和阶段二独立 README 留档。

## VPS 测试

阶段二测试请使用：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh && sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

`--clean` 会先停止旧容器并删除旧的 `/opt/esp32-ai-voice-cloud`，再克隆阶段二代码。

## 配套固件

请使用固件仓库同名 release：`v2.0.0-phase2`。
