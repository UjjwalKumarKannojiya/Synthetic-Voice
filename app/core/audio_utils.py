"""Audio decoding helpers used by the API and detector."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.svf.audio_io import AudioConfig, load_audio


def decode_audio_file(path: str | Path, sample_rate: int = 16000) -> tuple[np.ndarray, int]:
    """Decode one file through the repository's shared preprocessing path."""

    audio, actual_rate = load_audio(path, AudioConfig(sample_rate=sample_rate))
    if audio.ndim != 1 or not np.isfinite(audio).all():
        raise ValueError("decoded audio must be finite mono audio")
    return audio, actual_rate


def pcm16_to_float32(payload: bytes) -> np.ndarray:
    """Decode a little-endian mono PCM16 frame payload."""

    if len(payload) % 2:
        raise ValueError("PCM16 payload must contain an even number of bytes")
    samples = np.frombuffer(payload, dtype="<i2")
    return (samples.astype(np.float32) / 32768.0).copy()
