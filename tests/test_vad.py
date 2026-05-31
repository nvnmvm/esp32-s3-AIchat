import struct

from app.core.vad import RecordingBuffer, VadConfig


def chunk(value, samples=640):
    return b"".join(struct.pack("<h", value) for _ in range(samples))


def test_vad_waits_for_minimum_duration_before_finishing():
    vad = RecordingBuffer(
        VadConfig(min_recording_ms=100, silence_chunks=2, sample_rate=16000, sample_width_bytes=2)
    )

    assert vad.feed(chunk(3000))[0] is False
    assert vad.feed(chunk(0))[0] is False
    should_finish, reason = vad.feed(chunk(0))

    assert should_finish is True
    assert reason == "vad_silence"


def test_vad_forces_finish_at_max_duration():
    vad = RecordingBuffer(
        VadConfig(max_recording_ms=40, silence_chunks=20, sample_rate=16000, sample_width_bytes=2)
    )

    should_finish, reason = vad.feed(chunk(3000))

    assert should_finish is True
    assert reason == "max_recording_ms"
