from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx


SYSTEM_PROMPT = (
    "你是 ESP32-S3 私有语音机器人。回答要简短、直接、适合语音播报和小屏幕滚动显示。"
    "默认使用中文，不要输出 Markdown，不要输出思考过程。"
)


async def stream_openai_compatible_chat(
    user_text: str,
    *,
    provider_name: str,
    api_key: str,
    base_url: str,
    model: str,
    timeout_seconds: int,
    max_tokens: int,
    history: Optional[list[dict[str, str]]] = None,
    disable_thinking: bool = False,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    """Yield Chat Completions SSE content deltas and ignore reasoning deltas."""

    if not api_key:
        raise RuntimeError(f"{provider_name} API key is not configured.")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *(history or []),
            {"role": "user", "content": user_text},
        ],
        "stream": True,
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }
    if disable_thinking:
        payload["thinking"] = {"type": "disabled"}

    timeout = httpx.Timeout(timeout_seconds, connect=min(10, timeout_seconds))
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        async with client.stream(
            "POST",
            base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=payload,
        ) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise RuntimeError(f"{provider_name} HTTP {response.status_code}: {body[:240]}")

            emitted = False
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data_text = line[5:].strip()
                if data_text == "[DONE]":
                    break
                try:
                    data = json.loads(data_text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Invalid {provider_name} SSE data: {data_text[:160]}") from exc

                if isinstance(data, dict) and data.get("error"):
                    raise RuntimeError(f"{provider_name} stream error: {str(data['error'])[:240]}")
                choices = data.get("choices") if isinstance(data, dict) else None
                if not isinstance(choices, list) or not choices:
                    continue
                delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                content = delta.get("content") if isinstance(delta, dict) else None
                if isinstance(content, str) and content:
                    emitted = True
                    yield content

            if not emitted:
                raise RuntimeError(f"{provider_name} returned an empty streaming answer.")
