# 工程成熟度路线图

本项目会按阶段迭代，但每个阶段都要保持可部署、可诊断、可回滚。

## 成熟项目需要具备什么

一个可长期维护的 ESP32-S3 AI 对话机器人项目，至少需要下面几类能力：

- 部署可靠：一键安装、重复执行不破坏已有配置、可卸载、可诊断。
- 配置清晰：所有需要用户修改的云端值集中在 `.env`，固件值集中在本地 `include/config.h`。
- 安全默认值：必须有 WebSocket 令牌、默认不记录消息正文、限制单条消息大小。
- 可观测：健康检查、容器状态、日志、端口和防火墙检查。
- 自动验证：云端测试、脚本语法检查、Docker 构建检查、固件编译检查。
- 版本可追溯：每个阶段都有 tag、Release 和对应 README。
- 阶段边界清楚：阶段一只做通信，阶段二再做音频，阶段三再接 AI、ASR 和 TTS。

## 阶段一已经补齐

- `install-debian.sh` / `install-ubuntu.sh`：区分系统的一键部署脚本。
- `deploy.sh`：生成或填写 WebSocket 令牌，选择端口，填写 AI API Key，创建 `.env`，启动 Docker 服务。
- `manage.sh`：部署后的快捷管理菜单，可修改端口、令牌和 AI API Key。
- `uninstall.sh`：一键卸载本项目，默认保留 Docker。
- `scripts/doctor.sh`：部署后诊断 Docker、健康接口、端口和本机防火墙。
- Docker healthcheck：容器自动检查 `/health`。
- `MAX_WS_MESSAGE_BYTES`：限制 WebSocket 单条消息大小。
- `LOG_PAYLOADS=false`：默认不记录消息正文。
- `tests/`：云端基础自动化测试。
- `.github/workflows/ci.yml`：云端 CI，检查测试、Shell 脚本和 Docker 构建。
- `SECURITY.md`：令牌、日志和消息大小限制说明。

## 固件侧已经补齐

- 开机检查 WiFi、VPS 地址和 WebSocket 令牌是否仍是占位值。
- 配置错误时停止联网，并在串口打印明确提示。
- WebSocket 自动重连和心跳保持。
- 固件仓库 CI 会执行 PlatformIO 编译检查。

## 后续阶段再做

### 阶段二

- ESP32-S3 采集音频并按固定分片上传。
- 云端接收二进制音频帧，并记录设备、序号、时间戳和大小。
- 增加音频帧大小、采样率和上传频率的配置。
- 增加更完整的 WebSocket 协议文档。

### 阶段三

- 接入 ASR、AI 对话和 TTS。
- 增加任务队列，避免单个连接阻塞整个服务。
- 增加对话状态管理和超时清理。

### 阶段四

- 支持 HTTPS/WSS 反向代理部署。
- 增加监控指标、错误告警和更细的日志字段。
- 优化流式传输、延迟、重连恢复和长期运行稳定性。
