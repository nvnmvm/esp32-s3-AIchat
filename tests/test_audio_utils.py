import struct

from app.core.audio_utils import analyze_pcm16le


def pcm(samples):
    return b"".join(struct.pack("<h", value) for value in samples)


def test_audio_report_detects_ok_audio():
    data = pcm([2000, -2000] * 8000)
    report = analyze_pcm16le(data, min_duration_s=0.5)

    assert report.verdict == "ok"
    assert report.peak == 2000
    assert report.rms > 1000
    assert report.speech_ratio == 1.0


def test_audio_report_detects_mostly_zero():
    data = pcm([0] * 16000)
    report = analyze_pcm16le(data, min_duration_s=0.5)

    assert report.verdict == "mostly_zero"
    assert report.zero_ratio == 1.0


def test_audio_report_detects_clipping():
    data = pcm([32767, -32768] * 8000)
    report = analyze_pcm16le(data, min_duration_s=0.5)

    assert report.verdict == "clipped"
    assert report.clipping_ratio == 1.0
