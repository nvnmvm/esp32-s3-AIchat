# v3.0.2-menu-asr

## 重点

- 新增 8 类快捷菜单：仪表盘、模型与语音、服务控制、日志与诊断、数据与存储、网络与安全、语言、更新与卸载。
- 安装脚本支持配置一个或多个 LLM/ASR API，并支持默认厂商和自定义厂商。
- LLM 菜单改名为 `LLM 对话模型（AI 对话模型）`。
- `runtime/config/models.json` 升级到 v2，增加备注字段，继续使用 `llm-001`、`asr-001` 这类编号。
- 新增 `ASR_STRATEGY`，支持云端优先、本地优先、多模态优先和离线模式。
- 默认遮蔽 WebSocket token 和模型 API key，敏感配置需要二次确认。

## 验证

- `python -m py_compile app/main.py app/providers/asr/factory.py app/core/model_config.py scripts/model_config_cli.py`
- `scripts/model_config_cli.py` 手动新增 LLM/ASR、列表遮蔽 key 验证通过
- `bash scripts/smoke_manage.sh` 需要在 Linux/VPS 上执行

## 升级

```bash
cd /opt/esp32-ai-voice-cloud
sudo bash manage.sh
```

进入 `更新与卸载`，选择保留 `.env` 和 `runtime/` 的更新方式。
