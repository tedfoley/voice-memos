"""Local transcription with whisper.cpp.

Audio is converted to 16 kHz mono WAV with ffmpeg and transcribed entirely on
this machine. No audio bytes ever touch the network — only the resulting
transcript text is sent onward.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .config import Config


class TranscriptionError(RuntimeError):
    pass


def transcribe(cfg: Config, audio_path: Path) -> str:
    if not cfg.whisper_model.exists():
        raise TranscriptionError(f"whisper model not found: {cfg.whisper_model}")

    with tempfile.TemporaryDirectory(prefix="memo-pipe-") as tmp:
        wav = Path(tmp) / "audio.wav"
        ffmpeg = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(audio_path),
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                str(wav),
            ],
            capture_output=True,
            text=True,
        )
        if ffmpeg.returncode != 0:
            raise TranscriptionError(f"ffmpeg failed: {ffmpeg.stderr.strip()}")

        out_base = Path(tmp) / "transcript"
        whisper = subprocess.run(
            [
                cfg.whisper_bin,
                "-m", str(cfg.whisper_model),
                "-f", str(wav),
                "--output-txt",
                "--output-file", str(out_base),
                "--no-prints",
            ],
            capture_output=True,
            text=True,
        )
        if whisper.returncode != 0:
            raise TranscriptionError(f"whisper.cpp failed: {whisper.stderr.strip()}")

        txt = out_base.with_suffix(".txt")
        if not txt.exists():
            raise TranscriptionError("whisper.cpp produced no transcript file")
        transcript = txt.read_text().strip()

    if not transcript:
        raise TranscriptionError("empty transcript")
    return transcript
