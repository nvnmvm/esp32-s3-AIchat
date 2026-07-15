from __future__ import annotations

import asyncio
import base64
import json
import uuid
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote


@dataclass(frozen=True)
class RealtimeASREvent:
    type: str
    text: str = ""
    raw: Optional[dict[str, Any]] = None


class QwenRealtimeASRSession:
    """One Qwen-ASR-Realtime WebSocket connection for one user turn."""

    def __init__(
        self,
        *,
        api_key: str,
        workspace_id: str,
        model: str = "qwen3-asr-flash-realtime",
        region: str = "cn-beijing",
        ws_url: str = "",
        sample_rate: int = 16000,
        language: str = "zh",
        vad_threshold: float = 0.0,
        vad_silence_ms: int = 400,
        connect_timeout_seconds: int = 10,
        finish_timeout_seconds: int = 8,
    ) -> None:
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.model = model
        self.region = region
        self.ws_url = ws_url
        self.sample_rate = sample_rate
        self.language = language
        self.vad_threshold = vad_threshold
        self.vad_silence_ms = vad_silence_ms
        self.connect_timeout_seconds = connect_timeout_seconds
        self.finish_timeout_seconds = finish_timeout_seconds

        self.events: asyncio.Queue[RealtimeASREvent] = asyncio.Queue()
        self.transcript = ""
        self._websocket: Any = None
        self._receiver_task: Optional[asyncio.Task[None]] = None
        self._finished = asyncio.Event()
        self._finish_sent = False
        self._closed = False

    @property
    def endpoint(self) -> str:
        if self.ws_url:
            separator = "&" if "?" in self.ws_url else "?"
            if "model=" in self.ws_url:
                return self.ws_url
            return f"{self.ws_url}{separator}model={quote(self.model)}"
        if not self.workspace_id:
            raise RuntimeError("QWEN_REALTIME_WORKSPACE_ID is not configured.")
        hosts = {
            "cn-beijing": "cn-beijing.maas.aliyuncs.com",
            "ap-southeast-1": "ap-southeast-1.maas.aliyuncs.com",
        }
        host = hosts.get(self.region)
        if host is None:
            raise RuntimeError(f"Unsupported Qwen realtime region: {self.region}")
        return f"wss://{self.workspace_id}.{host}/api-ws/v1/realtime?model={quote(self.model)}"

    async def start(self) -> None:
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured.")
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            raise RuntimeError("Qwen realtime ASR requires the websockets package.") from exc

        self._websocket = await connect(
            self.endpoint,
            additional_headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "esp32-ai-voice-cloud/4",
            },
            open_timeout=self.connect_timeout_seconds,
            close_timeout=3,
            ping_interval=20,
            ping_timeout=20,
            max_size=2 * 1024 * 1024,
        )
        self._receiver_task = asyncio.create_task(self._receive_events(), name="qwen-realtime-asr-events")
        await self._send(
            {
                "event_id": self._event_id(),
                "type": "session.update",
                "session": {
                    "input_audio_format": "pcm",
                    "sample_rate": self.sample_rate,
                    "input_audio_transcription": {"language": self.language},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": self.vad_threshold,
                        "silence_duration_ms": self.vad_silence_ms,
                    },
                },
            }
        )

    async def append_audio(self, pcm: bytes) -> None:
        if not pcm or self._closed or self._finish_sent:
            return
        await self._send(
            {
                "event_id": self._event_id(),
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm).decode("ascii"),
            }
        )

    async def finish(self) -> str:
        if self._closed:
            return self.transcript
        if not self._finish_sent:
            self._finish_sent = True
            await self._send({"event_id": self._event_id(), "type": "session.finish"})
        try:
            await asyncio.wait_for(self._finished.wait(), timeout=self.finish_timeout_seconds)
        finally:
            await self.close()
        return self.transcript

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            await websocket.close()
        task = self._receiver_task
        self._receiver_task = None
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._finished.set()

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._websocket is None:
            raise RuntimeError("Qwen realtime ASR WebSocket is not connected.")
        await self._websocket.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    async def _receive_events(self) -> None:
        try:
            async for message in self._websocket:
                if isinstance(message, bytes):
                    message = message.decode("utf-8", errors="replace")
                payload = json.loads(message)
                if not isinstance(payload, dict):
                    continue
                event_type = str(payload.get("type") or "")
                if event_type == "conversation.item.input_audio_transcription.text":
                    preview = f"{payload.get('text') or ''}{payload.get('stash') or ''}".strip()
                    if preview:
                        await self.events.put(RealtimeASREvent("partial", preview, payload))
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = str(payload.get("transcript") or "").strip()
                    if transcript:
                        self.transcript = transcript
                        await self.events.put(RealtimeASREvent("final", transcript, payload))
                elif event_type == "input_audio_buffer.speech_started":
                    await self.events.put(RealtimeASREvent("speech_started", raw=payload))
                elif event_type == "input_audio_buffer.speech_stopped":
                    await self.events.put(RealtimeASREvent("speech_stopped", raw=payload))
                elif event_type in {"error", "conversation.item.input_audio_transcription.failed"}:
                    error = payload.get("error") or {}
                    message_text = str(error.get("message") or error.get("code") or "Qwen realtime ASR failed")
                    await self.events.put(RealtimeASREvent("error", message_text, payload))
                elif event_type == "session.finished":
                    self._finished.set()
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.events.put(RealtimeASREvent("error", str(exc), {"exception": type(exc).__name__}))
        finally:
            self._finished.set()

    @staticmethod
    def _event_id() -> str:
        return f"event_{uuid.uuid4().hex}"
