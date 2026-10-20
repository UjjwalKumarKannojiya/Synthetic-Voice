"""Shared audio loading and preprocessing used by every model path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class AudioConfig:
    """Audio settings; trimming and normalization remain disabled by default."""

    sample_rate: int = 16000
    mono: bool = True
    trim_silence: bool = False
    normalize: bool = False


def load_audio(path: str | Path, config: AudioConfig) -> tuple[np.ndarray, int]:
    """Load one file, apply shared preprocessing, and return float32 audio."""

    audio, sample_rate = sf.read(Path(path), dtype="float32", always_2d=False)
    if audio.ndim == 2:
        if not config.mono:
            raise ValueError("multichannel audio is not supported when mono=False")
        audio = np.mean(audio, axis=1, dtype=np.float32)
    audio = np.asarray(audio, dtype=np.float32)
    if sample_rate != config.sample_rate:
        audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=config.sample_rate)
        sample_rate = config.sample_rate
    if config.trim_silence:
        audio, _ = librosa.effects.trim(audio)
    if config.normalize:
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 0.0:
            audio = audio / peak
    return np.ascontiguousarray(audio, dtype=np.float32), sample_rate