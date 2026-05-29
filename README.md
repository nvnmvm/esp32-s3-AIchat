# ESP32-S3 AI 对话机器人云端服务

这是 ESP32-S3 AI 对话机器人“阶段一通信打通版”的云端项目。

本阶段只验证 ESP32-S3 和 VPS 之间的 WebSocket 双向通信，不接入麦克风、喇叭、ASR、AI 大模型或 TTS。

## 功能

- 提供 `GET /health` 健康检查接口。
- 提供 `WebSocket /ws?token=你的令牌&device_id=设备ID` 连接入口。
- 支持接收文本和二进制数据。
- 收到 ESP32-S3 发来的数据后原样返回，用于 echo 测试。
- 通过 `WS_TOKEN` 校验 WebSocket 连接，避免任何人随便连接。
- 部署时可以选择随机生成 WebSocket 令牌，也可以自定义令牌。

## 仓库地址

云端项目：

```bash
https://github.com/nvnmvm/esp32-s3-AIchat.git
```

ESP32-S3 固件项目：

```bash
https://github.com/nvnmvm/esp32-s3-AIchat-firmware.git
```

## Debian VPS 一键部署

适用于 Debian 系统的 VPS。

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-debian.sh -o install-debian.sh
sudo bash install-debian.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

## Ubuntu VPS 一键部署

适用于 Ubuntu 系统的 VPS。

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh
sudo bash install-ubuntu.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

## 自动识别系统的旧入口

如果你不确定 VPS 是 Debian 还是 Ubuntu，也可以使用自动识别脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh
sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

这个入口会读取 `/etc/os-release`，然后自动调用 Debian 或 Ubuntu 安装脚本。

## 安装脚本会做什么

安装脚本会自动完成：

- 检查系统是否为 Debian 或 Ubuntu。
- 安装 `curl`、`git`、`openssl`、`gnupg` 等基础工具。
- 安装 Docker 和 Docker Compose 插件。
- 优先使用系统自带 apt 源里的 Docker 包。
- 如果系统源没有合适的 Docker Compose 插件，会自动切换到 Docker 官方 apt 源。
- 克隆或更新本项目到 `/opt/esp32-ai-voice-cloud`。
- 询问 WebSocket 令牌生成方式。
- 创建 `.env` 配置文件。
- 执行 `docker compose up -d --build` 启动服务。

## 部署过程中的令牌选择

运行安装脚本后，会出现：

```text
Choose WebSocket token mode:
1) Random token
2) Custom token
Select [1]:
```

直接回车会随机生成一个令牌。

如果输入 `2`，可以手动设置自己的 WebSocket 令牌。

部署完成后，终端会打印类似信息：

```text
Deployment complete.
WebSocket URL: ws://你的VPS公网IP:8000/ws
WebSocket token: 生成或自定义的令牌
Set ESP32 WS_HOST to: 你的VPS公网IP
Set ESP32 WS_PORT to: 8000
Set ESP32 WS_TOKEN to: 生成或自定义的令牌
```

把这些值填入 ESP32-S3 固件项目的 `include/config.h`。

## ESP32-S3 固件需要修改的配置

在固件仓库中修改：

```c
#define WIFI_SSID "你的WiFi名称"
#define WIFI_PASSWORD "你的WiFi密码"
#define WS_HOST "你的VPS公网IP或域名"
#define WS_PORT 8000
#define WS_TOKEN "云端部署时生成或自定义的令牌"
#define AI_API_KEY "你的AI API Key"
```

说明：阶段一暂时不会使用 `AI_API_KEY`，它只是提前保留给后续 AI 对话阶段。

## 防火墙和安全组

VPS 必须放行 TCP `8000` 端口。

如果使用云服务器，还需要在云平台安全组里放行 `8000`。

如果 VPS 本机启用了 `ufw`，可以运行：

```bash
sudo ufw allow 8000/tcp
```

## 查看服务状态

进入项目目录：

```bash
cd /opt/esp32-ai-voice-cloud
```

查看容器：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f
```

正常情况下，ESP32-S3 连接后会看到类似日志：

```text
ESP32 connected
Received text ...
Echoed text ...
```

## 手动部署方式

如果不想使用一键安装脚本，也可以手动部署：

```bash
git clone https://github.com/nvnmvm/esp32-s3-AIchat.git
cd esp32-s3-AIchat
cp .env.example .env
docker compose up -d --build
```

然后修改 `.env`：

```env
SERVER_PORT=8000
WS_TOKEN=你的WebSocket令牌
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=后续AI阶段使用
LOG_LEVEL=INFO
```

## 常见问题

### ESP32-S3 连不上 WebSocket

先检查：

- VPS 公网 IP 是否正确。
- ESP32-S3 固件里的 `WS_TOKEN` 是否和云端 `.env` 里的 `WS_TOKEN` 完全一致。
- VPS 防火墙和云平台安全组是否放行 `8000`。
- 云端容器是否正在运行：`docker compose ps`。

### Docker 安装失败

脚本会先尝试系统 apt 源，再尝试 Docker 官方 apt 源。

如果仍失败，通常是 VPS 系统源不可用、DNS 不通或系统版本太旧。建议先运行：

```bash
sudo apt-get update
```

确认系统软件源正常。

### 想重新生成 WebSocket 令牌

重新运行部署脚本即可：

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash ./deploy.sh
```

然后把新令牌同步修改到 ESP32-S3 固件的 `include/config.h`。
