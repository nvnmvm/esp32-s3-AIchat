#!/usr/bin/env python3
"""Manage runtime/config/models.json for LLM and ASR providers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path("runtime/config/models.json")


def empty_config() -> dict[str, Any]:
    return {
        "version": 2,
        "active_llm_id": "",
        "active_asr_id": "",
        "llm_models": [],
        "asr_models": [],
    }


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_config()
    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = empty_config()
    cfg.update(data)
    try:
        cfg["version"] = max(int(cfg.get("version") or 1), 2)
    except (TypeError, ValueError):
        cfg["version"] = 2
    cfg["llm_models"] = [item for item in cfg.get("llm_models", []) if isinstance(item, dict)]
    cfg["asr_models"] = [item for item in cfg.get("asr_models", []) if isinstance(item, dict)]
    return cfg


def save(path: Path, cfg: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def next_id(items: list[dict[str, Any]], prefix: str) -> str:
    used = {str(item.get("id") or "") for item in items}
    index = 1
    while True:
        candidate = f"{prefix}-{index:03d}"
        if candidate not in used:
            return candidate
        index += 1


def mask_key(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "<configured>"
    return value[:4] + "..." + value[-4:]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cmd_list(args: argparse.Namespace) -> None:
    cfg = load(args.config)
    print(f"Config: {args.config}")
    print(f"Active LLM: {cfg.get('active_llm_id') or '<none>'}")
    for item in cfg["llm_models"]:
        active = "*" if item.get("id") == cfg.get("active_llm_id") else " "
        print(
            f"{active} {item.get('id')} LLM brand={item.get('brand')} "
            f"name={item.get('name')} remark={item.get('remark', '')} "
            f"model={item.get('model')} base_url={item.get('base_url')} "
            f"key={mask_key(str(item.get('api_key') or ''))}"
        )
    print(f"Active ASR: {cfg.get('active_asr_id') or '<none>'}")
    for item in cfg["asr_models"]:
        active = "*" if item.get("id") == cfg.get("active_asr_id") else " "
        print(
            f"{active} {item.get('id')} ASR provider={item.get('provider')} brand={item.get('brand')} "
            f"name={item.get('name')} remark={item.get('remark', '')} "
            f"model={item.get('model')} key={mask_key(str(item.get('api_key') or ''))}"
        )


def cmd_add_llm(args: argparse.Namespace) -> None:
    cfg = load(args.config)
    item_id = args.id or next_id(cfg["llm_models"], "llm")
    item = {
        "id": item_id,
        "brand": args.brand,
        "provider": "openai_compatible",
        "name": args.name or f"{args.brand}-{args.model}",
        "remark": args.remark or args.name or "",
        "base_url": args.base_url,
        "api_key": args.api_key,
        "model": args.model,
        "enabled": True,
        "updated_at": utc_now(),
    }
    cfg["llm_models"] = [item for item in cfg["llm_models"] if item.get("id") != item_id]
    cfg["llm_models"].append(item)
    if args.activate or not cfg.get("active_llm_id"):
        cfg["active_llm_id"] = item_id
    save(args.config, cfg)
    print(item_id)


def cmd_add_asr(args: argparse.Namespace) -> None:
    cfg = load(args.config)
    item_id = args.id or next_id(cfg["asr_models"], "asr")
    item = {
        "id": item_id,
        "brand": args.brand,
        "provider": args.provider,
        "name": args.name or f"{args.brand}-{args.model}",
        "remark": args.remark or args.name or "",
        "base_url": args.base_url,
        "base_http_api_url": args.base_http_api_url,
        "api_key": args.api_key,
        "model": args.model,
        "language": args.language,
        "enable_itn": args.enable_itn,
        "enabled": True,
        "updated_at": utc_now(),
    }
    cfg["asr_models"] = [item for item in cfg["asr_models"] if item.get("id") != item_id]
    cfg["asr_models"].append(item)
    if args.activate or not cfg.get("active_asr_id"):
        cfg["active_asr_id"] = item_id
    save(args.config, cfg)
    print(item_id)


def cmd_switch(args: argparse.Namespace) -> None:
    cfg = load(args.config)
    section = "llm_models" if args.kind == "llm" else "asr_models"
    key = "active_llm_id" if args.kind == "llm" else "active_asr_id"
    if not any(item.get("id") == args.id for item in cfg[section]):
        raise SystemExit(f"Unknown {args.kind} id: {args.id}")
    cfg[key] = args.id
    save(args.config, cfg)
    print(args.id)


def cmd_delete(args: argparse.Namespace) -> None:
    cfg = load(args.config)
    section = "llm_models" if args.kind == "llm" else "asr_models"
    key = "active_llm_id" if args.kind == "llm" else "active_asr_id"
    before = len(cfg[section])
    cfg[section] = [item for item in cfg[section] if item.get("id") != args.id]
    if before == len(cfg[section]):
        raise SystemExit(f"Unknown {args.kind} id: {args.id}")
    if cfg.get(key) == args.id:
        cfg[key] = str(cfg[section][0].get("id") or "") if cfg[section] else ""
    save(args.config, cfg)
    print(args.id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_PATH)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    add_llm = sub.add_parser("add-llm")
    add_llm.add_argument("--id")
    add_llm.add_argument("--brand", required=True)
    add_llm.add_argument("--name")
    add_llm.add_argument("--remark", default="")
    add_llm.add_argument("--base-url", required=True)
    add_llm.add_argument("--api-key", required=True)
    add_llm.add_argument("--model", required=True)
    add_llm.add_argument("--activate", action="store_true")
    add_llm.set_defaults(func=cmd_add_llm)

    add_asr = sub.add_parser("add-asr")
    add_asr.add_argument("--id")
    add_asr.add_argument("--brand", required=True)
    add_asr.add_argument("--provider", required=True)
    add_asr.add_argument("--name")
    add_asr.add_argument("--remark", default="")
    add_asr.add_argument("--base-url", default="")
    add_asr.add_argument("--base-http-api-url", default="https://dashscope.aliyuncs.com/api/v1")
    add_asr.add_argument("--api-key", required=True)
    add_asr.add_argument("--model", required=True)
    add_asr.add_argument("--language", default="zh")
    add_asr.add_argument("--enable-itn", action="store_true")
    add_asr.add_argument("--activate", action="store_true")
    add_asr.set_defaults(func=cmd_add_asr)

    switch = sub.add_parser("switch")
    switch.add_argument("kind", choices=["llm", "asr"])
    switch.add_argument("id")
    switch.set_defaults(func=cmd_switch)

    delete = sub.add_parser("delete")
    delete.add_argument("kind", choices=["llm", "asr"])
    delete.add_argument("id")
    delete.set_defaults(func=cmd_delete)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
