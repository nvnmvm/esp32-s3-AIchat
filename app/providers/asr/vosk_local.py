from __future__ import annotations

import json
import shutil
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any

from app.core.audio_utils import AudioReport
from app.providers.asr.base import ASRProvider, AsrResult


class VoskLocalASRProvider(ASRProvider):
    name = "vosk"
    _model: Any = None

    def __init__(
        self,
        *,
        model_dir: Path,
        model_url: str,
        auto_download: bool,
        sample_rate: int,
    ):
        self.model_dir = model_dir
        self.model_url = model_url
        self.auto_download = auto_download
        self.sample_rate = sample_rate

    def _download_model(self) -> None:
        if self.model_dir.exists():
            return
        self.model_dir.parent.mkdir(parents=True, exist_ok=True)
        archive_path = self.model_dir.parent / (Path(self.model_url).name or "vosk-model.zip")
        with urllib.request.urlopen(self.model_url, timeout=120) as response:
            with archive_path.open("wb") as output:
                shutil.copyfileobj(response, output)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(self.model_dir.parent)
        archive_path.unlink(missing_ok=True)
        if not self.model_dir.exists():
            raise RuntimeError(f"Vosk model was downloaded, but expected directory is missing: {self.model_dir}")

    def _get_model(self) -> Any:
        if self.__class__._model is not None:
            return self.__class__._model
        if not self.model_dir.exists():
            if self.auto_download:
                self._download_model()
            else:
                raise RuntimeError(f"Vosk model directory does not exist: {self.model_dir}")
        try:
            from vosk import Model, SetLogLevel
        except ImportError as exc:
            raise RuntimeError("ASR_PROVIDER=vosk requires the vosk Python package.") from exc
        SetLogLevel(-1)
        self.__class__._model = Model(str(self.model_dir))
        return self.__class__._model

    def transcribe(self, wav_path: Path, audio_report: AudioReport, *, context: str = "") -> AsrResult:
        try:
            from vosk import KaldiRecognizer
        except ImportError as exc:
            raise RuntimeError("ASR_PROVIDER=vosk requires the vosk Python package.") from exc

        model = self._get_model()
        results: list[str] = []
        with wave.open(str(wav_path), "rb") as wav_file:
            if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
                raise RuntimeError("Vosk ASR expects mono 16-bit WAV audio.")
            if wav_file.getframerate() != self.sample_rate:
                raise RuntimeError(f"Vosk ASR expects {self.sample_rate} Hz WAV audio.")

            recognizer = KaldiRecognizer(model, wav_file.getframerate())
            while True:
                chunk = wav_file.readframes(4000)
                if not chunk:
                    break
                if recognizer.AcceptWaveform(chunk):
                    part = json.loads(recognizer.Result()).get("text", "").strip()
                    if part:
                        results.append(part)

            final = json.loads(recognizer.FinalResult()).get("text", "").strip()
            if final:
                results.append(final)

        text = " ".join(results).strip()
        if not text:
            text = "没有识别到有效语音，请靠近麦克风再说一遍。"
        return AsrResult(text=text, provider=self.name)
