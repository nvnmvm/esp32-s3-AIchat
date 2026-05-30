# v2.1.0-phase2-complete

阶段二完善版。本版本用于进入阶段三前的稳定过渡，配套固件同名版本 `v2.1.0-phase2-complete`。

## 主要改进

- 统一云端和固件版本号，两个仓库都使用 `v2.1.0-phase2-complete`。
- 新增 debug WAV：`SAVE_DEBUG_WAV=true` 时，每轮录音保存到 `runtime/audio`。
- `runtime/` 通过 Docker volume 映射到宿主机，便于查看 debug WAV 和运行数据。
- 保留本轮语音转文字临时文件流程：写入 `runtime/conversations`，回复读取后自动删除。
- 新增 DeepSeek 普通非流式问答配置：`LLM_PROVIDER=deepseek` + `DEEPSEEK_API_KEY`。
- `/health` 返回 ASR/LLM/TTS provider、debug WAV、运行目录等诊断信息。
- 快捷管理菜单补齐：令牌、端口、AI API Key、状态、日志、启动、停止、重启、卸载、一键更新。
- 更新菜单区分“保留数据更新”和“不保留运行数据更新”，并提示兼容版本范围。

## 更新兼容性

- 可保留数据更新：`v2.0.1-phase2`、`v2.0.2-phase2`、`v2.1.x`。
- 其他旧版本或未知版本：建议先备份 `.env` 和 `runtime/`，再选择不保留运行数据更新。

## 配套固件

固件 release：[v2.1.0-phase2-complete](https://github.com/nvnmvm/esp32-s3-AIchat-firmware/releases/tag/v2.1.0-phase2-complete)
