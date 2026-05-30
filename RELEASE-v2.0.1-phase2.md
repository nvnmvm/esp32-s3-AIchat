# v2.0.1-phase2

阶段二云端修正版。本版本是 `v2.0.0-phase2` 的后继补丁版本，重点修复上传音频后屏幕状态不明确、云端回复链路不够可诊断的问题。

## 修复和完善

- 增加本轮语音解析文本的临时文件流程：写入 `runtime/conversations`，回复读取后自动删除。
- 云端 `/health` 增加 `conversation_storage` 和 `conversation_dir`，便于 VPS 诊断。
- `finish_record`、VAD 静音结束、录音过大结束统一走同一条处理链路。
- 云端处理异常时返回 `error` JSON，ESP32-S3 OLED 可以显示云端错误。
- 测试覆盖语音轮次返回 `asr_text`、`answer_text`、PCM 音频，以及临时文本文件自动删除。

## 当前边界

- 阶段二仍是闭环验证版本，语音解析为本地测试解析，不调用大模型 token。
- 返回本地测试 PCM 提示音，用于验证 MAX98357A 播放链路。
- 正式 ASR、DeepSeek 对话和 TTS 接入保留到后续阶段。

## 配套固件

请使用固件仓库 release：`v2.0.2-phase2`。
