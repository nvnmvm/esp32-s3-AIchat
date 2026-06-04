# ESP32-S3 AI 对话机器人云端服务

当前版本：`v3.0.3-config-readiness`。本版本在 3.0.2 多模型菜单基础上，重点修正首次部署路径、无模型运行提示、ASR 自动兜底和模型配置向导。

## 3.0.3 核心变化

- 一键部署默认只配置 WebSocket token 和服务端口，不再强制填写 ASR/LLM API。
- 部署时可选择是否立即进入模型配置向导，默认跳过；后续可在 `manage.sh > 模型与语音 > 首次配置向导` 配置。
- `cloud_first` 在未配置云端 ASR key 时会直接使用 `Vosk -> phase2`，不再先尝试空 key 的 DashScope。
- `/health` 新增 `model_readiness`，显示 `asr_configured`、`llm_configured`、`using_local_fallback` 和 warnings。
- 模型与语音菜单新增“首次配置向导”，原状态查看下移为“查看当前模型状态”。
- 模型相关菜单补齐主要中英文 i18n 文案。
- OLED 默认仍不显示识别文本页面；回答文本直接进入滚动显示。云端默认 `SEND_ASR_TEXT=false`。
- 3.0.3 仍是非流式一问一答方案；流式 ASR / Opus / MCP 不在本版本范围内。

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
APP_VERSION=v3.0.3-config-readiness
```

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
- VAD 阈值和录音限制

## 本地 / VPS 验证

```bash
python -m pip install -r requirements-dev.txt
pytest -q
bash scripts/smoke_manage.sh
```

Docker 构建：

```bash
docker build -t esp32-ai-voice-cloud:3.0.3 .
```
