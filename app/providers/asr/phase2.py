from __future__ import annotations

from pathlib import Path

from app.core.audio_utils import AudioReport
from app.providers.asr.base import ASRProvider, AsrResult


class Phase2ASRProvider(ASRProvider):
    name = "phase2"

    def transcribe(self, wav_path: Path, audio_report: AudioReport, *, context: str = "") -> AsrResult:
        if audio_report.verdict != "ok":
            text = audio_report.human_message
        else:
            text = (
                f"阶段三收到一段可用录音，时长约 {audio_report.duration_s:.1f} 秒，"
                f"RMS {audio_report.rms:.0f}，PCM 字节数 {audio_report.byte_count}。"
            )
        return AsrResult(text=text, provider=self.name, raw={"audio_report": audio_report.to_dict()})
