# ESP32-S3 AI 对话云端 v3.0.2

版本：`v3.0.2-menu-asr`

## 定位

3.0.2 是 3.0.1 的菜单与模型配置成熟化版本。它不改变“一问一答、非流式”的主架构，重点解决安装后难配置、多个 API 难管理、默认模型不清晰、ASR 策略不可见的问题。

## 安装到配置流程

1. 执行 `install.sh` 或 `deploy.sh`。
2. 设置 WebSocket token 和服务端口。
3. 选择模型配置方式：
   - 跳过：后续在 `manage.sh` 里配置。
   - 配置一个：添加后立即成为默认模型。
   - 配置多个：全部写入 `runtime/config/models.json`，最后可以按编号选择默认模型。
4. 选择用途：
   - `LLM 对话模型（AI 对话模型）`
   - `ASR 语音识别模型`
5. 选择默认厂商或其他厂商。
6. 默认厂商填写备注、API key、模型名；其他厂商额外填写 AI 调用网站 / base URL。
7. 启动容器并用 `/health` 验证当前 ASR chain、模型配置和服务状态。

## 快捷菜单

一级菜单：

```text
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

模型相关菜单：

```text
模型与语音
1) Dashboard summary
2) LLM 对话模型（AI 对话模型）
3) ASR 语音识别模型
4) Deployed models
5) ASR strategy and default
6) TTS settings
7) View model config
0) 返回
```

LLM 和 ASR 都支持：

- 查看已部署模型。
- 增加模型。
- 按编号切换默认模型。
- 按编号删除模型。

ASR 额外支持策略切换：

- 云端优先：`configured_asr -> vosk -> phase2`
- 本地优先：`vosk -> configured_asr -> phase2`
- 多模态优先：`configured_asr -> qwen_dashscope -> vosk -> phase2`
- 离线模式：`vosk -> phase2`

## 配置文件原则

- `.env` 放部署级开关和默认策略。
- `runtime/config/models.json` 放可读、可改、可菜单维护的模型条目。
- 模型条目使用 `llm-001`、`asr-001` 这类编号，便于脚本切换。
- API key 只放在 VPS 的 `runtime/` 或 `.env`，不提交 Git。
- 默认列表只提供常见厂商；其他 OpenAI-compatible 地址可手动填写，扩大脚本适用范围。

## 验收项

- `bash scripts/smoke_manage.sh` 通过。
- `curl -fsS http://127.0.0.1:$SERVER_PORT/health` 返回 `asr_strategy` 和 `asr_provider_chain`。
- `manage.sh > 网络与安全` 默认遮蔽 token。
- `manage.sh > 模型与语音 > LLM 对话模型（AI 对话模型）` 可添加、切换、删除模型。
- `manage.sh > 模型与语音 > ASR 语音识别模型` 可添加、切换、删除模型并切换 ASR 策略。
