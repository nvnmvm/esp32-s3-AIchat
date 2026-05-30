# 阶段一 README：WebSocket 通信打通版

阶段一只验证 ESP32-S3 与 VPS 云端之间的 WebSocket 双向通信。

## 功能范围

- `GET /health` 健康检查。
- `WebSocket /ws?token=...&device_id=...` 鉴权连接。
- ESP32-S3 每秒发送一条 `hello from esp32 ...`。
- 云端收到文本或二进制消息后原样 echo。
- ESP32-S3 串口打印云端返回内容。

## 发布版本

- 云端 tag/release：`v1.0.0-phase1`
- 配套固件 tag/release：`v1.0.0-phase1`

## 注意

阶段一不接入麦克风、OLED、ASRPRO、DeepSeek、TTS 或 MAX98357A。后续阶段的代码和 README 不应回写覆盖本阶段留档。
