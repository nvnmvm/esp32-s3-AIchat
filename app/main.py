import asyncio
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import math
import os
import secrets
import struct
import time
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse


APP_NAME = "esp32-ai-voice-cloud"
APP_VERSION = os.getenv("APP_VERSION", "v2.1.3-phase2-stable")
APP_PHASE = "voice-screen-loopback"
WS_TOKEN = os.getenv("WS_TOKEN", "")
ALLOW_EMPTY_TOKEN = os.getenv("ALLOW_EMPTY_TOKEN", "false").lower() == "true"
AI_API_KEY = os.getenv("AI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", AI_API_KEY)
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "phase2").lower()
ASR_PROVIDER = os.getenv("ASR_PROVIDER", "phase2").lower()
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "tone").lower()
LOG_PAYLOADS = os.getenv("LOG_PAYLOADS", "false").lower() == "true"
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOG_DIR = Path(os.getenv("LOG_DIR", "runtime/logs"))
CONVERSATION_DIR = Path(os.getenv("CONVERSATION_DIR", "runtime/conversations"))
SAVE_DEBUG_WAV = os.getenv("SAVE_DEBUG_WAV", "false").lower() == "true"
DEBUG_AUDIO_DIR = Path(os.getenv("DEBUG_AUDIO_DIR", "runtime/audio"))

logger = logging.getLogger(APP_NAME)

app = FastAPI(title=APP_NAME)


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid integer env %s=%s; using default=%d", name, raw, default)
        return default
    if value <= 0:
        logger.warning("Invalid non-positive env %s=%s; using default=%d", name, raw, default)
        return default
    return value


MAX_WS_MESSAGE_BYTES = env_int("MAX_WS_MESSAGE_BYTES", 1048576)
AUDIO_SAMPLE_RATE = env_int("AUDIO_SAMPLE_RATE", 16000)
AUDIO_CHANNELS = env_int("AUDIO_CHANNELS", 1)
AUDIO_SAMPLE_WIDTH_BYTES = env_int("AUDIO_SAMPLE_WIDTH_BYTES", 2)
MAX_RECORDING_BYTES = env_int("MAX_RECORDING_BYTES", AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES * 12)
VAD_MIN_RECORDING_BYTES = env_int("VAD_MIN_RECORDING_BYTES", AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES)
VAD_SILENCE_RMS = env_int("VAD_SILENCE_RMS", 450)
VAD_SILENCE_CHUNKS = env_int("VAD_SILENCE_CHUNKS", 12)
MOCK_TTS_DURATION_MS = env_int("MOCK_TTS_DURATION_MS", 900)
MOCK_TTS_TONE_HZ = env_int("MOCK_TTS_TONE_HZ", 660)
LLM_TIMEOUT_SECONDS = env_int("LLM_TIMEOUT_SECONDS", 30)
LOG_RETENTION_DAYS = env_int("LOG_RETENTION_DAYS", 7)


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        root_logger.addHandler(console_handler)

    if not LOG_TO_FILE:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - (LOG_RETENTION_DAYS * 86400)
    for path in LOG_DIR.glob("*.log*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            root_logger.warning("Failed to remove old log file path=%s", path, exc_info=True)

    file_handler = TimedRotatingFileHandler(
        LOG_DIR / "cloud.log",
        when="midnight",
        interval=1,
        backupCount=LOG_RETENTION_DAYS,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)


configure_logging()


@dataclass
class VoiceSession:
    recording: bool = False
    pcm: bytearray = field(default_factory=bytearray)
    silence_chunks: int = 0
    turn_id: int = 0
    transcript_path: Optional[Path] = None

    def reset_recording(self) -> None:
        self.recording = False
        self.pcm.clear()
        self.silence_chunks = 0

    def clear_transcript(self) -> None:
        if self.transcript_path is None:
            return
        try:
            self.transcript_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove transcript file path=%s", self.transcript_path, exc_info=True)
        finally:
            self.transcript_path = None


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
    token = token_from(websocket)
    return bool(WS_TOKEN) and token is not None and secrets.compare_digest(token, WS_TOKEN)


def payload_preview(text: str) -> str:
    if not LOG_PAYLOADS:
        return "<payload logging disabled>"
    return text[:160]


def json_text(message_type: str, **fields: Any) -> str:
    payload = {"type": message_type, **fields}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


async def send_json(websocket: WebSocket, message_type: str, **fields: Any) -> None:
    await websocket.send_text(json_text(message_type, **fields))


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


def make_tone_pcm(duration_ms: Optional[int] = None, frequency_hz: Optional[int] = None) -> bytes:
    duration_ms = duration_ms or MOCK_TTS_DURATION_MS
    frequency_hz = frequency_hz or MOCK_TTS_TONE_HZ
    sample_count = max(1, AUDIO_SAMPLE_RATE * duration_ms // 1000)
    amplitude = 9000
    frames = bytearray()
    for index in range(sample_count):
        envelope = min(1.0, index / 400) * min(1.0, (sample_count - index) / 400)
        value = int(amplitude * envelope * math.sin(2 * math.pi * frequency_hz * index / AUDIO_SAMPLE_RATE))
        frames.extend(struct.pack("<h", value))
    return bytes(frames)


def safe_device_slug(device_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in device_id)[:48] or "device"


def write_debug_wav(device_id: str, turn_id: int, pcm: bytes) -> Optional[Path]:
    if not SAVE_DEBUG_WAV:
        return None

    DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_AUDIO_DIR / f"turn-{turn_id}-{safe_device_slug(device_id)}.wav"
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(AUDIO_CHANNELS)
        wav_file.setsampwidth(AUDIO_SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(pcm)
    return path


def transcribe_phase2_audio(duration_s: float, rms: float, byte_count: int) -> str:
    if rms < VAD_SILENCE_RMS:
        return (
            f"阶段二收到一段音频，时长约 {duration_s:.1f} 秒，"
            f"但音量偏低，RMS {rms:.0f}。请检查麦克风接线、增益和供电。"
        )

    return (
        f"阶段二收到一段测试语音，时长约 {duration_s:.1f} 秒，"
        f"音量 RMS {rms:.0f}，PCM 字节数 {byte_count}。"
    )


def transcript_file_path(device_id: str, turn_id: int) -> Path:
    return CONVERSATION_DIR / f"{safe_device_slug(device_id)}-turn-{turn_id}.txt"


def write_transcript_file(device_id: str, turn_id: int, text: str) -> Path:
    CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)
    path = transcript_file_path(device_id, turn_id)
    path.write_text(text, encoding="utf-8")
    return path


def build_phase2_answer_from_file(path: Path) -> str:
    transcript = path.read_text(encoding="utf-8").strip()
    if not transcript:
        return "阶段二云端没有读取到有效识别文本，请重新唤醒后再说一遍。"

    return (
        "阶段二闭环已完成：云端已读取本轮语音转文字文件，"
        "OLED 应显示本回答；本轮文本文件已在回复后自动清理。"
    )


def deepseek_chat(user_text: str) -> str:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY or AI_API_KEY is not configured.")

    url = DEEPSEEK_API_BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是 ESP32-S3 AI 对话机器人阶段二闭环测试助手。回答要简洁、直接、适合显示在小屏幕上。",
            },
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "temperature": 0.7,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {body[:240]}") from exc

    try:
        answer = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected DeepSeek response: {data}") from exc

    if not answer:
        raise RuntimeError("DeepSeek returned an empty answer.")
    return answer


async def build_answer_text(path: Path) -> str:
    transcript = path.read_text(encoding="utf-8").strip()
    if LLM_PROVIDER == "deepseek" or (LLM_PROVIDER == "auto" and DEEPSEEK_API_KEY):
        return await asyncio.to_thread(deepseek_chat, transcript)
    return build_phase2_answer_from_file(path)


async def build_phase2_turn(device_id: str, turn_id: int, duration_s: float, rms: float, byte_count: int) -> tuple[str, str, Path]:
    asr_text = transcribe_phase2_audio(duration_s, rms, byte_count)
    transcript_path = write_transcript_file(device_id, turn_id, asr_text)
    answer_text = await build_answer_text(transcript_path)
    return asr_text, answer_text, transcript_path


async def finish_recording(websocket: WebSocket, session: VoiceSession, device_id: str, reason: str) -> None:
    if not session.pcm:
        await send_json(websocket, "error", text="没有收到有效 PCM 音频。")
        session.reset_recording()
        return

    pcm = bytes(session.pcm)
    session.reset_recording()

    duration_s = len(pcm) / float(AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES * AUDIO_CHANNELS)
    rms = pcm16_rms(pcm)
    wav_path = write_debug_wav(device_id, session.turn_id, pcm)

    logger.info(
        "Processed phase2 audio turn=%d bytes=%d duration_s=%.2f rms=%.1f reason=%s wav_path=%s",
        session.turn_id,
        len(pcm),
        duration_s,
        rms,
        reason,
        wav_path,
    )

    try:
        await send_json(websocket, "status", text="识别中...", state="asr", turn_id=session.turn_id)
        asr_text, answer_text, session.transcript_path = await build_phase2_turn(
            device_id=device_id,
            turn_id=session.turn_id,
            duration_s=duration_s,
            rms=rms,
            byte_count=len(pcm),
        )
        await send_json(websocket, "asr_text", text=asr_text, turn_id=session.turn_id)
        await send_json(websocket, "status", text="思考中...", state="thinking", turn_id=session.turn_id)
        await send_json(websocket, "answer_text", text=answer_text, turn_id=session.turn_id)
        await send_json(websocket, "audio_start", sample_rate=AUDIO_SAMPLE_RATE, format="pcm_s16le")

        audio = make_tone_pcm()
        chunk_size = AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES // 10
        for start in range(0, len(audio), chunk_size):
            await websocket.send_bytes(audio[start:start + chunk_size])

        await send_json(websocket, "audio_end")
        await send_json(websocket, "status", text="空闲，等待唤醒", state="idle")
    except Exception:
        logger.exception("Failed to process phase2 turn=%d device_id=%s", session.turn_id, device_id)
        await send_json(websocket, "error", text="云端处理本轮语音失败，请查看 VPS 日志。")
    finally:
        session.clear_transcript()


async def handle_json_message(websocket: WebSocket, session: VoiceSession, device_id: str, payload: dict[str, Any]) -> None:
    message_type = str(payload.get("type", "")).strip().lower()

    if message_type == "start_record":
        session.clear_transcript()
        session.turn_id += 1
        session.reset_recording()
        session.recording = True
        await send_json(websocket, "status", text="录音中...", state="recording", turn_id=session.turn_id)
        return

    if message_type in {"finish_record", "vad_end"}:
        await finish_recording(websocket, session, device_id, message_type)
        return

    if message_type == "cancel":
        session.clear_transcript()
        session.reset_recording()
        await send_json(websocket, "status", text="已取消，等待唤醒", state="idle")
        return

    if message_type == "stop":
        session.clear_transcript()
        session.reset_recording()
        await send_json(websocket, "status", text="已结束对话", state="idle")
        return

    if message_type == "ping":
        await send_json(websocket, "status", text="phase2 ok", state="idle")
        return

    await send_json(websocket, "error", text=f"未知消息类型: {message_type or '<empty>'}")


async def handle_binary_message(websocket: WebSocket, session: VoiceSession, device_id: str, data: bytes) -> None:
    if len(data) > MAX_WS_MESSAGE_BYTES:
        await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
        return

    if not session.recording:
        logger.info(
            "Ignored stray audio bytes=%d device_id=%s because session is not recording",
            len(data),
            device_id,
        )
        return

    if len(session.pcm) + len(data) > MAX_RECORDING_BYTES:
        await finish_recording(websocket, session, device_id, "max_recording_bytes")
        return

    session.pcm.extend(data)
    rms = pcm16_rms(data)
    if len(session.pcm) >= VAD_MIN_RECORDING_BYTES and rms < VAD_SILENCE_RMS:
        session.silence_chunks += 1
    else:
        session.silence_chunks = 0

    if session.silence_chunks >= VAD_SILENCE_CHUNKS:
        await finish_recording(websocket, session, device_id, "vad_silence")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "service": APP_NAME,
            "version": APP_VERSION,
            "phase": APP_PHASE,
            "token_required": not ALLOW_EMPTY_TOKEN,
            "max_ws_message_bytes": MAX_WS_MESSAGE_BYTES,
            "max_recording_bytes": MAX_RECORDING_BYTES,
            "audio": {
                "sample_rate": AUDIO_SAMPLE_RATE,
                "channels": AUDIO_CHANNELS,
                "sample_width_bytes": AUDIO_SAMPLE_WIDTH_BYTES,
                "format": "pcm_s16le",
            },
            "ai_api_key_configured": bool(AI_API_KEY),
            "asr_provider": ASR_PROVIDER,
            "llm_provider": LLM_PROVIDER,
            "tts_provider": TTS_PROVIDER,
            "tts_mode": "local-test-tone" if TTS_PROVIDER == "tone" else TTS_PROVIDER,
            "conversation_dir": str(CONVERSATION_DIR),
            "conversation_storage": "per-turn-file-auto-delete",
            "save_debug_wav": SAVE_DEBUG_WAV,
            "debug_audio_dir": str(DEBUG_AUDIO_DIR),
            "log_to_file": LOG_TO_FILE,
            "log_dir": str(LOG_DIR),
            "log_retention_days": LOG_RETENTION_DAYS,
        }
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    device_id = websocket.query_params.get("device_id", "unknown-device")
    peer = client_name(websocket)
    session = VoiceSession()

    if not token_is_valid(websocket):
        logger.warning("Rejected WebSocket peer=%s device_id=%s: invalid token", peer, device_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("ESP32 connected peer=%s device_id=%s phase=%s", peer, device_id, APP_PHASE)
    await send_json(websocket, "status", text="云端已连接，等待唤醒", state="idle")

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                logger.info("ESP32 disconnected peer=%s device_id=%s", peer, device_id)
                break

            if "text" in message and message["text"] is not None:
                text = message["text"]
                payload_size = len(text.encode("utf-8"))
                if payload_size > MAX_WS_MESSAGE_BYTES:
                    await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                    break

                logger.info(
                    "Received text peer=%s device_id=%s bytes=%d preview=%s",
                    peer,
                    device_id,
                    payload_size,
                    payload_preview(text),
                )
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    await send_json(websocket, "error", text="阶段二协议需要 JSON 文本消息。")
                    continue

                if not isinstance(payload, dict):
                    await send_json(websocket, "error", text="JSON 消息必须是对象。")
                    continue

                await handle_json_message(websocket, session, device_id, payload)

            elif "bytes" in message and message["bytes"] is not None:
                await handle_binary_message(websocket, session, device_id, message["bytes"])

    except WebSocketDisconnect:
        logger.info("ESP32 disconnected peer=%s device_id=%s", peer, device_id)
    finally:
        session.clear_transcript()
