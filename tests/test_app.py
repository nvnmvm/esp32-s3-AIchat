from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_service_state():
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "esp32-ai-voice-cloud"
    assert data["phase"] == "websocket-echo"
    assert data["token_required"] is True
    assert data["max_ws_message_bytes"] > 0


def test_websocket_rejects_missing_token():
    try:
        with client.websocket_connect("/ws?device_id=test-device"):
            raise AssertionError("WebSocket should reject missing token")
    except Exception as exc:
        assert "1008" in str(exc) or "WebSocketDisconnect" in exc.__class__.__name__


def test_websocket_echoes_text_with_valid_token(monkeypatch):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")

    with client.websocket_connect("/ws?token=test-token&device_id=test-device") as websocket:
        websocket.send_text("hello")
        assert websocket.receive_text() == "hello"


def test_websocket_closes_oversized_text(monkeypatch):
    monkeypatch.setattr("app.main.WS_TOKEN", "test-token")
    monkeypatch.setattr("app.main.MAX_WS_MESSAGE_BYTES", 4)

    with client.websocket_connect("/ws?token=test-token&device_id=test-device") as websocket:
        websocket.send_text("hello")
        try:
            websocket.receive_text()
            raise AssertionError("WebSocket should close oversized payload")
        except Exception as exc:
            assert "1009" in str(exc) or "WebSocketDisconnect" in exc.__class__.__name__
