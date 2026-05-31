#!/usr/bin/env python3
"""Transcribe one WAV recording into a UTF-8 text file.

This utility uses the same ASR provider configuration as the FastAPI service.
It is useful for manually re-processing files under runtime/session/录音.
"""

from __future__ import annotations

import argparse
import os
import sys
import wave
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe a 16 kHz mono PCM WAV recording.")
    parser.add_argument("wav_path", type=Path, help="Input WAV file")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("runtime/session/录音转文字"),
        help="Directory for the transcript txt file",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "configured_asr", "qwen_dashscope", "openai_multimodal", "vosk", "phase2"],
        help="Override ASR_PROVIDER",
    )
    return parser.parse_args()


def wav_stats(path: Path) -> tuple[float, float, int]:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from app.main import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE, AUDIO_SAMPLE_WIDTH_BYTES, pcm16_rms

    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getnchannels() != AUDIO_CHANNELS:
            raise SystemExit(f"Expected {AUDIO_CHANNELS} channel(s), got {wav_file.getnchannels()}.")
        if wav_file.getsampwidth() != AUDIO_SAMPLE_WIDTH_BYTES:
            raise SystemExit(f"Expected sample width {AUDIO_SAMPLE_WIDTH_BYTES}, got {wav_file.getsampwidth()}.")
        if wav_file.getframerate() != AUDIO_SAMPLE_RATE:
            raise SystemExit(f"Expected sample rate {AUDIO_SAMPLE_RATE}, got {wav_file.getframerate()}.")
        frames = wav_file.readframes(wav_file.getnframes())

    byte_count = len(frames)
    duration_s = byte_count / float(AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES * AUDIO_CHANNELS)
    return duration_s, pcm16_rms(frames), byte_count


def main() -> None:
    args = parse_args()
    if args.provider:
        os.environ["ASR_PROVIDER"] = args.provider

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from app.main import transcribe_audio_file

    wav_path = args.wav_path
    if not wav_path.exists():
        raise SystemExit(f"WAV file not found: {wav_path}")

    duration_s, rms, byte_count = wav_stats(wav_path)
    text = transcribe_audio_file(wav_path, duration_s, rms, byte_count)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{wav_path.stem}.txt"
    out_path.write_text(text.strip() + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
