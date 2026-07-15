# v4.0.0-realtime-foundation

阶段四第一个可发布增量：实时 Qwen ASR、协议 v4、可取消 turn 后台任务、短期会话上下文和 TTS PCM 节奏发送。

## 兼容性

- 云端继续兼容 v3 的 `start_record` / `finish_record`。
- 未配置 Qwen Workspace ID 时自动使用原批量 ASR 回退链。
- 配套固件版本为 `v4.0.0-realtime-foundation`，协议号 `400`。

## 验证

- 完整 Python 依赖可安装，包括 `vosk==0.3.44`。
- 云端自动化测试覆盖 v4 握手、取消和 Qwen 实时事件解析。
- 详细部署和验收步骤见 `docs/README-phase-4.md`。
