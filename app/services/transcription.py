from __future__ import annotations

import os
import shutil

try:
    import whisper
except Exception:
    whisper = None


class TranscriptionError(Exception):
    pass


class TranscriptionService:
    _model = None

    def __init__(self, model_name: str = "base", ffmpeg_location: str = ""):
        self.model_name = model_name
        if whisper is None:
            raise TranscriptionError("openai-whisper is not installed")
        if ffmpeg_location:
            if os.path.isdir(ffmpeg_location):
                os.environ["PATH"] = ffmpeg_location + os.pathsep + os.environ.get("PATH", "")
            elif os.path.isfile(ffmpeg_location):
                ffmpeg_dir = os.path.dirname(ffmpeg_location)
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        if not shutil.which("ffmpeg"):
            raise TranscriptionError("ffmpeg not found for transcription. Install ffmpeg or set FFMPEG_LOCATION in .env")
        if TranscriptionService._model is None:
            TranscriptionService._model = whisper.load_model(self.model_name)

    def transcribe(self, audio_path: str) -> str:
        if not audio_path or not os.path.isfile(audio_path):
            return ""
        try:
            result = TranscriptionService._model.transcribe(audio_path, fp16=False)
        except Exception as exc:
            raise TranscriptionError("Whisper failed to transcribe audio") from exc
        if not isinstance(result, dict):
            raise TranscriptionError("Whisper returned invalid response")
        return (result.get("text") or "").strip()

