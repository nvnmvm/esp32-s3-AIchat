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

复制下面一整行执行：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-debian.sh -o install-debian.sh && sudo bash install-debian.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

## Ubuntu VPS 一键部署

适用于 Ubuntu 系统的 VPS。

复制下面一整行执行：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install-ubuntu.sh -o install-ubuntu.sh && sudo bash install-ubuntu.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

## 自动识别系统的旧入口

如果你不确定 VPS 是 Debian 还是 Ubuntu，也可以使用自动识别脚本：

复制下面一整行执行：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh && sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

这个入口会读取 `/etc/os-release`，然后自动调用 Debian 或 Ubuntu 安装脚本。

注意：不要把 `curl ... -o install.sh` 和 `sudo bash install.sh ...` 直接用空格拼在一起；如果不用上面的一行命令，就必须分两次执行。

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
- 检查本机防火墙；如果 `ufw` 或 `firewalld` 正在运行，会自动放行 TCP `8000`。
- 执行 `docker compose up -d --build` 启动服务。

注意：脚本只能检查 VPS 系统内部防火墙，不能自动修改云平台安全组。阿里云、腾讯云、AWS 等控制台里的安全组仍需要手动放行 TCP `8000`。

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

如果不想使用一键安装脚本，也可以手动部署。

最快方式是复制下面整段命令：

```bash
git clone https://github.com/nvnmvm/esp32-s3-AIchat.git
cd esp32-s3-AIchat
cp .env.example .env
sed -i 's/^WS_TOKEN=.*/WS_TOKEN=请改成你自己的WebSocket令牌/' .env
docker compose up -d --build
```

如果不想用 `sed`，也可以手动编辑 `.env`：

```env
SERVER_PORT=8000
WS_TOKEN=你的WebSocket令牌
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=后续AI阶段使用
LOG_LEVEL=INFO
```

手动部署后检查服务：

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/health
```

如果服务器启用了本机防火墙，请手动放行端口：

```bash
sudo ufw allow 8000/tcp
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

## 后续阶段迭代计划

本仓库会和 ESP32-S3 固件仓库一起迭代。

计划按阶段推进：

- `phase-1`：WebSocket 通信打通，只做 echo 测试。
- `phase-2`：接收 ESP32-S3 上传的音频数据，并为后续 ASR 做准备。
- `phase-3`：接入 ASR、AI 对话、TTS，并把回复结果传回 ESP32-S3。

## GitHub 版本管理方式

后续每完成一个阶段，会按下面方式管理两个仓库：

- `main` 分支：始终保存当前最新可用版本。
- `phase-1`、`phase-2`、`phase-3` 分支：用于对应阶段开发和修复。
- `v1.0.0-phase1`、`v2.0.0-phase2`、`v3.0.0-phase3` 标签：用于固定每个阶段完成时的代码。
- GitHub Release：每个标签会发布一个 Release，说明本阶段功能、部署方式、固件配套版本和注意事项。
- README：每个阶段完成时都会同步更新 README；Git tag 会保存当时的 README，所以以后可以回看每个阶段对应的说明。

推荐工作流：

```bash
git checkout -b phase-2
# 开发阶段二
git commit -m "Add phase 2 audio receive service"
git push -u origin phase-2

# 阶段二稳定后合并到 main，并打标签
git checkout main
git merge phase-2
git tag v2.0.0-phase2
git push origin main --tags
```

实际后续我会直接基于这两个仓库继续改，不会重新另起项目。
