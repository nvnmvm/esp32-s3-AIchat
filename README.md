# ESP32-S3 AI 对话机器人云端服务

当前版本：`v4.1.0-streaming-pipeline`。

这是阶段 4.1 可发布增量：在 Qwen-ASR-Realtime、协议 v4、可取消 turn 和异步播放基础上，加入 OpenAI-compatible/DeepSeek SSE 回答、`answer_delta`、按标点分句、句子级 Edge TTS 队列和边生成边播放。没有实时供应商配置时仍会自动回退，v3 固件消息继续兼容。

当前是“实时 ASR + 流式 LLM + 分句 TTS + 可打断半双工”。Edge TTS 每句话仍需先完成一次合成，并非供应商原生 PCM 流；没有 AEC，不能宣称真全双工。详细部署、协议、验收和后续拆分计划见 [阶段四开发文档](docs/README-phase-4.md)。

## 一键部署

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh && sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git --clean
```

安装流程会询问：

- WebSocket token：保留、随机生成或手动填写。
- WebSocket 服务端口。
- 是否立即打开首次配置向导：默认跳过。

部署完成后配置模型：

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

进入：

```text
模型与语音 -> 首次配置向导
```

向导会按需询问：

- 模型用途：`ASR 语音识别模型` 或 `LLM 对话模型（AI 对话模型）`。
- 默认厂商或其他厂商：
  - 默认 LLM 厂商：DeepSeek、Qwen / 阿里百炼、豆包 / 火山 Ark、Kimi、OpenAI。
  - 默认 ASR 厂商：Qwen3-ASR-Flash / DashScope，或 OpenAI-compatible 多模态 ASR。
  - 默认厂商只需填备注、API key、模型名。
  - 其他厂商会额外询问 AI 调用网站 / base URL、API key、模型名和备注。

模型配置写入：

```text
runtime/config/models.json
```

示例结构见：

```text
config/model_config.example.json
```

## 快捷菜单

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

当前菜单结构：

```text
ESP32-S3 AI 对话云端管理
1) 仪表盘
2) 模型与语音
3) 服务控制
4) 日志与诊断
5) 数据与存储
6) 网络与安全
7) 语言
8) 更新与卸载
0) 退出
```

`模型与语音` 二级菜单：

```text
1) 首次配置向导
2) 查看当前模型状态
3) LLM 对话模型（AI 对话模型）
4) ASR 语音识别模型
5) 已部署模型
6) ASR 策略与默认值
7) TTS 设置
8) 查看模型配置
0) 返回
```

`LLM 对话模型（AI 对话模型）` 三级菜单：

```text
1) Deployed models
2) Add model
3) Switch default model
4) Delete model
0) 返回
```

`ASR 语音识别模型` 三级菜单：

```text
1) Deployed models
2) Add model
3) Switch default model
4) Delete model
5) ASR strategy
0) 返回
```

## 关键配置

```env
MENU_LANG=zh_CN
ASR_PROVIDER=auto
ASR_STRATEGY=cloud_first
ASR_PRIMARY=configured_asr
ASR_FALLBACK=vosk
ASR_DEFAULT_VENDOR=qwen
LLM_PROVIDER=auto
LLM_DEFAULT_VENDOR=deepseek
MODEL_CONFIG_PATH=runtime/config/models.json
SEND_ASR_TEXT=false
SEND_ANSWER_TEXT=true
LLM_STREAMING_ENABLED=true
LLM_DISABLE_THINKING=true
LLM_MAX_TOKENS=512
LLM_SENTENCE_MAX_CHARS=80
TTS_SENTENCE_QUEUE_SIZE=4
APP_VERSION=v4.1.0-streaming-pipeline
```

这里的 `APP_VERSION` 只供管理菜单记录部署版本和判断升级路径；实际运行代码版本以 `/health.version` 为准。

阶段四实时 ASR 还需要在 `.env` 填写阿里云百炼业务空间：

```env
QWEN_REALTIME_ENABLED=true
QWEN_REALTIME_WORKSPACE_ID=ws-你的业务空间ID
QWEN_REALTIME_REGION=cn-beijing
QWEN_REALTIME_MODEL=qwen3-asr-flash-realtime
QWEN_REALTIME_VAD_SILENCE_MS=400
CONVERSATION_MAX_TURNS=5
```

没有实时 ASR 配置时，服务仍会使用原来的批量 ASR/Vosk 回退链，旧版 `start_record`、`finish_record` 消息也继续兼容。

推荐分工：

- `.env` 放部署级开关、默认策略、端口、token。
- `runtime/config/models.json` 放多个模型条目，适合人工查看和菜单修改。
- 真实 API key 不提交到 Git；菜单和 `/health` 默认只显示遮蔽后的配置摘要。

## ASR 策略

- `cloud_first`：默认。已配置云端 ASR -> Vosk -> phase2 调试兜底。
- 如果未配置任何云端 ASR key，`cloud_first` 会自动变成 Vosk -> phase2，不会先报空 key 错误。
- `local_first`：Vosk -> 已配置云端 ASR -> phase2，适合弱网或控制成本。
- `llm_audio`：已配置多模态 ASR -> Qwen3-ASR-Flash -> Vosk，适合把录音交给多模态大模型处理。
- `offline`：Vosk -> phase2，不调用云端 ASR。

## 运行模式

- 无模型测试：不配置 ASR/LLM，系统仍可启动；ESP32 可测试录音、OLED、喇叭和云端会话链路，回答为 phase3 测试文本。
- 离线识别模式：使用 Vosk，本地优先或离线策略，适合弱网和低成本验证。
- 云端 ASR + 测试回答：只配置 ASR，不配置 LLM，适合先验证识别准确性。
- 完整 AI 对话：配置 ASR 和 LLM，进入真实一问一答模式。

## 音频诊断

查看最近录音和诊断：

```bash
ls runtime/session/录音
ls runtime/session/audio_report
```

单独诊断一个 WAV：

```bash
python scripts/inspect_wav.py runtime/session/录音/xxx.wav
```

对同一 WAV 重新跑 ASR：

```bash
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav --provider phase2
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav --provider vosk
python scripts/asr_transcribe.py runtime/session/录音/xxx.wav --provider auto
```

## Health

```bash
curl -fsS http://127.0.0.1:8000/health
```

`/health` 会返回：

- `asr_strategy`
- `asr_provider_chain`
- `model_readiness`
- `vosk_model_exists`
- `model_config_exists`
- `models` 的脱敏摘要
- `session_dirs.audio_report`
- `llm_streaming_enabled`、`llm_sentence_max_chars`
- `tts_sentence_queue_size`
- VAD 阈值和录音限制

## 本地 / VPS 验证

```bash
python -m pip install -r requirements-dev.txt
pytest -q
bash scripts/smoke_manage.sh
```

Docker 构建：

```bash
docker build -t esp32-ai-voice-cloud:4.1.0 .
```

## 发布说明

- [v4.1 流式管线发布说明](RELEASE-v4.1.0-streaming-pipeline.md)
- [阶段四详细开发与验收文档](docs/README-phase-4.md)
