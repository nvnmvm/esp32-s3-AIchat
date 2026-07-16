# v4.1.0-streaming-pipeline

阶段 4.1 将 v4 的实时 ASR 与可取消播放框架扩展为 SSE LLM 和句子级 TTS 流水线。

## 主要变化

- OpenAI-compatible/DeepSeek Chat Completions 使用 `stream=true`，解析 data-only SSE 到 `[DONE]`。
- 忽略 `reasoning_content`，并支持跨分片过滤 `<think>...</think>`。
- 增加 `answer_delta` 和 `sentence_tts` 能力声明；旧 v3/v4 客户端可忽略新增事件。
- 按标点和长度上限切句，LLM、TTS、PCM 播放通过有界队列并行运行。
- 第一完成句即可进入 Edge TTS，播放上一句时可合成下一句。
- `cancel` 会同时终止 LLM、TTS 和 PCM 发送；部分流断线时保留已生成的可用回答。
- 保留 `TTS_MAX_CHARS` 总长度保护，避免异常长输出造成无界内存和播放延迟。
- DeepSeek 默认模型更新为 `deepseek-v4-flash`；旧 VPS 的 `.env` 或 `runtime/config/models.json` 需要人工核对模型名。

## 兼容性

- 协议号保持 `400`。
- 继续兼容 `start_record`、`finish_record` 和批量 ASR/Vosk 回退。
- 固件 v4.0 可继续播放，只是不会显示 `answer_delta`；推荐升级到配套固件 v4.1。
- 当前 Edge TTS 是“逐句完整合成”，不是供应商原生 PCM 流。

## 验证

```bash
python -m pytest -q
python -m compileall -q app tests
bash scripts/smoke_manage.sh
docker build -t esp32-ai-voice-cloud:4.1.0 .
```

自动化覆盖 SSE 解析、思考标签跨分片、标点/长度分句、部分流中断、回答长度上限、播放前取消、协议握手和完整模拟语音 turn。真实云密钥、VPS/WSS 和物理硬件仍需按阶段四文档执行验收。
