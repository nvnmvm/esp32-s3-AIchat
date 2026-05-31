from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EMPTY_MODEL_CONFIG: dict[str, Any] = {
    "version": 1,
    "active_llm_id": "",
    "active_asr_id": "",
    "llm_models": [],
    "asr_models": [],
}


def load_model_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return dict(EMPTY_MODEL_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid model config JSON: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Model config must be a JSON object: {path}")
    merged = dict(EMPTY_MODEL_CONFIG)
    merged.update(data)
    merged["llm_models"] = [item for item in merged.get("llm_models", []) if isinstance(item, dict)]
    merged["asr_models"] = [item for item in merged.get("asr_models", []) if isinstance(item, dict)]
    return merged


def active_item(config: dict[str, Any], section: str) -> dict[str, Any] | None:
    key = "active_llm_id" if section == "llm_models" else "active_asr_id"
    active_id = str(config.get(key) or "")
    items = config.get(section, [])
    if active_id:
        for item in items:
            if str(item.get("id") or "") == active_id and item.get("enabled", True):
                return item
    for item in items:
        if item.get("enabled", True):
            return item
    return None


def masked_config_summary(config: dict[str, Any]) -> dict[str, Any]:
    def mask(item: dict[str, Any]) -> dict[str, Any]:
        clean = dict(item)
        if clean.get("api_key"):
            clean["api_key"] = "<configured>"
        return clean

    return {
        "version": config.get("version", 1),
        "active_llm_id": config.get("active_llm_id", ""),
        "active_asr_id": config.get("active_asr_id", ""),
        "llm_models": [mask(item) for item in config.get("llm_models", [])],
        "asr_models": [mask(item) for item in config.get("asr_models", [])],
    }
