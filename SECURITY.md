# 安全说明

阶段一只用于 WebSocket 通信打通，但仍然建议按下面方式部署。

## 必须修改的配置

- `WS_TOKEN` 必须改成随机长令牌，不要使用示例值。
- `ALLOW_EMPTY_TOKEN` 保持为 `false`。
- 只开放必要端口，默认是 TCP `8000`，也可以在部署时改成其他端口。
- 云平台安全组和 VPS 本机防火墙都要检查。
- AI API Key 只放云端 `.env`，不要写入 ESP32 固件。

## 配置文件

云端配置文件：

```text
/opt/esp32-ai-voice-cloud/.env
```

可以通过快捷菜单修改端口、WebSocket 令牌和 AI API Key：

```bash
sudo bash /opt/esp32-ai-voice-cloud/manage.sh
```

ESP32-S3 固件只保留本地 `include/config.h`，仓库只提交 `include/config.example.h` 模板。

## 日志隐私

默认 `LOG_PAYLOADS=false`，云端只记录消息字节数，不记录完整消息内容。

如果排查问题时临时需要记录文本内容，可以在 `.env` 里设置：

```env
LOG_PAYLOADS=true
```

排查完成后建议改回 `false`。

## 消息大小限制

默认 `MAX_WS_MESSAGE_BYTES=1048576`，也就是单条 WebSocket 消息最大 1MB。

阶段二接入音频后，如果需要更大的分片，应优先调整音频分片大小，而不是无限放大这个值。
