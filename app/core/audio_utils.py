from __future__ import annotations

import json
import math
import struct
import wave
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AudioReport:
    duration_s: float
    byte_count: int
    rms: float
    peak: int
    clipping_ratio: float
    zero_ratio: float
    dc_offset: float
    speech_ratio: float
    verdict: str
    warnings: list[str]

    @property
    def human_message(self) -> str:
        if self.verdict == "too_short":
            return "录音时间太短，没有足够语音内容。请靠近麦克风后完整说一句。"
        if self.verdict == "mostly_zero":
            return "录音几乎全是零值，可能是麦克风接线、I2S 通道或供电配置有问题。"
        if self.verdict == "too_quiet":
            return "录音音量过低，建议靠近麦克风、检查左右声道或适当提高麦克风增益。"
        if self.verdict == "clipped":
            return "录音出现削波，音量过大或增益过高，建议降低增益或离麦克风稍远。"
        return "录音质量正常。"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["human_message"] = self.human_message
        return data


def pcm16_rms(data: bytes) -> float:
    if len(data) < 2:
        return 0.0

    usable = len(data) - (len(data) % 2)
    sample_count = usable // 2
    if sample_count == 0:
        return 0.0

    total = 0
    for (sample,) in struct.iter_unpack("<h", data[:usable]):
        total += sample * sample
    return math.sqrt(total / sample_count)


def analyze_pcm16le(
    pcm: bytes,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width_bytes: int = 2,
    silence_rms: int = 450,
    min_duration_s: float = 0.8,
) -> AudioReport:
    bytes_per_second = sample_rate * channels * sample_width_bytes
    duration_s = len(pcm) / float(bytes_per_second) if bytes_per_second else 0.0
    usable = len(pcm) - (len(pcm) % 2)
    samples = [sample for (sample,) in struct.iter_unpack("<h", pcm[:usable])]
    sample_count = len(samples)

    if sample_count == 0:
        return AudioReport(
            duration_s=0.0,
            byte_count=len(pcm),
            rms=0.0,
            peak=0,
            clipping_ratio=0.0,
            zero_ratio=1.0,
            dc_offset=0.0,
            speech_ratio=0.0,
            verdict="mostly_zero",
            warnings=["没有可解析的 PCM16LE 采样。"],
        )

    abs_samples = [abs(sample) for sample in samples]
    rms = math.sqrt(sum(sample * sample for sample in samples) / sample_count)
    peak = max(abs_samples)
    clipping_ratio = sum(1 for sample in abs_samples if sample >= 32760) / sample_count
    zero_ratio = sum(1 for sample in abs_samples if sample <= 1) / sample_count
    dc_offset = sum(samples) / sample_count
    speech_ratio = sum(1 for sample in abs_samples if sample >= silence_rms) / sample_count

    warnings: list[str] = []
    verdict = "ok"
    if duration_s < min_duration_s:
        verdict = "too_short"
        warnings.append(f"录音时长 {duration_s:.2f}s 低于最小时长 {min_duration_s:.2f}s。")
    elif zero_ratio > 0.8:
        verdict = "mostly_zero"
        warnings.append(f"零值比例 {zero_ratio:.2%} 过高，疑似未采集到有效麦克风信号。")
    elif rms < silence_rms:
        verdict = "too_quiet"
        warnings.append(f"RMS {rms:.0f} 低于静音阈值 {silence_rms}。")
    elif clipping_ratio > 0.01:
        verdict = "clipped"
        warnings.append(f"削波比例 {clipping_ratio:.2%} 过高，可能增益过大。")

    if abs(dc_offset) > 1000:
        warnings.append(f"直流偏移 {dc_offset:.0f} 偏高，建议检查采集链路。")
    if speech_ratio < 0.05 and verdict == "ok":
        warnings.append("有效语音占比偏低，可能环境太安静或 VAD 截断过早。")

    return AudioReport(
        duration_s=duration_s,
        byte_count=len(pcm),
        rms=rms,
        peak=peak,
        clipping_ratio=clipping_ratio,
        zero_ratio=zero_ratio,
        dc_offset=dc_offset,
        speech_ratio=speech_ratio,
        verdict=verdict,
        warnings=warnings,
    )


def read_wav_pcm16le(path: Path) -> tuple[bytes, int, int, int]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        pcm = wav_file.readframes(wav_file.getnframes())
    if sample_width != 2:
        raise RuntimeError(f"Only 16-bit PCM WAV is supported, got sample width={sample_width}.")
    return pcm, sample_rate, channels, sample_width


def write_audio_report(path: Path, report: AudioReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
