# 阶段 4.1 云端：SSE 回答与分句语音流水线

版本：`v4.1.0-streaming-pipeline`

本阶段在 v4 实时会话框架上继续降低“识别完成到首段声音”的等待：ESP32 的 PCM 在录音过程中转发到 Qwen-ASR-Realtime；ASR final 后，云端用 SSE 接收 LLM 增量，把可见文本立即作为 `answer_delta` 返回设备，并按完整句子进入有界 TTS 队列。第一句完成合成后即可播放，后续句可在上一句播放时并行合成。

> 当前仍是可打断半双工，不是带声学回声消除的真全双工。Edge TTS 是“每句话独立合成”，不是供应商原生流式 PCM；这一区别会影响首包延迟的上限。

## 1. 本阶段已经实现

- 协议版本提升到 `400`，增加 `hello`、`turn_start`、`turn_end`、`turn_ready`、`capture_stop`、`asr_partial`、`asr_final`、`turn_cancelled`。
- 保留 `start_record`、`finish_record`、`vad_end`、`asr_text` 等 v3 消息兼容。
- 新增 Qwen-ASR-Realtime WebSocket 适配器，一轮对话使用一个上游 ASR 连接。
- 实时识别不可用、超时或没有最终文本时，自动回退到现有批量 ASR/Vosk 链。
- ASR/LLM/TTS 在后台任务中运行；WebSocket 接收循环可以继续接收 `cancel` 和新一轮 `turn_start`。
- 每个连接保留最近若干轮对话上下文，传入 OpenAI-compatible/DeepSeek LLM。
- LLM 使用 Chat Completions `stream=true` 的 SSE 增量，忽略 `reasoning_content`，并跨分片过滤 `<think>...</think>`。
- 新增 `answer_delta`；ESP32 可在完整回答生成前显示文本。
- 按 `。！？；` 等强标点立即切句；无标点超长文本按软标点或 `LLM_SENTENCE_MAX_CHARS` 切分。
- LLM、句子 TTS、PCM 播放是三个可取消任务，使用有界队列传递数据并形成背压。
- 流中断前已有可用文本时保留部分回答；完全失败且 `LLM_PROVIDER=auto` 时使用测试回答兜底。
- 最终可播报文本受 `TTS_MAX_CHARS` 限制，防止异常超长回答无限占用内存和队列。
- TTS PCM 按 80 ms 节奏下发，避免一次性灌满 ESP32 播放队列，也让取消能快速生效。
- 修正不可安装的 `vosk==0.3.45` 为 `0.3.44`，并显式加入 `websockets` 依赖。
- 删除未被调用的旧转写包装函数和无效的 `VAD_MIN_RECORDING_BYTES` 配置。

## 2. 当前数据流

```mermaid
sequenceDiagram
    participant E as ESP32-S3
    participant C as FastAPI 云端
    participant A as Qwen Realtime ASR
    participant L as LLM
    participant T as TTS

    E->>C: hello(protocol=400)
    C-->>E: hello(capabilities)
    E->>C: turn_start(turn_id)
    C->>A: 建立上游 WebSocket + session.update
    C-->>E: turn_ready
    loop 每 40 ms
        E->>C: PCM s16le 二进制
        C->>A: input_audio_buffer.append(base64)
        A-->>C: transcription.text
        C-->>E: asr_partial
    end
    A-->>C: speech_stopped
    C-->>E: capture_stop
    E->>C: turn_end
    C->>A: session.finish
    A-->>C: transcription.completed
    C-->>E: asr_final
    C->>L: stream=true + 文本 + 最近上下文
    loop LLM SSE 增量
        L-->>C: delta.content
        C-->>E: answer_delta
        C->>C: 去 think + 分句
        C->>T: 已完成句子
        T-->>C: 该句 PCM
        C-->>E: audio_start(仅一次) + PCM(80 ms节奏)
    end
    C-->>E: answer_text + audio_end
```

## 3. 代码结构

当前结构在不破坏 v3 的前提下做了最小可发布改造：

```text
app/
├── main.py                         # WebSocket、会话状态、后台 turn 任务、LLM/TTS
├── core/
│   ├── audio_utils.py              # PCM 质量分析
│   ├── model_config.py             # 模型配置
│   └── vad.py                      # 本地回退 VAD
├── providers/asr/
│   ├── qwen_realtime.py             # Qwen 实时 ASR 会话
│   ├── qwen_dashscope.py             # 批量 Qwen ASR 回退
│   ├── vosk_local.py                 # 离线回退
│   └── factory.py                    # 批量 ASR 策略链
├── providers/llm/
│   └── openai_stream.py              # OpenAI-compatible SSE 解析
└── services/
    └── text_stream.py                # think 过滤、标点分句和长度边界
```

后续建议按下面目录继续拆分，避免 `app/main.py` 再次膨胀：

```text
app/
├── api/ws.py                        # 只负责协议收发和鉴权
├── protocol/messages.py             # v4 消息校验和序列化
├── session/controller.py            # turn 生命周期、取消、超时
├── services/dialog_pipeline.py      # ASR -> LLM -> TTS 流水线
├── providers/asr/
├── providers/llm/
├── providers/tts/
└── observability/metrics.py          # 首包延迟、错误率、队列深度
```

拆分顺序应为：先搬运且保持测试通过，再定义接口，最后替换实现；不要一次同时重写协议和供应商适配器。

## 4. VPS 部署步骤

### 4.1 准备环境

推荐 Ubuntu 22.04/24.04、Docker Engine 和 Docker Compose v2。开放业务端口前，先准备域名和 TLS；生产环境不要让 ESP32 通过明文公网 `ws://` 传输 token 和语音。

```bash
git clone https://github.com/nvnmvm/esp32-s3-AIchat.git
cd esp32-s3-AIchat
cp .env.example .env
openssl rand -hex 32
```

把生成值写到 `.env` 的 `WS_TOKEN`。

### 4.2 配置 Qwen 实时 ASR

在阿里云百炼创建 API Key，确认业务空间所在地域，取得 Workspace ID。北京和新加坡业务空间不能混用域名。

```env
DASHSCOPE_API_KEY=sk-xxxxxxxx
QWEN_REALTIME_ENABLED=true
QWEN_REALTIME_WORKSPACE_ID=ws-xxxxxxxx
QWEN_REALTIME_REGION=cn-beijing
QWEN_REALTIME_MODEL=qwen3-asr-flash-realtime
QWEN_REALTIME_VAD_SILENCE_MS=400
QWEN_REALTIME_CONNECT_TIMEOUT_SECONDS=10
QWEN_REALTIME_FINISH_TIMEOUT_SECONDS=8
```

如果使用阿里云提供的自定义完整地址，可填写 `QWEN_REALTIME_WS_URL`；代码会在没有 `model` 查询参数时自动补上。正常情况下建议只填 Workspace ID 和地域。

官方事件依据：

- [Qwen-ASR Realtime WebSocket 交互流程](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-interaction-process)
- [客户端事件](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-client-events)
- [服务端事件](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events)

### 4.3 配置 LLM 和 TTS

DeepSeek/OpenAI-compatible 示例：

```env
LLM_PROVIDER=auto
DEEPSEEK_API_KEY=sk-xxxxxxxx
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
CONVERSATION_MAX_TURNS=5
LLM_STREAMING_ENABLED=true
LLM_DISABLE_THINKING=true
LLM_MAX_TOKENS=512
LLM_SENTENCE_MAX_CHARS=80

TTS_PROVIDER=edge
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
TTS_PCM_CHUNK_MS=80
TTS_SENTENCE_QUEUE_SIZE=4
```

截至 2026-07-16，DeepSeek 官方模型列表为 `deepseek-v4-flash` 和 `deepseek-v4-pro`，并公告兼容别名 `deepseek-chat` / `deepseek-reasoner` 将于 2026-07-24 15:59 UTC 弃用，因此新部署默认使用 `deepseek-v4-flash`。流式协议是 data-only SSE，并以 `data: [DONE]` 结束；`thinking.type=disabled` 用于语音场景关闭默认思考模式。参考 [DeepSeek 模型与兼容别名说明](https://api-docs.deepseek.com/quick_start/pricing/) 和 [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)。

已有 VPS 不会因为代码默认值变化而自动改写 `.env` 或 `runtime/config/models.json`；升级时必须检查这两个位置，避免仍指向即将弃用的兼容别名。

`.env` 的 `APP_VERSION` 只供管理菜单记录部署版本和判断可保留数据的升级路径，不能覆盖代码版本。`/health.version` 始终报告当前代码版本；`configured_app_version` 报告部署记录，`version_config_matches=false` 表示应通过管理菜单升级或同步该记录后重启。

`CONVERSATION_MAX_TURNS=5` 表示当前 WebSocket 连接最多向 LLM 携带最近 5 轮问答。连接断开后内存上下文会清空，当前版本不会把对话内容长期写入数据库。

### 4.4 启动和检查

```bash
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8000/health | python3 -m json.tool
docker compose logs -f --tail=200
```

健康检查应至少看到：

```json
{
  "ok": true,
  "version": "v4.1.0-streaming-pipeline",
  "phase": "streaming-pipeline",
  "protocol": 400,
  "qwen_realtime": {
    "enabled": true,
    "configured": true,
    "workspace_configured": true
  }
}
```

`configured=false` 不会让服务启动失败，但实际对话会回退到批量 ASR，ESP32 的 `turn_ready.realtime_asr` 也会是 `false`。

### 4.5 使用 Caddy 提供 WSS

示例 `Caddyfile`：

```caddyfile
voice.example.com {
    reverse_proxy 127.0.0.1:8000
    encode zstd gzip
}
```

ESP32 配置改为：

```cpp
#define WS_HOST "voice.example.com"
#define WS_PORT 443
#define WS_USE_SSL true
```

只在防火墙开放 80/443；不要把 8000 直接暴露给公网。正式设备还应校验服务器证书，后续版本再加入设备级短期 token。

## 5. 协议 v4

### 5.1 握手

设备连接后发送：

```json
{"type":"hello","protocol":400,"firmware":"v4.1.0-streaming-pipeline","device_id":"esp32-s3-voice-001"}
```

云端返回能力列表。为了兼容旧固件，连接建立时云端仍先发送 v3 风格的 `status=idle`，只有设备主动发送 `hello` 才返回 v4 握手。

### 5.2 一轮对话

```json
{"type":"turn_start","protocol":400,"turn_id":1,"audio":{"format":"pcm_s16le","sample_rate":16000,"channels":1,"chunk_ms":40}}
```

收到 `turn_ready` 后持续发送 16 kHz、单声道、16-bit little-endian PCM 二进制。服务端 VAD 检测到结尾时返回：

```json
{"type":"capture_stop","reason":"server_vad","turn_id":1}
```

设备停止采集并发送：

```json
{"type":"turn_end","protocol":400,"turn_id":1,"reason":"server_vad"}
```

### 5.3 打断

```json
{"type":"cancel","protocol":400,"turn_id":1,"reason":"barge_in"}
```

云端会取消后台任务、关闭该轮 Qwen 连接并返回 `turn_cancelled`。设备可以紧接着发新的 `turn_start`；所有带 `turn_id` 的旧轮事件都应丢弃。

### 5.4 流式回答与音频

LLM 每产生一段可见文本，云端发送：

```json
{"type":"answer_delta","turn_id":1,"text":"今天北京"}
```

旧固件不认识该消息时会忽略它，仍可依靠最终 `answer_text` 工作。新固件把 delta 追加到 OLED 文本，但只接受当前 `turn_id`。

第一句完成 Edge TTS 后，云端只发送一次：

```json
{"type":"audio_start","turn_id":1,"sample_rate":16000,"format":"pcm_s16le","text":"第一句。"}
```

之后的每句话直接接续发送 PCM 二进制帧，不会重复 `audio_start`。LLM 全部完成后发送最终 `answer_text`；所有句子的 PCM 入队并发送完后再发 `audio_end`。因此设备必须保持播放状态，直到收到并消费完 `audio_end` 队列标记。

取消规则适用于三个阶段：等待 LLM、合成任意句子、发送 PCM。收到 `cancel` 后云端取消 TaskGroup，固件清空播放 generation，旧轮后续事件不能进入新轮。

## 6. 本地验证

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python -m compileall -q app tests
```

SSE、分句、取消和 Qwen 供应商测试使用假的传输，不消耗云 API。上线前还需要用真实设备完成：

1. OLED 在说话时出现 `asr_partial` 文本。
2. 停止说话约 400 ms 后收到 `capture_stop`。
3. 播放过程中再次唤醒，旧音频在 300 ms 量级内停止。
4. 日志中旧 turn 不会覆盖新 turn 的状态。
5. 断开 Qwen 网络后仍能走批量 ASR 回退。
6. OLED 在 `answer_text` 前已显示 `answer_delta`。
7. 两句以上回答在第一句播放时继续生成或合成后续句，句间无明显异常爆音。

## 7. 延迟目标和观测

建议记录：`turn_start`、首个 `asr_partial`、`asr_final`、首个 `answer_delta`、`audio_start` 和首个 PCM。阶段 4.1 的可接受目标：

| 指标 | 目标 |
| --- | ---: |
| 首个局部识别 | 800 ms 内 |
| 说完到 ASR final | 1.2 s 内 |
| ASR final 到首个 answer_delta | 1.0 s 内 |
| ASR final 到首段音频 | 2.0 s 内 |
| 播放打断生效 | 300 ms 内 |

这些是工程验收目标，不是供应商 SLA。实际值受 Wi-Fi、VPS 地域、模型和文本长度影响。

## 8. 下一阶段

按优先级继续：

1. 用真实 Qwen、DeepSeek、VPS/WSS 和 ESP32 做端到端延迟、断线、连续 50 轮和打断验收。
2. 接入供应商原生流式 PCM TTS，和当前 Edge TTS 分句实现做首包延迟及成本对比。
3. 增加首 ASR、首 delta、首 PCM、整轮耗时、队列深度、取消次数和供应商错误指标。
4. 将 `main.py` 拆为 protocol/session/services/providers，并保持现有测试逐步迁移。
5. 增加连接限流、设备独立鉴权、token 轮换和 TLS 证书校验/固定。
6. 真全双工前先评估 AEC；没有回声消除时不要在扬声器播放期间持续上传麦克风。
