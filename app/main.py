import logging
import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse


APP_NAME = "esp32-ai-voice-cloud"
WS_TOKEN = os.getenv("WS_TOKEN", "")
ALLOW_EMPTY_TOKEN = os.getenv("ALLOW_EMPTY_TOKEN", "false").lower() == "true"
AI_API_KEY = os.getenv("AI_API_KEY", "")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(APP_NAME)

app = FastAPI(title=APP_NAME)


def client_name(websocket: WebSocket) -> str:
    host = websocket.client.host if websocket.client else "unknown"
    port = websocket.client.port if websocket.client else "unknown"
    return f"{host}:{port}"


def token_from(websocket: WebSocket) -> Optional[str]:
    query_token = websocket.query_params.get("token")
    header_token = websocket.headers.get("x-ws-token")
    return query_token or header_token


def token_is_valid(websocket: WebSocket) -> bool:
    if ALLOW_EMPTY_TOKEN and not WS_TOKEN:
        return True
    return bool(WS_TOKEN) and token_from(websocket) == WS_TOKEN


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "service": APP_NAME,
            "phase": "websocket-echo",
            "token_required": not ALLOW_EMPTY_TOKEN,
            "ai_api_key_configured": bool(AI_API_KEY),
        }
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    device_id = websocket.query_params.get("device_id", "unknown-device")
    peer = client_name(websocket)

    if not token_is_valid(websocket):
        logger.warning("Rejected WebSocket peer=%s device_id=%s: invalid token", peer, device_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("ESP32 connected peer=%s device_id=%s", peer, device_id)

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                logger.info("ESP32 disconnected peer=%s device_id=%s", peer, device_id)
                break

            if "text" in message and message["text"] is not None:
                text = message["text"]
                logger.info("Received text peer=%s device_id=%s bytes=%d text=%s",
                            peer, device_id, len(text.encode("utf-8")), text)
                await websocket.send_text(text)
                logger.info("Echoed text peer=%s device_id=%s bytes=%d",
                            peer, device_id, len(text.encode("utf-8")))

            elif "bytes" in message and message["bytes"] is not None:
                data = message["bytes"]
                logger.info("Received binary peer=%s device_id=%s bytes=%d",
                            peer, device_id, len(data))
                await websocket.send_bytes(data)
                logger.info("Echoed binary peer=%s device_id=%s bytes=%d",
                            peer, device_id, len(data))

    except WebSocketDisconnect:
        logger.info("ESP32 disconnected peer=%s device_id=%s", peer, device_id)
