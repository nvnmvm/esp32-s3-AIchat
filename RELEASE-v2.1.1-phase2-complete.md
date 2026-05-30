# v2.1.1-phase2-complete

阶段二完善版云端脚本修正版。本版本专门补齐 VPS 端安装/部署后的版本号输出，方便确认下载到的代码版本和容器实际运行版本。

## 本次改动

- `install-debian.sh` 和 `install-ubuntu.sh` 在拉取代码后输出：
  - `Downloaded cloud code version`
  - `Git code version`
  - `Default APP_VERSION`
- `deploy.sh` 在部署完成后输出：
  - `Configured APP_VERSION`
  - `Git code version`
  - `Running /health version`
- README 和阶段二文档补充部署完成后需要记录的版本信息。

## 为什么需要这个版本

VPS 端下载脚本和 Docker 容器运行版本可能因为 tag、main 分支、缓存或更新方式不同而不一致。本版本把“下载到的代码版本”和“容器实际运行版本”都打印出来，方便排查部署是否使用了预期版本。

## 更新兼容性

- 可保留数据更新：`v2.0.1-phase2`、`v2.0.2-phase2`、`v2.1.x`。
- 其他旧版本或未知版本：建议先备份 `.env` 和 `runtime/`，再选择不保留运行数据更新。

## 下载

- [下载云端 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.1-phase2-complete.zip)
- [下载云端 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.1-phase2-complete.tar.gz)

## 云端版本一键下载

| 云端版本 | 阶段/用途 | ZIP 下载 | TAR.GZ 下载 | 配套固件 |
| --- | --- | --- | --- | --- |
| `v2.1.1-phase2-complete` | 阶段二完善版云端脚本修正版，推荐使用 | [下载 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.1-phase2-complete.zip) | [下载 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.1-phase2-complete.tar.gz) | [固件 v2.1.0-phase2-complete](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.0-phase2-complete) |
| `v2.1.0-phase2-complete` | 阶段二完善版 | [下载 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.0-phase2-complete.zip) | [下载 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.0-phase2-complete.tar.gz) | [固件 v2.1.0-phase2-complete](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.0-phase2-complete) |
| `v2.0.1-phase2` | 阶段二云端对话文件修正版 | [下载 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.0.1-phase2.zip) | [下载 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.0.1-phase2.tar.gz) | [固件 v2.0.2-phase2](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.0.2-phase2) |
| `v2.0.0-phase2` | 阶段二语音/屏幕闭环初版 | [下载 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.0.0-phase2.zip) | [下载 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.0.0-phase2.tar.gz) | [固件 v2.0.0-phase2](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.0.0-phase2) |
| `v1.0.0-phase1` | 阶段一 WebSocket 通信打通版 | [下载 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v1.0.0-phase1.zip) | [下载 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v1.0.0-phase1.tar.gz) | [固件 v1.0.0-phase1](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v1.0.0-phase1) |

## 配套固件

固件无新增代码要求，继续使用：[v2.1.0-phase2-complete](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.0-phase2-complete)
