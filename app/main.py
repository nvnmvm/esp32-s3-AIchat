from __future__ import annotations

import asyncio
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import math
import os
import re
import secrets
import shutil
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from app.core.audio_utils import (
    AudioReport,
    analyze_pcm16le,
)
from app.core.model_config import active_item, load_model_config, masked_config_summary
from app.core.vad import RecordingBuffer, VadConfig
from app.providers.asr.base import AsrResult
from app.providers.asr.factory import provider_chain, transcribe_with_fallback
from app.providers.asr.qwen_realtime import QwenRealtimeASRSession, RealtimeASREvent
from app.providers.llm.openai_stream import stream_openai_compatible_chat
from app.services.text_stream import SentenceAccumulator, ThinkingTagFilter


APP_NAME = "esp32-ai-voice-cloud"
APP_VERSION = "v4.1.0-streaming-pipeline"
CONFIGURED_APP_VERSION = os.getenv("APP_VERSION", APP_VERSION)
APP_PHASE = "streaming-pipeline"
PROTOCOL_VERSION = 400
WS_TOKEN = os.getenv("WS_TOKEN", "")
ALLOW_EMPTY_TOKEN = os.getenv("ALLOW_EMPTY_TOKEN", "false").lower() == "true"

AI_API_KEY = os.getenv("AI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", AI_API_KEY)
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
AI_API_BASE = os.getenv("AI_API_BASE", DEEPSEEK_API_BASE)
AI_MODEL = os.getenv("AI_MODEL", DEEPSEEK_MODEL)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()
LLM_STREAMING_ENABLED = os.getenv("LLM_STREAMING_ENABLED", "true").lower() == "true"
LLM_DISABLE_THINKING = os.getenv("LLM_DISABLE_THINKING", "true").lower() == "true"

ASR_PROVIDER = os.getenv("ASR_PROVIDER", "auto").lower()
ASR_PRIMARY = os.getenv("ASR_PRIMARY", "configured_asr").lower()
ASR_FALLBACK = os.getenv("ASR_FALLBACK", "vosk").lower()
ASR_STRATEGY = os.getenv("ASR_STRATEGY", "cloud_first").lower()
ASR_CONTEXT = os.getenv("ASR_CONTEXT", "小一小一,ESP32-S3,高数,数据结构,计算机科学与技术")
ASR_LANGUAGE = os.getenv("ASR_LANGUAGE", "zh")
ASR_TIMEOUT_SECONDS = int(os.getenv("ASR_TIMEOUT_SECONDS", "60"))
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_ASR_MODEL = os.getenv("DASHSCOPE_ASR_MODEL", "qwen3-asr-flash")
DASHSCOPE_BASE_HTTP_API_URL = os.getenv("DASHSCOPE_BASE_HTTP_API_URL", "https://dashscope.aliyuncs.com/api/v1")
QWEN_REALTIME_ENABLED = os.getenv("QWEN_REALTIME_ENABLED", "true").lower() == "true"
QWEN_REALTIME_WORKSPACE_ID = os.getenv("QWEN_REALTIME_WORKSPACE_ID", "")
QWEN_REALTIME_REGION = os.getenv("QWEN_REALTIME_REGION", "cn-beijing")
QWEN_REALTIME_WS_URL = os.getenv("QWEN_REALTIME_WS_URL", "")
QWEN_REALTIME_MODEL = os.getenv("QWEN_REALTIME_MODEL", "qwen3-asr-flash-realtime")

TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge").lower()
LOG_PAYLOADS = os.getenv("LOG_PAYLOADS", "false").lower() == "true"
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOG_DIR = Path(os.getenv("LOG_DIR", "runtime/logs"))
SESSION_DIR = Path(os.getenv("SESSION_DIR", "runtime/session"))
SESSION_RECORDINGS_DIR = Path(os.getenv("SESSION_RECORDINGS_DIR", str(SESSION_DIR / "录音")))
SESSION_TRANSCRIPTS_DIR = Path(os.getenv("SESSION_TRANSCRIPTS_DIR", str(SESSION_DIR / "录音转文字")))
SESSION_ANSWERS_DIR = Path(os.getenv("SESSION_ANSWERS_DIR", str(SESSION_DIR / "ai回答的文本")))
SESSION_AUDIO_REPORT_DIR = Path(os.getenv("SESSION_AUDIO_REPORT_DIR", str(SESSION_DIR / "audio_report")))
CONVERSATION_DIR = Path(os.getenv("CONVERSATION_DIR", str(SESSION_TRANSCRIPTS_DIR)))
MODEL_CONFIG_PATH = Path(os.getenv("MODEL_CONFIG_PATH", "runtime/config/models.json"))
SAVE_DEBUG_WAV = os.getenv("SAVE_DEBUG_WAV", "false").lower() == "true"
DEBUG_AUDIO_DIR = Path(os.getenv("DEBUG_AUDIO_DIR", "runtime/audio"))
VOSK_MODEL_DIR = Path(os.getenv("VOSK_MODEL_DIR", "runtime/models/vosk-model-small-cn-0.22"))
VOSK_MODEL_URL = os.getenv(
    "VOSK_MODEL_URL",
    "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
)
VOSK_AUTO_DOWNLOAD = os.getenv("VOSK_AUTO_DOWNLOAD", "true").lower() == "true"
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
SEND_ASR_TEXT = os.getenv("SEND_ASR_TEXT", "false").lower() == "true"
SEND_ANSWER_TEXT = os.getenv("SEND_ANSWER_TEXT", "true").lower() == "true"

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
AUDIO_CHUNK_MS = env_int("AUDIO_CHUNK_MS", 40)
MAX_RECORDING_BYTES = env_int("MAX_RECORDING_BYTES", AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES * 12)
VAD_MIN_RECORDING_MS = env_int("VAD_MIN_RECORDING_MS", 900)
VAD_MAX_RECORDING_MS = env_int("VAD_MAX_RECORDING_MS", 12000)
VAD_SILENCE_RMS = env_int("VAD_SILENCE_RMS", 450)
VAD_SILENCE_CHUNKS = env_int("VAD_SILENCE_CHUNKS", 12)
VAD_PREROLL_MS = env_int("VAD_PREROLL_MS", 300)
VAD_POSTROLL_MS = env_int("VAD_POSTROLL_MS", 240)
MOCK_TTS_DURATION_MS = env_int("MOCK_TTS_DURATION_MS", 900)
MOCK_TTS_TONE_HZ = env_int("MOCK_TTS_TONE_HZ", 660)
LLM_TIMEOUT_SECONDS = env_int("LLM_TIMEOUT_SECONDS", 30)
LLM_MAX_TOKENS = env_int("LLM_MAX_TOKENS", 512)
TTS_TIMEOUT_SECONDS = env_int("TTS_TIMEOUT_SECONDS", 45)
LOG_RETENTION_DAYS = env_int("LOG_RETENTION_DAYS", 7)
SESSION_RETENTION_DAYS = env_int("SESSION_RETENTION_DAYS", 3)
ANSWER_MAX_CHARS = env_int("ANSWER_MAX_CHARS", 800)
TTS_MAX_CHARS = env_int("TTS_MAX_CHARS", 500)
TTS_PCM_CHUNK_MS = env_int("TTS_PCM_CHUNK_MS", 80)
LLM_SENTENCE_MAX_CHARS = max(16, env_int("LLM_SENTENCE_MAX_CHARS", 80))
TTS_SENTENCE_QUEUE_SIZE = env_int("TTS_SENTENCE_QUEUE_SIZE", 4)
QWEN_REALTIME_VAD_SILENCE_MS = env_int("QWEN_REALTIME_VAD_SILENCE_MS", 400)
QWEN_REALTIME_CONNECT_TIMEOUT_SECONDS = env_int("QWEN_REALTIME_CONNECT_TIMEOUT_SECONDS", 10)
QWEN_REALTIME_FINISH_TIMEOUT_SECONDS = env_int("QWEN_REALTIME_FINISH_TIMEOUT_SECONDS", 8)
CONVERSATION_MAX_TURNS = env_int("CONVERSATION_MAX_TURNS", 5)


@dataclass
class SettingsSnapshot:
    app_version: str
    asr_provider: str
    asr_primary: str
    asr_fallback: str
    asr_strategy: str
    asr_context: str
    asr_language: str
    asr_timeout_seconds: int
    audio_sample_rate: int
    audio_channels: int
    audio_sample_width_bytes: int
    vosk_model_dir: Path
    vosk_model_url: str
    vosk_auto_download: bool
    dashscope_api_key: str
    dashscope_asr_model: str
    dashscope_base_http_api_url: str
    ai_api_key: str
    ai_api_base: str
    ai_model: str
    model_config: dict[str, Any]


@dataclass
class VoiceSession:
    recording: bool = False
    pcm: bytearray = field(default_factory=bytearray)
    silence_chunks: int = 0
    turn_id: int = 0
    recording_path: Optional[Path] = None
    transcript_path: Optional[Path] = None
    answer_path: Optional[Path] = None
    audio_report_path: Optional[Path] = None
    meta_path: Optional[Path] = None
    recording_buffer: Optional[RecordingBuffer] = None
    protocol_version: int = 303
    history: list[dict[str, str]] = field(default_factory=list)
    processing_task: Optional[asyncio.Task[None]] = None
    realtime_asr: Optional[QwenRealtimeASRSession] = None
    realtime_event_task: Optional[asyncio.Task[None]] = None
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def reset_recording(self) -> None:
        self.recording = False
        self.pcm.clear()
        self.silence_chunks = 0
        self.recording_buffer = None

    def clear_transcript(self) -> None:
        self.recording_path = None
        self.transcript_path = None
        self.answer_path = None
        self.audio_report_path = None
        self.meta_path = None

    def remember_turn(self, transcript: str, answer: str) -> None:
        self.history.extend(
            [
                {"role": "user", "content": transcript},
                {"role": "assistant", "content": answer},
            ]
        )
        self.history = self.history[-(CONVERSATION_MAX_TURNS * 2) :]


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

    log_path = LOG_DIR / "cloud.log"
    if any(isinstance(handler, TimedRotatingFileHandler) and Path(handler.baseFilename) == log_path for handler in root_logger.handlers):
        return

    file_handler = TimedRotatingFileHandler(
        log_path,
        when="midnight",
        interval=1,
        backupCount=LOG_RETENTION_DAYS,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)


configure_logging()


def current_model_config() -> dict[str, Any]:
    return load_model_config(MODEL_CONFIG_PATH)


def current_settings() -> SettingsSnapshot:
    return SettingsSnapshot(
        app_version=APP_VERSION,
        asr_provider=ASR_PROVIDER,
        asr_primary=ASR_PRIMARY,
        asr_fallback=ASR_FALLBACK,
        asr_strategy=ASR_STRATEGY,
        asr_context=ASR_CONTEXT,
        asr_language=ASR_LANGUAGE,
        asr_timeout_seconds=ASR_TIMEOUT_SECONDS,
        audio_sample_rate=AUDIO_SAMPLE_RATE,
        audio_channels=AUDIO_CHANNELS,
        audio_sample_width_bytes=AUDIO_SAMPLE_WIDTH_BYTES,
        vosk_model_dir=VOSK_MODEL_DIR,
        vosk_model_url=VOSK_MODEL_URL,
        vosk_auto_download=VOSK_AUTO_DOWNLOAD,
        dashscope_api_key=DASHSCOPE_API_KEY,
        dashscope_asr_model=DASHSCOPE_ASR_MODEL,
        dashscope_base_http_api_url=DASHSCOPE_BASE_HTTP_API_URL,
        ai_api_key=DEEPSEEK_API_KEY or AI_API_KEY,
        ai_api_base=AI_API_BASE,
        ai_model=AI_MODEL,
        model_config=current_model_config(),
    )


def model_readiness(settings: SettingsSnapshot) -> dict[str, Any]:
    active_llm = active_item(settings.model_config, "llm_models")
    active_asr = active_item(settings.model_config, "asr_models")
    chain = provider_chain(settings)
    cloud_providers = {
        "qwen",
        "qwen_dashscope",
        "dashscope",
        "openai_audio",
        "openai_multimodal",
        "multimodal_llm",
        "custom_http",
    }
    chain_has_cloud_asr = any(name.lower().replace("-", "_") in cloud_providers for name in chain)
    active_asr_provider = str((active_asr or {}).get("provider") or "").lower().replace("-", "_")
    active_asr_has_key = bool((active_asr or {}).get("api_key"))
    active_asr_can_use_env_key = (
        active_asr_provider in {"qwen", "qwen_dashscope", "dashscope"} and bool(settings.dashscope_api_key)
    ) or (
        active_asr_provider in {"openai_audio", "openai_multimodal", "multimodal_llm", "custom_http"}
        and bool(settings.ai_api_key)
    )
    asr_configured = bool(active_asr_has_key or active_asr_can_use_env_key or settings.dashscope_api_key or chain_has_cloud_asr)
    llm_configured = bool(active_llm or DEEPSEEK_API_KEY or AI_API_KEY)
    warnings: list[str] = []

    if not asr_configured:
        warnings.append("cloud ASR is not configured; using local fallback chain")
    if not llm_configured and LLM_PROVIDER == "auto":
        warnings.append("LLM is not configured; auto mode uses the phase3 test answer")
    if "vosk" in chain and not settings.vosk_model_dir.exists():
        warnings.append("Vosk fallback model is missing; first local ASR may download it or fall back to phase2")
    active_llm_model = str((active_llm or {}).get("model") or AI_MODEL)
    active_llm_brand = str((active_llm or {}).get("brand") or AI_API_BASE).lower()
    if "deepseek" in active_llm_brand and active_llm_model in {"deepseek-chat", "deepseek-reasoner"}:
        warnings.append(
            f"DeepSeek compatibility alias {active_llm_model} is deprecated after 2026-07-24; use deepseek-v4-flash"
        )
    if CONFIGURED_APP_VERSION != APP_VERSION:
        warnings.append(
            f"APP_VERSION in .env is stale ({CONFIGURED_APP_VERSION}); running code is {APP_VERSION}"
        )

    return {
        "asr_configured": asr_configured,
        "llm_configured": llm_configured,
        "using_local_fallback": not chain_has_cloud_asr,
        "asr_provider_chain": chain,
        "active_asr_id": settings.model_config.get("active_asr_id", ""),
        "active_llm_id": settings.model_config.get("active_llm_id", ""),
        "warnings": warnings,
    }


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


async def send_session_json(
    websocket: WebSocket,
    session: VoiceSession,
    message_type: str,
    **fields: Any,
) -> None:
    async with session.send_lock:
        await send_json(websocket, message_type, **fields)


async def send_session_audio(websocket: WebSocket, session: VoiceSession, audio: bytes) -> None:
    async with session.send_lock:
        await websocket.send_bytes(audio)


def realtime_asr_configured() -> bool:
    return bool(
        QWEN_REALTIME_ENABLED
        and DASHSCOPE_API_KEY
        and (QWEN_REALTIME_WORKSPACE_ID or QWEN_REALTIME_WS_URL)
    )


def make_realtime_asr() -> QwenRealtimeASRSession:
    return QwenRealtimeASRSession(
        api_key=DASHSCOPE_API_KEY,
        workspace_id=QWEN_REALTIME_WORKSPACE_ID,
        model=QWEN_REALTIME_MODEL,
        region=QWEN_REALTIME_REGION,
        ws_url=QWEN_REALTIME_WS_URL,
        sample_rate=AUDIO_SAMPLE_RATE,
        language=ASR_LANGUAGE,
        vad_silence_ms=QWEN_REALTIME_VAD_SILENCE_MS,
        connect_timeout_seconds=QWEN_REALTIME_CONNECT_TIMEOUT_SECONDS,
        finish_timeout_seconds=QWEN_REALTIME_FINISH_TIMEOUT_SECONDS,
    )


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


def session_dirs() -> tuple[Path, ...]:
    return SESSION_RECORDINGS_DIR, SESSION_TRANSCRIPTS_DIR, SESSION_ANSWERS_DIR, SESSION_AUDIO_REPORT_DIR


def ensure_session_dirs() -> None:
    for directory in session_dirs():
        directory.mkdir(parents=True, exist_ok=True)


def cleanup_old_session_files() -> None:
    ensure_session_dirs()
    cutoff = time.time() - (SESSION_RETENTION_DAYS * 86400)
    for directory in session_dirs():
        for path in directory.iterdir():
            if not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                logger.warning("Failed to remove old session file path=%s", path, exc_info=True)


def session_file_stem(device_id: str, turn_id: int) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{safe_device_slug(device_id)}-turn-{turn_id:04d}"


def write_session_wav(stem: str, pcm: bytes) -> Path:
    ensure_session_dirs()
    path = SESSION_RECORDINGS_DIR / f"{stem}.wav"
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(AUDIO_CHANNELS)
        wav_file.setsampwidth(AUDIO_SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(pcm)
    return path


def write_session_text(directory: Path, stem: str, text: str) -> Path:
    ensure_session_dirs()
    path = directory / f"{stem}.txt"
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path


def write_session_json(directory: Path, stem: str, suffix: str, data: dict[str, Any]) -> Path:
    ensure_session_dirs()
    path = directory / f"{stem}{suffix}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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


def build_phase3_answer_from_text(transcript: str) -> str:
    transcript = transcript.strip()
    if not transcript:
        return "云端没有读取到有效识别文本，请重新唤醒后靠近麦克风完整说一遍。"

    return (
        "阶段三会话链路已跑通。录音、识别文本和 AI 回答已保存到 session 文件夹。"
        f"我识别到你说：{transcript}"
    )


def limit_text(text: str, max_chars: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max(0, max_chars - 3)].rstrip() + "..."


def strip_thinking_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def openai_compatible_chat(
    user_text: str,
    *,
    provider_name: str,
    api_key: str,
    base_url: str,
    model: str,
    history: Optional[list[dict[str, str]]] = None,
    disable_thinking: bool = False,
) -> str:
    if not api_key:
        raise RuntimeError(f"{provider_name} API key is not configured.")

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 ESP32-S3 私有语音机器人。回答要简短、直接、适合小屏幕滚动显示。"
                    "默认使用中文，不要输出 Markdown，不要输出思考过程。"
                ),
            },
            *(history or []),
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "temperature": 0.7,
        "max_tokens": LLM_MAX_TOKENS,
    }
    if disable_thinking:
        payload["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{provider_name} HTTP {exc.code}: {body[:240]}") from exc

    try:
        answer = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected {provider_name} response: {data}") from exc

    answer = strip_thinking_tags(answer)
    if not answer:
        raise RuntimeError(f"{provider_name} returned an empty answer.")
    return answer


def current_llm_target() -> tuple[str, str, str, str]:
    settings = current_settings()
    llm_config = active_item(settings.model_config, "llm_models")
    if llm_config:
        return (
            str(llm_config.get("brand") or "configured-llm"),
            str(llm_config.get("api_key") or ""),
            str(llm_config.get("base_url") or AI_API_BASE),
            str(llm_config.get("model") or AI_MODEL),
        )

    return "DeepSeek", DEEPSEEK_API_KEY or AI_API_KEY, AI_API_BASE, AI_MODEL


def target_supports_thinking_control(provider_name: str, base_url: str, model: str) -> bool:
    return "deepseek" in f"{provider_name} {base_url} {model}".lower()


def deepseek_chat(user_text: str, history: Optional[list[dict[str, str]]] = None) -> str:
    provider_name, api_key, base_url, model = current_llm_target()
    return openai_compatible_chat(
        user_text,
        provider_name=provider_name,
        api_key=api_key,
        base_url=base_url,
        model=model,
        history=history,
        disable_thinking=LLM_DISABLE_THINKING
        and target_supports_thinking_control(provider_name, base_url, model),
    )


async def build_answer_text(transcript: str, history: Optional[list[dict[str, str]]] = None) -> str:
    if LLM_PROVIDER == "phase3":
        return build_phase3_answer_from_text(transcript)

    settings = current_settings()
    has_configured_llm = active_item(settings.model_config, "llm_models") is not None
    has_env_key = bool(DEEPSEEK_API_KEY or AI_API_KEY)
    should_call_llm = LLM_PROVIDER in {"deepseek", "openai", "openai-compatible", "auto"} and (
        has_configured_llm or has_env_key or LLM_PROVIDER != "auto"
    )

    if should_call_llm:
        try:
            return await asyncio.to_thread(deepseek_chat, transcript, history)
        except Exception:
            if LLM_PROVIDER != "auto":
                raise
            logger.warning("Configured LLM failed in auto mode; falling back to phase3 answer.", exc_info=True)

    return build_phase3_answer_from_text(transcript)


async def stream_answer_chunks(
    transcript: str,
    history: Optional[list[dict[str, str]]] = None,
) -> AsyncIterator[str]:
    """Yield clean LLM deltas, with the existing non-streaming path as fallback."""

    if LLM_PROVIDER == "phase3" or not LLM_STREAMING_ENABLED:
        yield await build_answer_text(transcript, history)
        return

    settings = current_settings()
    has_configured_llm = active_item(settings.model_config, "llm_models") is not None
    has_env_key = bool(DEEPSEEK_API_KEY or AI_API_KEY)
    should_call_llm = LLM_PROVIDER in {"deepseek", "openai", "openai-compatible", "auto"} and (
        has_configured_llm or has_env_key or LLM_PROVIDER != "auto"
    )
    if not should_call_llm:
        yield build_phase3_answer_from_text(transcript)
        return

    provider_name, api_key, base_url, model = current_llm_target()
    emitted = False
    try:
        async for delta in stream_openai_compatible_chat(
            transcript,
            provider_name=provider_name,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=LLM_TIMEOUT_SECONDS,
            max_tokens=LLM_MAX_TOKENS,
            history=history,
            disable_thinking=LLM_DISABLE_THINKING
            and target_supports_thinking_control(provider_name, base_url, model),
        ):
            emitted = True
            yield delta
    except Exception:
        if emitted:
            logger.warning(
                "Streaming LLM ended after partial output; keeping the usable partial answer.",
                exc_info=True,
            )
            return
        if LLM_PROVIDER != "auto":
            raise
        logger.warning("Streaming LLM failed in auto mode; using the phase3 fallback answer.", exc_info=True)
        yield build_phase3_answer_from_text(transcript)


def ffmpeg_to_pcm_s16le(media_path: Path) -> bytes:
    ffmpeg_path = shutil.which(FFMPEG_BIN)
    if ffmpeg_path is None:
        candidate = Path(FFMPEG_BIN)
        if not candidate.exists():
            raise RuntimeError("ffmpeg is required for TTS_PROVIDER=edge but was not found in PATH.")
        ffmpeg_path = str(candidate)
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(media_path),
        "-ac",
        str(AUDIO_CHANNELS),
        "-ar",
        str(AUDIO_SAMPLE_RATE),
        "-f",
        "s16le",
        "pipe:1",
    ]
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=TTS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"ffmpeg failed to convert TTS audio: {error}")
    if not result.stdout:
        raise RuntimeError("ffmpeg produced empty TTS audio.")
    return result.stdout


def miniaudio_to_pcm_s16le(media_path: Path) -> bytes:
    try:
        import miniaudio
    except ImportError as exc:
        raise RuntimeError("miniaudio is not installed.") from exc

    decoded = miniaudio.decode(
        media_path.read_bytes(),
        output_format=miniaudio.SampleFormat.SIGNED16,
        nchannels=AUDIO_CHANNELS,
        sample_rate=AUDIO_SAMPLE_RATE,
    )
    samples = decoded.samples
    if hasattr(samples, "tobytes"):
        audio = samples.tobytes()
    else:
        audio = struct.pack(f"<{len(samples)}h", *samples)
    if not audio:
        raise RuntimeError("miniaudio produced empty TTS audio.")
    return audio


def media_to_pcm_s16le(media_path: Path) -> bytes:
    try:
        return miniaudio_to_pcm_s16le(media_path)
    except Exception:
        logger.warning("miniaudio failed to decode TTS media; trying ffmpeg fallback.", exc_info=True)
        return ffmpeg_to_pcm_s16le(media_path)


async def synthesize_edge_tts_pcm(text: str) -> bytes:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("TTS_PROVIDER=edge requires the edge-tts Python package.") from exc

    with tempfile.TemporaryDirectory(prefix="esp32-tts-") as tmp_dir:
        media_path = Path(tmp_dir) / "answer.mp3"
        communicate = edge_tts.Communicate(text=text, voice=EDGE_TTS_VOICE)
        await asyncio.wait_for(communicate.save(str(media_path)), timeout=TTS_TIMEOUT_SECONDS)
        return await asyncio.to_thread(media_to_pcm_s16le, media_path)


async def synthesize_tts_pcm(text: str) -> bytes:
    if TTS_PROVIDER == "edge":
        return await synthesize_edge_tts_pcm(limit_text(text, TTS_MAX_CHARS))
    return make_tone_pcm()


async def build_asr_turn(
    stem: str,
    wav_path: Path,
    audio_report: AudioReport,
    *,
    realtime_result: Optional[AsrResult] = None,
) -> tuple[AsrResult, Path, Path]:
    settings = current_settings()
    asr_result = realtime_result or await asyncio.to_thread(transcribe_with_fallback, wav_path, audio_report, settings)
    transcript_path = write_session_text(SESSION_TRANSCRIPTS_DIR, stem, asr_result.text)
    meta_path = write_session_json(
        SESSION_AUDIO_REPORT_DIR,
        stem,
        ".turn_meta",
        {
            "version": APP_VERSION,
            "asr": {
                "provider": asr_result.provider,
                "confidence": asr_result.confidence,
                "duration_ms": asr_result.duration_ms,
                "fallback_from": asr_result.fallback_from,
            },
            "audio_report": audio_report.to_dict(),
            "pipeline": {
                "llm_streaming": LLM_STREAMING_ENABLED,
                "sentence_max_chars": LLM_SENTENCE_MAX_CHARS,
                "tts_sentence_queue_size": TTS_SENTENCE_QUEUE_SIZE,
            },
        },
    )
    return asr_result, transcript_path, meta_path


async def send_pcm_paced(websocket: WebSocket, session: VoiceSession, audio: bytes) -> None:
    chunk_size = AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES * TTS_PCM_CHUNK_MS // 1000
    for start in range(0, len(audio), chunk_size):
        if session.cancelled.is_set():
            raise asyncio.CancelledError
        chunk = audio[start : start + chunk_size]
        await send_session_audio(websocket, session, chunk)
        await asyncio.sleep(len(chunk) / (AUDIO_SAMPLE_RATE * AUDIO_SAMPLE_WIDTH_BYTES))


async def stream_answer_and_audio(
    websocket: WebSocket,
    session: VoiceSession,
    *,
    transcript: str,
    history: list[dict[str, str]],
    stem: str,
    turn_id: int,
) -> tuple[str, Path]:
    """Run LLM, sentence TTS and PCM playback concurrently with bounded queues."""

    sentence_queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=TTS_SENTENCE_QUEUE_SIZE)
    audio_queue: asyncio.Queue[Optional[tuple[str, bytes]]] = asyncio.Queue(maxsize=TTS_SENTENCE_QUEUE_SIZE)

    async def produce_sentences() -> tuple[str, Path]:
        thinking_filter = ThinkingTagFilter()
        accumulator = SentenceAccumulator(LLM_SENTENCE_MAX_CHARS)
        answer_parts: list[str] = []
        sent_display_chars = 0
        answer_chars = 0
        generation_truncated = False

        async def consume_clean_text(clean_text: str) -> None:
            nonlocal answer_chars, generation_truncated, sent_display_chars
            if not clean_text:
                return
            remaining = TTS_MAX_CHARS - answer_chars
            if remaining <= 0:
                generation_truncated = True
                return
            if len(clean_text) > remaining:
                clean_text = clean_text[:remaining]
                generation_truncated = True
            answer_parts.append(clean_text)
            answer_chars += len(clean_text)
            if SEND_ANSWER_TEXT and sent_display_chars < ANSWER_MAX_CHARS:
                visible_delta = clean_text[: ANSWER_MAX_CHARS - sent_display_chars]
                if visible_delta:
                    await send_session_json(
                        websocket,
                        session,
                        "answer_delta",
                        text=visible_delta,
                        turn_id=turn_id,
                    )
                    sent_display_chars += len(visible_delta)
            for sentence in accumulator.feed(clean_text):
                await sentence_queue.put(sentence)

        async for delta in stream_answer_chunks(transcript, history):
            if session.cancelled.is_set():
                raise asyncio.CancelledError
            await consume_clean_text(thinking_filter.feed(delta))
            if generation_truncated:
                break
        if not generation_truncated:
            await consume_clean_text(thinking_filter.flush())
        for sentence in accumulator.flush():
            await sentence_queue.put(sentence)

        answer_text = "".join(answer_parts).strip()
        if not answer_text:
            raise RuntimeError("LLM returned an empty answer after filtering.")
        answer_path = write_session_text(SESSION_ANSWERS_DIR, stem, answer_text)
        if SEND_ANSWER_TEXT:
            display_answer = limit_text(answer_text, ANSWER_MAX_CHARS)
            await send_session_json(
                websocket,
                session,
                "answer_text",
                text=display_answer,
                turn_id=turn_id,
                answer_file=answer_path.name,
                answer_chars=len(answer_text),
                truncated=generation_truncated or display_answer != " ".join(answer_text.split()),
            )
        await sentence_queue.put(None)
        return answer_text, answer_path

    async def synthesize_sentences() -> None:
        while True:
            sentence = await sentence_queue.get()
            if sentence is None:
                await audio_queue.put(None)
                return
            audio = await synthesize_tts_pcm(sentence)
            await audio_queue.put((sentence, audio))

    async def play_audio() -> None:
        started = False
        while True:
            item = await audio_queue.get()
            if item is None:
                if not started:
                    raise RuntimeError("TTS pipeline produced no audio.")
                await send_session_json(websocket, session, "audio_end", turn_id=turn_id)
                return
            sentence, audio = item
            if not started:
                await send_session_json(websocket, session, "status", text="语音合成中...", state="tts", turn_id=turn_id)
                await send_session_json(
                    websocket,
                    session,
                    "audio_start",
                    sample_rate=AUDIO_SAMPLE_RATE,
                    format="pcm_s16le",
                    text=limit_text(sentence, ANSWER_MAX_CHARS),
                    turn_id=turn_id,
                )
                started = True
            await send_pcm_paced(websocket, session, audio)

    async with asyncio.TaskGroup() as task_group:
        producer_task = task_group.create_task(produce_sentences(), name=f"llm-turn-{turn_id}")
        task_group.create_task(synthesize_sentences(), name=f"tts-turn-{turn_id}")
        task_group.create_task(play_audio(), name=f"playback-turn-{turn_id}")

    return producer_task.result()


def make_vad_config() -> VadConfig:
    return VadConfig(
        min_recording_ms=VAD_MIN_RECORDING_MS,
        max_recording_ms=VAD_MAX_RECORDING_MS,
        silence_rms=VAD_SILENCE_RMS,
        silence_chunks=VAD_SILENCE_CHUNKS,
        chunk_ms=AUDIO_CHUNK_MS,
        preroll_ms=VAD_PREROLL_MS,
        postroll_ms=VAD_POSTROLL_MS,
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        sample_width_bytes=AUDIO_SAMPLE_WIDTH_BYTES,
    )


async def pump_realtime_asr_events(
    websocket: WebSocket,
    session: VoiceSession,
    asr: QwenRealtimeASRSession,
    turn_id: int,
) -> None:
    while session.realtime_asr is asr and session.turn_id == turn_id:
        event: RealtimeASREvent = await asr.events.get()
        if event.type == "partial":
            await send_session_json(websocket, session, "asr_partial", text=event.text, turn_id=turn_id)
        elif event.type == "final":
            await send_session_json(
                websocket,
                session,
                "asr_final",
                text=event.text,
                turn_id=turn_id,
                provider="qwen_realtime",
            )
        elif event.type == "speech_stopped":
            await send_session_json(websocket, session, "capture_stop", reason="server_vad", turn_id=turn_id)
        elif event.type == "error":
            logger.warning("Realtime ASR event turn=%d error=%s", turn_id, event.text)
            await send_session_json(websocket, session, "asr_warning", text=event.text, turn_id=turn_id)


async def close_realtime_asr(session: VoiceSession) -> None:
    asr = session.realtime_asr
    event_task = session.realtime_event_task
    session.realtime_asr = None
    session.realtime_event_task = None
    if asr is not None:
        await asr.close()
    if event_task is not None and event_task is not asyncio.current_task() and not event_task.done():
        event_task.cancel()
        await asyncio.gather(event_task, return_exceptions=True)


async def cancel_active_turn(
    websocket: WebSocket,
    session: VoiceSession,
    *,
    notify: bool,
    clear_history: bool = False,
) -> None:
    turn_id = session.turn_id
    session.cancelled.set()
    session.reset_recording()
    task = session.processing_task
    session.processing_task = None
    if task is not None and task is not asyncio.current_task() and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await close_realtime_asr(session)
    session.clear_transcript()
    if clear_history:
        session.history.clear()
    if notify:
        await send_session_json(websocket, session, "turn_cancelled", turn_id=turn_id)
        await send_session_json(
            websocket,
            session,
            "status",
            text="已取消，等待唤醒",
            state="idle",
            turn_id=turn_id,
        )


async def start_turn(
    websocket: WebSocket,
    session: VoiceSession,
    payload: dict[str, Any],
) -> None:
    if session.recording or session.processing_task is not None or session.realtime_asr is not None:
        await cancel_active_turn(websocket, session, notify=False)

    requested_turn_id = payload.get("turn_id")
    if isinstance(requested_turn_id, int) and requested_turn_id > session.turn_id:
        session.turn_id = requested_turn_id
    else:
        session.turn_id += 1
    requested_protocol = payload.get("protocol")
    if isinstance(requested_protocol, int):
        session.protocol_version = requested_protocol

    session.clear_transcript()
    session.reset_recording()
    session.cancelled = asyncio.Event()
    session.recording = True
    session.recording_buffer = RecordingBuffer(make_vad_config())

    realtime_ready = False
    if realtime_asr_configured():
        asr = make_realtime_asr()
        try:
            await asr.start()
            session.realtime_asr = asr
            session.realtime_event_task = asyncio.create_task(
                pump_realtime_asr_events(websocket, session, asr, session.turn_id),
                name=f"qwen-events-turn-{session.turn_id}",
            )
            realtime_ready = True
        except Exception:
            logger.warning("Unable to start Qwen realtime ASR; this turn will use batch fallback.", exc_info=True)
            await asr.close()

    if str(payload.get("type") or "").strip().lower() == "turn_start":
        await send_session_json(
            websocket,
            session,
            "turn_ready",
            turn_id=session.turn_id,
            protocol=PROTOCOL_VERSION,
            realtime_asr=realtime_ready,
        )
    await send_session_json(
        websocket,
        session,
        "status",
        text="录音中...",
        state="recording",
        turn_id=session.turn_id,
    )


async def finish_recording(websocket: WebSocket, session: VoiceSession, device_id: str, reason: str) -> None:
    turn_id = session.turn_id
    if not session.pcm:
        await send_session_json(websocket, session, "error", text="没有收到有效 PCM 音频。", turn_id=turn_id)
        session.reset_recording()
        await close_realtime_asr(session)
        return

    pcm = bytes(session.pcm)
    vad_diagnostics = session.recording_buffer.diagnostics() if session.recording_buffer else {}
    session.reset_recording()

    cleanup_old_session_files()
    stem = session_file_stem(device_id, turn_id)
    session.recording_path = write_session_wav(stem, pcm)
    debug_wav_path = write_debug_wav(device_id, turn_id, pcm)
    audio_report = analyze_pcm16le(
        pcm,
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        sample_width_bytes=AUDIO_SAMPLE_WIDTH_BYTES,
        silence_rms=VAD_SILENCE_RMS,
        min_duration_s=VAD_MIN_RECORDING_MS / 1000.0,
    )
    report_data = audio_report.to_dict()
    report_data["finish_reason"] = reason
    report_data["vad"] = vad_diagnostics
    session.audio_report_path = SESSION_AUDIO_REPORT_DIR / f"{stem}.audio_report.json"
    session.audio_report_path.parent.mkdir(parents=True, exist_ok=True)
    session.audio_report_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    logger.info(
        "Processed audio turn=%d bytes=%d duration_s=%.2f rms=%.1f peak=%d verdict=%s reason=%s recording_path=%s debug_wav_path=%s",
        turn_id,
        len(pcm),
        audio_report.duration_s,
        audio_report.rms,
        audio_report.peak,
        audio_report.verdict,
        reason,
        session.recording_path,
        debug_wav_path,
    )

    try:
        await send_session_json(websocket, session, "status", text="识别中...", state="asr", turn_id=turn_id)
        realtime_result: Optional[AsrResult] = None
        if session.realtime_asr is not None:
            try:
                transcript = (await session.realtime_asr.finish()).strip()
                if transcript:
                    realtime_result = AsrResult(
                        text=transcript,
                        provider="qwen_realtime",
                        raw={"model": QWEN_REALTIME_MODEL},
                    )
            except Exception:
                logger.warning("Qwen realtime ASR did not produce a final result; using batch fallback.", exc_info=True)

        asr_result, session.transcript_path, session.meta_path = await build_asr_turn(
            stem=stem,
            wav_path=session.recording_path,
            audio_report=audio_report,
            realtime_result=realtime_result,
        )
        if realtime_result is None:
            await send_session_json(
                websocket,
                session,
                "asr_final",
                text=asr_result.text,
                turn_id=turn_id,
                provider=asr_result.provider,
            )
        if SEND_ASR_TEXT:
            await send_session_json(
                websocket,
                session,
                "asr_text",
                text=asr_result.text,
                turn_id=turn_id,
                transcript_file=session.transcript_path.name,
                provider=asr_result.provider,
            )

        await send_session_json(websocket, session, "status", text="思考中...", state="thinking", turn_id=turn_id)
        answer_text, session.answer_path = await stream_answer_and_audio(
            websocket,
            session,
            transcript=asr_result.text,
            history=list(session.history),
            stem=stem,
            turn_id=turn_id,
        )
        session.remember_turn(asr_result.text, answer_text)
        await send_session_json(websocket, session, "status", text="空闲，等待唤醒", state="idle", turn_id=turn_id)
    except asyncio.CancelledError:
        logger.info("Cancelled turn=%d device_id=%s", turn_id, device_id)
        raise
    except Exception:
        logger.exception("Failed to process turn=%d device_id=%s", turn_id, device_id)
        await send_session_json(websocket, session, "error", text="云端处理本轮语音失败，请查看 VPS 日志。", turn_id=turn_id)
        await send_session_json(websocket, session, "status", text="空闲，等待唤醒", state="idle", turn_id=turn_id)
    finally:
        await close_realtime_asr(session)
        session.clear_transcript()


def schedule_finish_recording(
    websocket: WebSocket,
    session: VoiceSession,
    device_id: str,
    reason: str,
) -> None:
    if session.processing_task is not None and not session.processing_task.done():
        logger.info("Ignored duplicate finish turn=%d reason=%s", session.turn_id, reason)
        return
    if not session.recording and not session.pcm:
        logger.info("Ignored finish_record device_id=%s because session is not recording", device_id)
        return
    session.recording = False
    task = asyncio.create_task(
        finish_recording(websocket, session, device_id, reason),
        name=f"voice-turn-{session.turn_id}",
    )
    session.processing_task = task

    def clear_finished_task(finished: asyncio.Task[None]) -> None:
        if session.processing_task is finished:
            session.processing_task = None
        if not finished.cancelled() and finished.exception() is not None:
            error = finished.exception()
            logger.error(
                "Voice turn task ended unexpectedly",
                exc_info=(type(error), error, error.__traceback__),
            )

    task.add_done_callback(clear_finished_task)


async def handle_json_message(websocket: WebSocket, session: VoiceSession, device_id: str, payload: dict[str, Any]) -> None:
    message_type = str(payload.get("type", "")).strip().lower()

    if message_type == "hello":
        requested_protocol = payload.get("protocol")
        if isinstance(requested_protocol, int):
            session.protocol_version = requested_protocol
        await send_session_json(
            websocket,
            session,
            "hello",
            protocol=PROTOCOL_VERSION,
            version=APP_VERSION,
            audio={"format": "pcm_s16le", "sample_rate": AUDIO_SAMPLE_RATE, "channels": AUDIO_CHANNELS},
            capabilities=["asr_partial", "answer_delta", "sentence_tts", "barge_in", "cancel", "legacy_v303"],
        )
        return

    if message_type in {"turn_start", "start_record"}:
        await start_turn(websocket, session, payload)
        return

    if message_type in {"turn_end", "finish_record", "vad_end"}:
        schedule_finish_recording(websocket, session, device_id, message_type)
        return

    if message_type == "audio_stats":
        logger.info("ESP32 audio_stats device_id=%s payload=%s", device_id, payload)
        return

    if message_type == "cancel":
        await cancel_active_turn(websocket, session, notify=True)
        return

    if message_type == "stop":
        await cancel_active_turn(websocket, session, notify=False, clear_history=True)
        await send_session_json(
            websocket,
            session,
            "status",
            text="已结束对话",
            state="idle",
            turn_id=session.turn_id,
        )
        return

    if message_type == "ping":
        await send_session_json(
            websocket,
            session,
            "status",
            text="phase4 ok",
            state="idle",
            protocol=PROTOCOL_VERSION,
        )
        return

    await send_session_json(websocket, session, "error", text=f"未知消息类型: {message_type or '<empty>'}")


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
        schedule_finish_recording(websocket, session, device_id, "max_recording_bytes")
        return

    session.pcm.extend(data)
    if session.realtime_asr is not None:
        try:
            await session.realtime_asr.append_audio(data)
        except Exception:
            logger.warning("Failed to stream PCM to realtime ASR; keeping batch fallback.", exc_info=True)
            await close_realtime_asr(session)
    if session.recording_buffer is None:
        session.recording_buffer = RecordingBuffer(make_vad_config())
    should_finish, finish_reason = session.recording_buffer.feed(data)
    session.silence_chunks = session.recording_buffer.silence_chunks_seen
    if should_finish:
        schedule_finish_recording(websocket, session, device_id, finish_reason or "vad")


@app.get("/health")
async def health() -> JSONResponse:
    ensure_session_dirs()
    settings = current_settings()
    config = settings.model_config
    readiness = model_readiness(settings)
    return JSONResponse(
        {
            "ok": True,
            "service": APP_NAME,
            "version": APP_VERSION,
            "configured_app_version": CONFIGURED_APP_VERSION,
            "version_config_matches": CONFIGURED_APP_VERSION == APP_VERSION,
            "phase": APP_PHASE,
            "protocol": PROTOCOL_VERSION,
            "protocol_compatibility": [303, PROTOCOL_VERSION],
            "token_required": not ALLOW_EMPTY_TOKEN,
            "max_ws_message_bytes": MAX_WS_MESSAGE_BYTES,
            "max_recording_bytes": MAX_RECORDING_BYTES,
            "audio": {
                "sample_rate": AUDIO_SAMPLE_RATE,
                "channels": AUDIO_CHANNELS,
                "sample_width_bytes": AUDIO_SAMPLE_WIDTH_BYTES,
                "format": "pcm_s16le",
                "chunk_ms": AUDIO_CHUNK_MS,
            },
            "vad": {
                "min_recording_ms": VAD_MIN_RECORDING_MS,
                "max_recording_ms": VAD_MAX_RECORDING_MS,
                "silence_rms": VAD_SILENCE_RMS,
                "silence_chunks": VAD_SILENCE_CHUNKS,
                "preroll_ms": VAD_PREROLL_MS,
                "postroll_ms": VAD_POSTROLL_MS,
            },
            "ai_api_key_configured": bool(AI_API_KEY or DEEPSEEK_API_KEY or active_item(config, "llm_models")),
            "asr_provider": ASR_PROVIDER,
            "asr_strategy": ASR_STRATEGY,
            "asr_provider_chain": readiness["asr_provider_chain"],
            "model_readiness": readiness,
            "llm_provider": LLM_PROVIDER,
            "llm_streaming_enabled": LLM_STREAMING_ENABLED,
            "llm_disable_thinking": LLM_DISABLE_THINKING,
            "llm_max_tokens": LLM_MAX_TOKENS,
            "llm_sentence_max_chars": LLM_SENTENCE_MAX_CHARS,
            "tts_provider": TTS_PROVIDER,
            "tts_mode": "local-test-tone" if TTS_PROVIDER == "tone" else TTS_PROVIDER,
            "session_dir": str(SESSION_DIR),
            "session_retention_days": SESSION_RETENTION_DAYS,
            "session_dirs": {
                "recordings": str(SESSION_RECORDINGS_DIR),
                "transcripts": str(SESSION_TRANSCRIPTS_DIR),
                "answers": str(SESSION_ANSWERS_DIR),
                "audio_report": str(SESSION_AUDIO_REPORT_DIR),
            },
            "conversation_dir": str(CONVERSATION_DIR),
            "conversation_storage": "session-files-retention-cleanup",
            "save_debug_wav": SAVE_DEBUG_WAV,
            "debug_audio_dir": str(DEBUG_AUDIO_DIR),
            "vosk_model_dir": str(VOSK_MODEL_DIR),
            "vosk_model_exists": VOSK_MODEL_DIR.exists(),
            "vosk_auto_download": VOSK_AUTO_DOWNLOAD,
            "dashscope_asr_model": DASHSCOPE_ASR_MODEL,
            "dashscope_key_configured": bool(DASHSCOPE_API_KEY),
            "qwen_realtime": {
                "enabled": QWEN_REALTIME_ENABLED,
                "configured": realtime_asr_configured(),
                "model": QWEN_REALTIME_MODEL,
                "region": QWEN_REALTIME_REGION,
                "workspace_configured": bool(QWEN_REALTIME_WORKSPACE_ID),
                "custom_ws_url_configured": bool(QWEN_REALTIME_WS_URL),
                "vad_silence_ms": QWEN_REALTIME_VAD_SILENCE_MS,
            },
            "edge_tts_voice": EDGE_TTS_VOICE,
            "tts_decoder": "miniaudio-primary-ffmpeg-fallback",
            "ffmpeg_bin": FFMPEG_BIN,
            "answer_max_chars": ANSWER_MAX_CHARS,
            "tts_max_chars": TTS_MAX_CHARS,
            "tts_pcm_chunk_ms": TTS_PCM_CHUNK_MS,
            "tts_sentence_queue_size": TTS_SENTENCE_QUEUE_SIZE,
            "conversation_max_turns": CONVERSATION_MAX_TURNS,
            "send_asr_text": SEND_ASR_TEXT,
            "send_answer_text": SEND_ANSWER_TEXT,
            "model_config_path": str(MODEL_CONFIG_PATH),
            "model_config_exists": MODEL_CONFIG_PATH.exists(),
            "models": masked_config_summary(config),
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
    await send_session_json(websocket, session, "status", text="云端已连接，等待唤醒", state="idle")

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
                    await send_session_json(websocket, session, "error", text="协议 v4 需要 JSON 文本消息。")
                    continue

                if not isinstance(payload, dict):
                    await send_session_json(websocket, session, "error", text="JSON 消息必须是对象。")
                    continue

                await handle_json_message(websocket, session, device_id, payload)

            elif "bytes" in message and message["bytes"] is not None:
                await handle_binary_message(websocket, session, device_id, message["bytes"])

    except WebSocketDisconnect:
        logger.info("ESP32 disconnected peer=%s device_id=%s", peer, device_id)
    finally:
        await cancel_active_turn(websocket, session, notify=False)
