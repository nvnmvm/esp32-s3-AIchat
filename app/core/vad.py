from __future__ import annotations

from dataclasses import dataclass

from app.core.audio_utils import pcm16_rms


@dataclass(frozen=True)
class VadConfig:
    min_recording_ms: int = 900
    max_recording_ms: int = 12000
    silence_rms: int = 450
    silence_chunks: int = 12
    chunk_ms: int = 40
    preroll_ms: int = 300
    postroll_ms: int = 240
    sample_rate: int = 16000
    channels: int = 1
    sample_width_bytes: int = 2


class RecordingBuffer:
    def __init__(self, config: VadConfig):
        self.config = config
        self.bytes_seen = 0
        self.chunks_seen = 0
        self.silence_chunks_seen = 0
        self.first_voice_ms: int | None = None
        self.last_voice_ms: int | None = None
        self.finish_reason: str | None = None

    @property
    def duration_ms(self) -> int:
        bytes_per_ms = (
            self.config.sample_rate
            * self.config.channels
            * self.config.sample_width_bytes
            / 1000.0
        )
        if bytes_per_ms <= 0:
            return 0
        return int(self.bytes_seen / bytes_per_ms)

    def feed(self, pcm_chunk: bytes) -> tuple[bool, str | None]:
        self.bytes_seen += len(pcm_chunk)
        self.chunks_seen += 1

        rms = pcm16_rms(pcm_chunk)
        now_ms = self.duration_ms
        has_voice = rms >= self.config.silence_rms

        if has_voice:
            self.silence_chunks_seen = 0
            if self.first_voice_ms is None:
                self.first_voice_ms = now_ms
            self.last_voice_ms = now_ms
        else:
            self.silence_chunks_seen += 1

        if now_ms >= self.config.max_recording_ms:
            self.finish_reason = "max_recording_ms"
            return True, self.finish_reason

        if now_ms < self.config.min_recording_ms:
            return False, None

        if self.first_voice_ms is None:
            return False, None

        if self.silence_chunks_seen >= self.config.silence_chunks:
            self.finish_reason = "vad_silence"
            return True, self.finish_reason

        return False, None

    def diagnostics(self) -> dict[str, int | None]:
        return {
            "duration_ms": self.duration_ms,
            "chunks_seen": self.chunks_seen,
            "silence_chunks_seen": self.silence_chunks_seen,
            "first_voice_ms": self.first_voice_ms,
            "last_voice_ms": self.last_voice_ms,
        }
