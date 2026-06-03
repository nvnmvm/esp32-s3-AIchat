import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "model_config_cli.py"


def run_cli(config_path, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(config_path), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def test_model_config_cli_adds_remark_and_masks_keys(tmp_path):
    config_path = tmp_path / "models.json"

    llm = run_cli(
        config_path,
        "add-llm",
        "--brand",
        "deepseek",
        "--name",
        "home-default",
        "--remark",
        "客厅默认 AI 对话模型",
        "--base-url",
        "https://api.deepseek.com",
        "--api-key",
        "sk-1234567890",
        "--model",
        "deepseek-chat",
        "--activate",
    ).stdout.strip()
    asr = run_cli(
        config_path,
        "add-asr",
        "--brand",
        "qwen",
        "--provider",
        "qwen_dashscope",
        "--name",
        "home-asr",
        "--remark",
        "客厅默认语音识别",
        "--base-http-api-url",
        "https://dashscope.aliyuncs.com/api/v1",
        "--api-key",
        "sk-asr-1234567890",
        "--model",
        "qwen3-asr-flash",
        "--language",
        "zh",
        "--enable-itn",
        "--activate",
    ).stdout.strip()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert data["active_llm_id"] == llm
    assert data["active_asr_id"] == asr
    assert data["llm_models"][0]["remark"] == "客厅默认 AI 对话模型"
    assert data["asr_models"][0]["remark"] == "客厅默认语音识别"

    listing = run_cli(config_path, "list").stdout
    assert "sk-1234567890" not in listing
    assert "sk-asr-1234567890" not in listing
    assert "remark=客厅默认 AI 对话模型" in listing


def test_model_config_cli_switches_and_deletes(tmp_path):
    config_path = tmp_path / "models.json"
    first = run_cli(
        config_path,
        "add-llm",
        "--brand",
        "deepseek",
        "--base-url",
        "https://api.deepseek.com",
        "--api-key",
        "sk-first",
        "--model",
        "deepseek-chat",
        "--activate",
    ).stdout.strip()
    second = run_cli(
        config_path,
        "add-llm",
        "--brand",
        "qwen",
        "--base-url",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "--api-key",
        "sk-second",
        "--model",
        "qwen-flash",
    ).stdout.strip()

    run_cli(config_path, "switch", "llm", second)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["active_llm_id"] == second

    run_cli(config_path, "delete", "llm", second)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["active_llm_id"] == first
