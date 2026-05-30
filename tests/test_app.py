import json
import struct

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def receive_json(websocket):
    return json.loads(websocket.receive_text())


def test_health_reports_phase2_state():
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "esp32-ai-voice-cloud"
    assert data["phase"] == "voice-screen-loopback"
    assert data["token_required"] is True
    assert data["audio"]["sample_rate"] == 16000
    assert data["tts_mode"] == "local-test-tone"
    assert data["conversation_storage"] == "per-turn-file-auto-delete"


def test_websocket_rejects_missing_token():
    try:
        with client.websocket_connect("/ws?device_id=test-device"):
            raise AssertionError("WebSocket should reject missing token")
    except Exception as exc:
        assert "1008" in str(exc) or "WebSocketDisconnect" in exc.__class__.__name__


def test_websocket_accepts_phase2_ping(monkeypatch):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")

    with client.websocket_connect("/ws?token=test-token&device_id=test-device") as websocket:
        connected = receive_json(websocket)
        assert connected["type"] == "status"
        websocket.send_text(json.dumps({"type": "ping"}))
        pong = receive_json(websocket)
        assert pong["type"] == "status"
        assert pong["state"] == "idle"


def test_websocket_voice_turn_returns_text_and_audio(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")
    monkeypatch.setattr("app.main.VAD_MIN_RECORDING_BYTES", 256)
    monkeypatch.setattr("app.main.VAD_SILENCE_CHUNKS", 2)
    monkeypatch.setattr("app.main.MOCK_TTS_DURATION_MS", 50)
    monkeypatch.setattr("app.main.CONVERSATION_DIR", tmp_path)

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
        for _ in range(20):
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

        assert "asr_text" in seen_types
        assert "answer_text" in seen_types
        assert "audio_start" in seen_types
        assert "audio_end" in seen_types
        assert got_audio is True
        assert "本轮文本文件已在回复后自动清理" in answer_text
        assert list(tmp_path.glob("*.txt")) == []


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
