# v3.0.1-phase3-asr-quality

## 云端

- 新增音频质量报告，定位录音不准的具体原因。
- 新增 ASR provider 回退链路：配置模型优先，Vosk 兜底，phase2 调试。
- 新增 `runtime/config/models.json` 多模型配置和 `scripts/model_config_cli.py`。
- `manage.sh` 增加 Large model brands 菜单，可新增、切换、删除 LLM/ASR 模型。
- `deploy.sh` 部署时可选择添加一个或多个模型。
- 默认不向设备显示 `asr_text` 页面，回答直接进入滚动显示。

## 验收

- `/health` 返回 `asr_provider_chain`、`model_config_exists`、`vosk_model_exists`、`audio_report` 目录。
- `pytest -q` 通过。
- `scripts/inspect_wav.py` 可独立诊断 WAV。
- `scripts/asr_transcribe.py --provider auto/vosk/phase2` 可重跑同一录音。
