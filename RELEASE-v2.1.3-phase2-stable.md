# v2.1.3-phase2-stable

阶段二稳定收尾版。本版本修复录音结束后少量残余 PCM 包导致 ESP32 OLED 固定显示 `云端错误` 的问题。

## 修复内容

- 云端在非录音状态收到残余音频包时，只写入日志，不再向 ESP32 发送 `error`。
- 日志格式：`Ignored stray audio bytes=... device_id=... because session is not recording`。
- `APP_VERSION` 更新为 `v2.1.3-phase2-stable`。
- 管理菜单的一键更新目标版本同步更新为 `v2.1.3-phase2-stable`。

## 为什么要改

阶段二 VAD 判断录音结束后，ESP32 可能还有少量已经发出或正在发送的 PCM 包。旧版本云端会把这些尾包当成严重协议错误，发送：

```text
收到音频，但当前没有 start_record。
```

ESP32 收到该错误后会显示 `云端错误`，导致用户误以为主流程失败。实际上这只是录音结束边界上的残余音频，应该忽略。

## 配套固件

推荐同步更新固件：[v2.1.2-display-stable](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.2-display-stable)

固件 `v2.1.2-display-stable` 会额外忽略旧云端发出的“没有 start_record”无害错误，并让普通错误页 2 秒后自动回到等待唤醒。

## 更新方式

保留数据更新：

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

进入菜单后选择 `Update, preserve data`。

也可以重新下载安装脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh
sudo bash install-ubuntu.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

## 兼容性

`v2.1.3-phase2-stable` 支持从 `v2.0.1-phase2`、`v2.0.2-phase2` 和 `v2.1.x` 保留 `.env` 与 `runtime/` 更新。

## 下载

- [下载云端 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.3-phase2-stable.zip)
- [下载云端 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.3-phase2-stable.tar.gz)
