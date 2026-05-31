#!/usr/bin/env python3
"""Inspect a WAV file and print the same audio quality report used by the cloud."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a 16-bit PCM WAV recording.")
    parser.add_argument("wav_path", type=Path, help="Input WAV file")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    from app.core.audio_utils import analyze_pcm16le, read_wav_pcm16le
    from app.main import VAD_MIN_RECORDING_MS, VAD_SILENCE_RMS

    if not args.wav_path.exists():
        raise SystemExit(f"WAV file not found: {args.wav_path}")

    pcm, sample_rate, channels, sample_width = read_wav_pcm16le(args.wav_path)
    report = analyze_pcm16le(
        pcm,
        sample_rate=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        silence_rms=VAD_SILENCE_RMS,
        min_duration_s=VAD_MIN_RECORDING_MS / 1000.0,
    )
    text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
