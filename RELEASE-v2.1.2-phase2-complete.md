# v2.1.2-phase2-complete

阶段二完善版云端日志菜单修正版。本版本在 `v2.1.1-phase2-complete` 的版本号输出基础上，补齐 VPS 日志保留策略和管理菜单层级。

## 本次改动

- 默认开启文件日志：`LOG_TO_FILE=true`。
- 默认日志目录：`runtime/logs`。
- 默认日志保留时间：`LOG_RETENTION_DAYS=7`，超过 7 天的旧日志会自动删除。
- 云端应用使用按天轮转文件日志，减少 VPS 长期运行占用空间。
- `manage.sh` 一级菜单中的日志相关项合并成 `Logs` 二级菜单。
- 日志二级菜单包含：
  - `Log retention`
  - `Follow realtime logs`
  - `Disable file logs`
  - `Enable file logs`
  - `Show recent Docker logs`
  - `Show recent file logs`
- 日志保留时间是三级菜单，可选：
  - 保留 7 天
  - 保留 3 天
  - 保留 1 天

## 版本号输出

继续保留 `v2.1.1` 的 VPS 部署版本输出能力：

- 下载代码后输出 `Downloaded cloud code version`。
- 部署完成后输出 `Configured APP_VERSION`、`Git code version`、`Running /health version`。

## 下载

- [下载云端 ZIP](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.2-phase2-complete.zip)
- [下载云端 TAR.GZ](https://github.com/nvnmvm/esp32-s3-AIchat/archive/refs/tags/v2.1.2-phase2-complete.tar.gz)

## 常见命令错误

`docker compose logs -f` 是实时日志命令，会持续占用当前终端。看完日志后需要按 `Ctrl+C` 退出，再执行安装或更新命令。

错误示例：

```bash
docker compose logs -fcurl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh
```

正确示例：

```bash
cd /opt/esp32-ai-voice-cloud
docker compose logs -f
# 按 Ctrl+C 退出日志后，再运行：
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh
sudo bash install-ubuntu.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

## 配套固件

固件无新增代码要求，继续使用：[v2.1.0-phase2-complete](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.0-phase2-complete)
