"""Fixed-shape log-mel spectrogram extraction."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass(frozen=True)
class SpectrogramConfig:
    """CPU-friendly fixed-shape log-mel settings."""

    sample_rate: int = 16000
    n_mels: int = 64
    n_fft: int = 400
    hop_length: int = 160
    frames: int = 200


def extract_log_mel(audio: np.ndarray, config: SpectrogramConfig) -> np.ndarray:
    """Return a normalized float32 log-mel image with fixed dimensions."""

    target_length = (config.frames - 1) * config.hop_length + config.n_fft
    if audio.size < target_length:
        audio = np.pad(audio, (0, target_length - audio.size))
    else:
        start = (audio.size - target_length) // 2
        audio = audio[start : start + target_length]
    mel = librosa.feature.melspectrogram(
        y=np.asarray(audio, dtype=np.float32),
        sr=config.sample_rate,
        n_fft=config.n_fft,
        hop_length=config.hop_length,
        n_mels=config.n_mels,
        power=2.0,
    )
    log_mel = librosa.power_to_db(mel, ref=np.max)
    log_mel = log_mel[:, : config.frames]
    if log_mel.shape[1] < config.frames:
        log_mel = np.pad(log_mel, ((0, 0), (0, config.frames - log_mel.shape[1])))
    result = np.asarray(log_mel, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError("log-mel extraction produced non-finite values")
    return result