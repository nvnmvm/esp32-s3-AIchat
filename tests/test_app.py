import asyncio
import json
import logging
import os
import struct
import time

from fastapi.testclient import TestClient

from app.main import VoiceSession, app, cleanup_old_session_files, handle_binary_message


client = TestClient(app)


def receive_json(websocket):
    return json.loads(websocket.receive_text())


def test_health_reports_realtime_foundation_state():
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "esp32-ai-voice-cloud"
    assert data["phase"] == "realtime-foundation"
    assert data["protocol"] == 400
    assert data["protocol_compatibility"] == [303, 400]
    assert data["token_required"] is True
    assert data["audio"]["sample_rate"] == 16000
    assert data["tts_mode"] == "edge"
    assert data["conversation_storage"] == "session-files-retention-cleanup"
    assert data["session_retention_days"] == 3
    assert "recordings" in data["session_dirs"]
    assert "transcripts" in data["session_dirs"]
    assert "answers" in data["session_dirs"]
    assert "audio_report" in data["session_dirs"]
    assert data["save_debug_wav"] is False
    assert data["llm_provider"] == "auto"
    assert data["asr_provider"] == "auto"
    assert data["asr_strategy"] == "cloud_first"
    assert "asr_provider_chain" in data
    assert "model_readiness" in data
    assert data["model_readiness"]["asr_provider_chain"] == data["asr_provider_chain"]
    assert isinstance(data["model_readiness"]["warnings"], list)
    assert data["qwen_realtime"]["model"] == "qwen3-asr-flash-realtime"
    assert data["conversation_max_turns"] == 5


def test_websocket_rejects_missing_token():
    try:
        with client.websocket_connect("/ws?device_id=test-device"):
            raise AssertionError("WebSocket should reject missing token")
    except Exception as exc:
        assert "1008" in str(exc) or "WebSocketDisconnect" in exc.__class__.__name__


def test_websocket_accepts_phase3_ping(monkeypatch):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")

    with client.websocket_connect("/ws?token=test-token&device_id=test-device") as websocket:
        connected = receive_json(websocket)
        assert connected["type"] == "status"
        websocket.send_text(json.dumps({"type": "ping"}))
        pong = receive_json(websocket)
        assert pong["type"] == "status"
        assert pong["state"] == "idle"
        assert pong["protocol"] == 400


def test_websocket_protocol_v4_handshake_and_cancel(monkeypatch):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")

    with client.websocket_connect("/ws?token=test-token&device_id=test-device") as websocket:
        assert receive_json(websocket)["state"] == "idle"
        websocket.send_text(json.dumps({"type": "hello", "protocol": 400}))
        hello = receive_json(websocket)
        assert hello["type"] == "hello"
        assert hello["protocol"] == 400
        assert "barge_in" in hello["capabilities"]

        websocket.send_text(json.dumps({"type": "turn_start", "protocol": 400, "turn_id": 7}))
        ready = receive_json(websocket)
        assert ready["type"] == "turn_ready"
        assert ready["turn_id"] == 7
        assert receive_json(websocket)["state"] == "recording"

        websocket.send_text(json.dumps({"type": "cancel", "turn_id": 7}))
        cancelled = receive_json(websocket)
        assert cancelled["type"] == "turn_cancelled"
        assert cancelled["turn_id"] == 7
        assert receive_json(websocket)["state"] == "idle"


def test_websocket_voice_turn_returns_answer_and_audio(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")
    monkeypatch.setattr("app.main.VAD_MIN_RECORDING_MS", 1)
    monkeypatch.setattr("app.main.VAD_MAX_RECORDING_MS", 1000)
    monkeypatch.setattr("app.main.VAD_SILENCE_CHUNKS", 2)
    monkeypatch.setattr("app.main.MOCK_TTS_DURATION_MS", 50)
    monkeypatch.setattr("app.main.ASR_PROVIDER", "phase2")
    monkeypatch.setattr("app.main.LLM_PROVIDER", "phase3")
    monkeypatch.setattr("app.main.TTS_PROVIDER", "tone")
    monkeypatch.setattr("app.main.SESSION_RECORDINGS_DIR", tmp_path / "session" / "录音")
    monkeypatch.setattr("app.main.SESSION_TRANSCRIPTS_DIR", tmp_path / "session" / "录音转文字")
    monkeypatch.setattr("app.main.SESSION_ANSWERS_DIR", tmp_path / "session" / "ai回答的文本")
    monkeypatch.setattr("app.main.SESSION_AUDIO_REPORT_DIR", tmp_path / "session" / "audio_report")
    monkeypatch.setattr("app.main.CONVERSATION_DIR", tmp_path / "session" / "录音转文字")
    monkeypatch.setattr("app.main.DEBUG_AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr("app.main.SAVE_DEBUG_WAV", True)

    speech = b"".join(struct.pack("<h", 3000) for _ in range(160))
    silence = b"".join(struct.pack("<h", 0) for _ in range(160))

    with client.websocket_connect("/ws?token=test-token&device_id=test-device") as websocket:
        receive_json(websocket)
        websocket.send_text(json.dumps({"type": "start_record"}))
        assert receive_json(websocket)["state"] == "recording"

        websocket.send_bytes(speech)
        websocket.send_bytes(silence)
        websocket.send_bytes(silence)

        seen_types = []
        got_audio = False
        answer_text = ""
        for _ in range(30):
            message = websocket.receive()
            if "text" in message:
                payload = json.loads(message["text"])
                seen_types.append(payload["type"])
                if payload["type"] == "answer_text":
                    answer_text = payload["text"]
                if payload["type"] == "audio_end":
                    break
            elif "bytes" in message:
                got_audio = True

        assert "asr_text" not in seen_types
        assert "answer_text" in seen_types
        assert "audio_start" in seen_types
        assert "audio_end" in seen_types
        assert got_audio is True
        assert "阶段三会话链路已跑通" in answer_text
        assert len(list((tmp_path / "session" / "录音").glob("*.wav"))) == 1
        assert len(list((tmp_path / "session" / "录音转文字").glob("*.txt"))) == 1
        assert len(list((tmp_path / "session" / "ai回答的文本").glob("*.txt"))) == 1
        assert len(list((tmp_path / "session" / "audio_report").glob("*.audio_report.json"))) == 1
        assert len(list((tmp_path / "session" / "audio_report").glob("*.turn_meta.json"))) == 1
        assert len(list((tmp_path / "audio").glob("*.wav"))) == 1


def test_session_retention_cleanup_removes_old_files(monkeypatch, tmp_path):
    recordings_dir = tmp_path / "session" / "录音"
    transcripts_dir = tmp_path / "session" / "录音转文字"
    answers_dir = tmp_path / "session" / "ai回答的文本"
    reports_dir = tmp_path / "session" / "audio_report"
    monkeypatch.setattr("app.main.SESSION_RECORDINGS_DIR", recordings_dir)
    monkeypatch.setattr("app.main.SESSION_TRANSCRIPTS_DIR", transcripts_dir)
    monkeypatch.setattr("app.main.SESSION_ANSWERS_DIR", answers_dir)
    monkeypatch.setattr("app.main.SESSION_AUDIO_REPORT_DIR", reports_dir)
    monkeypatch.setattr("app.main.SESSION_RETENTION_DAYS", 1)

    old_timestamp = time.time() - (2 * 86400)
    recent_paths = []
    old_paths = []
    for directory in (recordings_dir, transcripts_dir, answers_dir, reports_dir):
        directory.mkdir(parents=True)
        recent_path = directory / "recent.txt"
        old_path = directory / "old.txt"
        recent_path.write_text("recent", encoding="utf-8")
        old_path.write_text("old", encoding="utf-8")
        os.utime(old_path, (old_timestamp, old_timestamp))
        recent_paths.append(recent_path)
        old_paths.append(old_path)

    cleanup_old_session_files()

    assert all(path.exists() for path in recent_paths)
    assert all(not path.exists() for path in old_paths)


def test_stray_audio_after_recording_is_ignored(caplog):
    caplog.set_level(logging.INFO, logger="esp32-ai-voice-cloud")
    session = VoiceSession()

    class FakeWebSocket:
        async def close(self, code):
            raise AssertionError(f"WebSocket should not close for stray audio: {code}")

    asyncio.run(handle_binary_message(FakeWebSocket(), session, "test-device", b"1234"))

    assert session.pcm == bytearray()
    assert "Ignored stray audio bytes=4 device_id=test-device because session is not recording" in caplog.text


def test_websocket_closes_oversized_binary(monkeypatch):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")

    with client.websocket_connect("/ws?token=test-token&device_id=test-device") as websocket:
        receive_json(websocket)
        websocket.send_text(json.dumps({"type": "start_record"}))
        receive_json(websocket)
        monkeypatch.setattr("app.main.MAX_WS_MESSAGE_BYTES", 4)
        websocket.send_bytes(b"12345")
        try:
            websocket.receive_text()
            raise AssertionError("WebSocket should close oversized payload")
        except Exception as exc:
            assert "1009" in str(exc) or "WebSocketDisconnect" in exc.__class__.__name__
