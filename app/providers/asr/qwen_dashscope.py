from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.audio_utils import AudioReport
from app.providers.asr.base import ASRProvider, AsrResult


class QwenDashScopeASRProvider(ASRProvider):
    name = "qwen_dashscope"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "qwen3-asr-flash",
        base_http_api_url: str = "https://dashscope.aliyuncs.com/api/v1",
        language: str = "zh",
        enable_itn: bool = True,
    ):
        self.api_key = api_key
        self.model = model
        self.base_http_api_url = base_http_api_url
        self.language = language
        self.enable_itn = enable_itn

    def transcribe(self, wav_path: Path, audio_report: AudioReport, *, context: str = "") -> AsrResult:
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured.")
        try:
            import dashscope
        except ImportError as exc:
            raise RuntimeError("qwen_dashscope ASR requires the dashscope Python package.") from exc

        dashscope.base_http_api_url = self.base_http_api_url
        system_text = context or "请将录音准确转写为简体中文，保留必要的英文术语。"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": [{"text": system_text}]},
            {"role": "user", "content": [{"audio": wav_path.resolve().as_uri()}]},
        ]
        asr_options: dict[str, Any] = {"enable_itn": self.enable_itn}
        if self.language:
            asr_options["language"] = self.language

        response = dashscope.MultiModalConversation.call(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            result_format="message",
            asr_options=asr_options,
        )
        raw = response if isinstance(response, dict) else getattr(response, "output", response)
        text = _extract_dashscope_text(raw).strip()
        if not text:
            raise RuntimeError(f"DashScope ASR returned empty text: {raw}")
        return AsrResult(text=text, provider=self.name, raw={"model": self.model})


def _extract_dashscope_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, dict):
        raw = getattr(raw, "output", None)
    if not isinstance(raw, dict):
        return ""

    output = raw.get("output", raw)
    choices = output.get("choices") if isinstance(output, dict) else None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    for key in ("text", "transcript", "content"):
                        value = item.get(key)
                        if isinstance(value, str):
                            parts.append(value)
            return "".join(parts)

    text = output.get("text") if isinstance(output, dict) else None
    return text if isinstance(text, str) else ""
