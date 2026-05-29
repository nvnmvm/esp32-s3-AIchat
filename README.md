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

## 部署完成后常用命令

一键部署完成后，终端会直接打印下面这些重要信息：

- ESP32-S3 固件需要填写的 `WS_HOST`、`WS_PORT`、`WS_TOKEN`。
- 云端配置文件位置：`/opt/esp32-ai-voice-cloud/.env`。
- VPS 快捷管理菜单命令。

最常用的是这个菜单：

```bash
sudo bash /opt/esp32-ai-voice-cloud/manage.sh
```

菜单可以修改 WebSocket 端口、WebSocket 令牌、AI API Key，也可以重启服务、查看状态、查看日志和运行诊断。

其他常用命令：

```bash
sudo bash /opt/esp32-ai-voice-cloud/scripts/doctor.sh
cd /opt/esp32-ai-voice-cloud && docker compose ps
cd /opt/esp32-ai-voice-cloud && docker compose logs -f
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
- 询问 WebSocket 服务端口，默认 `8000`，可以自定义。
- 询问 AI API Key，阶段一可以留空，后续阶段会使用。
- 创建 `.env` 配置文件。
- 检查本机防火墙；如果 `ufw` 或 `firewalld` 正在运行，会自动放行你选择的 TCP 端口。
- 执行 `docker compose up -d --build` 启动服务。
- 给容器配置健康检查，方便后续排查服务是否正常。

注意：脚本只能检查 VPS 系统内部防火墙，不能自动修改云平台安全组。阿里云、腾讯云、AWS 等控制台里的安全组仍需要手动放行你选择的 TCP 端口。

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

随后会继续询问端口和 AI API Key：

```text
Enter WebSocket server port [8000]:
Enter AI API key [optional, press Enter to skip]:
```

阶段一不使用 AI API Key，可以直接回车跳过。后续接入 AI 对话时，AI API Key 只保存在云端 `.env`，不写入 ESP32 固件。

部署完成后，终端会打印类似信息：

```text
Deployment complete.

=== ESP32 firmware config ===
WebSocket URL: ws://你的VPS公网IP:你选择的端口/ws
WebSocket token: 生成或自定义的令牌
Set ESP32 WS_HOST to: 你的VPS公网IP
Set ESP32 WS_PORT to: 你选择的端口
Set ESP32 WS_TOKEN to: 生成或自定义的令牌

=== VPS common commands ===
Cloud config file: /opt/esp32-ai-voice-cloud/.env
Open management menu: sudo bash /opt/esp32-ai-voice-cloud/manage.sh
Run health doctor: sudo bash /opt/esp32-ai-voice-cloud/scripts/doctor.sh
View service status: cd /opt/esp32-ai-voice-cloud && docker compose ps
View logs: cd /opt/esp32-ai-voice-cloud && docker compose logs -f
```

把这些值填入 ESP32-S3 固件项目的 `include/config.h`。

云端配置文件位置：

```text
/opt/esp32-ai-voice-cloud/.env
```

以后要修改 WebSocket 端口、WebSocket 令牌或 AI API Key，可以直接运行快捷菜单：

```bash
sudo bash /opt/esp32-ai-voice-cloud/manage.sh
```

## ESP32-S3 固件需要修改的配置

在固件仓库中修改：

```c
#define WIFI_SSID "你的WiFi名称"
#define WIFI_PASSWORD "你的WiFi密码"
#define WS_HOST "你的VPS公网IP或域名"
#define WS_PORT 8000
#define WS_TOKEN "云端部署时生成或自定义的令牌"
```

说明：AI API Key 只放云端 `.env`，不要写进 ESP32-S3 固件。

## 防火墙和安全组

VPS 必须放行云端部署时选择的 TCP 端口。

如果使用云服务器，还需要在云平台安全组里放行同一个端口。

如果 VPS 本机启用了 `ufw`，可以运行：

```bash
sudo ufw allow 8000/tcp
```

如果部署时选择了其他端口，把 `8000` 改成实际端口。

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

## 运行诊断

如果部署后 ESP32-S3 连不上，可以先在 VPS 上运行诊断脚本：

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash scripts/doctor.sh
```

诊断脚本会检查：

- Docker 和 Docker Compose 是否可用。
- 项目目录和 `.env` 是否存在。
- 容器状态。
- `http://127.0.0.1:端口/health` 是否可访问。
- 你选择的 TCP 端口是否正在监听。
- 本机防火墙状态。

注意：云平台安全组无法从 VPS 内部自动检查，仍然需要去云服务器控制台确认对应 TCP 端口已放行。

## 快捷管理菜单

部署完成后，可以随时运行：

```bash
sudo bash /opt/esp32-ai-voice-cloud/manage.sh
```

菜单可以完成：

- 查看当前 `.env` 配置。
- 修改 WebSocket 端口。
- 随机生成或自定义 WebSocket 令牌。
- 修改或清空 AI API Key。
- 重启 Docker 服务。
- 查看容器状态和 `/health`。
- 查看日志。
- 运行 `scripts/doctor.sh` 诊断。

修改端口后，脚本会尝试放行 VPS 本机防火墙，但云平台安全组仍然需要手动放行新端口。修改 WebSocket 端口或令牌后，也要同步修改 ESP32-S3 固件的 `include/config.h`。

## 一键卸载

如果以后想从 VPS 上移除本项目，可以复制下面一整行执行：

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/uninstall.sh -o uninstall.sh && sudo bash uninstall.sh
```

默认卸载内容：

- 停止并删除本项目的 Docker 容器。
- 删除 `/opt/esp32-ai-voice-cloud` 项目目录。
- 保留 Docker 本身，避免影响同一台 VPS 上的其他 Docker 服务。

如果确认这台 VPS 不再需要 Docker，可以使用：

```bash
sudo bash uninstall.sh --remove-docker
```

如果想同时删除本项目本地构建出来的 Docker 镜像，可以使用：

```bash
sudo bash uninstall.sh --remove-images
```

## 手动部署方式

如果不想使用一键安装脚本，也可以手动部署。

### 方法一：使用 git clone

适合服务器已经安装 `git`，并且希望以后用 `git pull` 更新项目的用户。

复制下面整段命令：

```bash
git clone https://github.com/nvnmvm/esp32-s3-AIchat.git
cd esp32-s3-AIchat
cp .env.example .env
sed -i 's/^WS_TOKEN=.*/WS_TOKEN=请改成你自己的WebSocket令牌/' .env
docker compose up -d --build
```

### 方法二：下载 GitHub Release 源码包

适合不想在服务器上使用 `git`，只想下载一个固定版本压缩包后手动配置的用户。

1. 打开 Release 页面：

```text
https://github.com/nvnmvm/esp32-s3-AIchat/releases
```

2. 进入 `v1.0.0-phase1`，下载 `Source code (zip)` 或 `Source code (tar.gz)`。

3. 把压缩包上传到 VPS，例如：

```bash
scp esp32-s3-AIchat-*.zip root@你的VPS公网IP:/root/
```

4. 在 VPS 上解压并进入项目目录。

如果下载的是 zip：

```bash
sudo apt-get update
sudo apt-get install -y unzip docker.io docker-compose-plugin
unzip esp32-s3-AIchat-*.zip
cd esp32-s3-AIchat-*
```

如果下载的是 tar.gz：

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
tar -xzf esp32-s3-AIchat-*.tar.gz
cd esp32-s3-AIchat-*
```

5. 创建 `.env` 并启动服务：

```bash
cp .env.example .env
sed -i 's/^WS_TOKEN=.*/WS_TOKEN=请改成你自己的WebSocket令牌/' .env
sudo ufw allow 8000/tcp || true
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8000/health
```

如果使用云服务器，还要在云平台安全组里手动放行实际 TCP 端口。

如果不想用 `sed`，也可以手动编辑 `.env`：

```env
SERVER_PORT=8000
WS_TOKEN=你的WebSocket令牌
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=你的AI API Key，可以为空
LOG_LEVEL=INFO
LOG_PAYLOADS=false
MAX_WS_MESSAGE_BYTES=1048576
APP_VERSION=v1.0.0-phase1
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

## 工程化说明

本仓库阶段一已经补齐以下基础工程能力，后续阶段会继续沿用：

- `tests/`：云端服务的基础自动化测试。
- `.github/workflows/ci.yml`：GitHub Actions 会执行 Python 测试、Shell 脚本语法检查和 Docker 构建。
- Docker healthcheck：容器会定期检查 `/health`。
- `manage.sh`：部署后的快捷管理菜单，可修改端口、令牌和 AI API Key。
- `scripts/doctor.sh`：部署后的 VPS 自诊断脚本。
- `SECURITY.md`：令牌、日志和消息大小限制说明。
- `MAX_WS_MESSAGE_BYTES`：限制单条 WebSocket 消息大小，避免异常大包拖垮服务。
- `LOG_PAYLOADS=false`：默认不把消息正文写进日志，减少隐私泄露风险。

更完整的成熟度分析和后续改进计划见：

```text
docs/maturity-roadmap.md
```

## 常见问题

### ESP32-S3 连不上 WebSocket

先检查：

- VPS 公网 IP 是否正确。
- ESP32-S3 固件里的 `WS_TOKEN` 是否和云端 `.env` 里的 `WS_TOKEN` 完全一致。
- VPS 防火墙和云平台安全组是否放行云端实际端口。
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
- `phase-2`：音频采集上传，云端保存和识别测试。
- `phase-3`：ASR、LLM、TTS 和 ESP32 播放闭环。
- `phase-4`：流式优化、稳定性和工程化增强。

## GitHub 版本管理方式

后续每完成一个阶段，会按下面方式管理两个仓库：

- `main` 分支：始终保存当前最新可用版本。
- `phase-1`、`phase-2`、`phase-3`、`phase-4` 分支：用于对应阶段开发和修复。
- `v1.0.0-phase1`、`v2.0.0-phase2`、`v3.0.0-phase3`、`v4.0.0-phase4` 标签：用于固定每个阶段完成时的代码。
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
