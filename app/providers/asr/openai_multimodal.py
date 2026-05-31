from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.core.audio_utils import AudioReport
from app.providers.asr.base import ASRProvider, AsrResult


class OpenAIMultimodalASRProvider(ASRProvider):
    name = "openai_multimodal"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 60,
        brand: str = "openai-compatible",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.brand = brand

    def transcribe(self, wav_path: Path, audio_report: AudioReport, *, context: str = "") -> AsrResult:
        if not self.api_key:
            raise RuntimeError(f"{self.brand} ASR API key is not configured.")
        audio_b64 = base64.b64encode(wav_path.read_bytes()).decode("ascii")
        url = self.base_url.rstrip("/") + "/chat/completions"
        prompt = context or "请只输出这段录音的准确转写文本，不要解释。"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "转写这段 WAV 录音。"},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_b64,
                                "format": "wav",
                            },
                        },
                    ],
                },
            ],
            "stream": False,
            "temperature": 0,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.brand} ASR HTTP {exc.code}: {body[:240]}") from exc

        text = data["choices"][0]["message"]["content"].strip()
        if not text:
            raise RuntimeError(f"{self.brand} ASR returned empty text.")
        return AsrResult(text=text, provider=self.name, raw={"brand": self.brand, "model": self.model})
