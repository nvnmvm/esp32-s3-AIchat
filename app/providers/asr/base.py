from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.audio_utils import AudioReport


@dataclass
class AsrResult:
    text: str
    provider: str
    confidence: float | None = None
    duration_ms: int = 0
    fallback_from: str | None = None
    raw: dict[str, Any] | None = None


class ASRProvider:
    name = "base"

    def transcribe(self, wav_path: Path, audio_report: AudioReport, *, context: str = "") -> AsrResult:
        raise NotImplementedError
