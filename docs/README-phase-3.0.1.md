# Phase 3.0.1 ASR Quality Plan

版本：`v3.0.1-phase3-asr-quality`

## 目标

3.0.1 的目标不是直接追求流式，而是先让一问一答链路成熟：

- 录音准确性可诊断
- ASR provider 可切换和可回退
- LLM / ASR 模型可通过菜单管理
- OLED 不显示识别结果和回答总览页，直接进入回答滚动页
- 回答结束后不因正常重连显示“云端断开”

## ASR 策略

默认策略：

```text
configured_asr -> vosk -> phase2
```

可选策略：

- `qwen_dashscope`：推荐的 3.0.1 文件级云端 ASR。
- `openai_multimodal`：把录音交给可处理音频的多模态大模型转写。
- `vosk`：本地兜底，不依赖 API key。
- `phase2`：硬件链路调试文本，不作为正式识别。

## 模型配置

多模型配置文件：

```text
runtime/config/models.json
```

不提交真实配置，只提交：

```text
config/model_config.example.json
```

设计原则：

- 修改方便：JSON 结构简单，按 `id` 管理。
- 查看方便：`manage.sh` 可以列出已部署模型并脱敏 API key。
- 使用方便：云端启动时读 active id，菜单切换后重建容器即可生效。

## 快捷菜单结构

```text
Large model brands
  Deployed models
    <model id>
      Switch to this model
      Delete this model
  Add LLM dialogue model
  Add ASR transcription model
```

## 录音准确率排查

每轮生成：

- `runtime/session/录音/*.wav`
- `runtime/session/录音转文字/*.txt`
- `runtime/session/ai回答的文本/*.txt`
- `runtime/session/audio_report/*.audio_report.json`
- `runtime/session/audio_report/*.turn_meta.json`

优先检查 `audio_report.verdict`：

- `too_short`：录音太短。
- `mostly_zero`：I2S 声道、接线或麦克风供电问题。
- `too_quiet`：距离太远、声道错误或增益过低。
- `clipped`：增益过大或离麦克风太近。
- `ok`：优先比较 ASR provider 的结果。

## 取舍

3.0.1 不做流式传输。当前协议是录完一轮再处理，文件级 ASR 改动小、稳定、容易回退。流式 ASR、Opus、持续对话记忆和 MCP 放到 3.1。
