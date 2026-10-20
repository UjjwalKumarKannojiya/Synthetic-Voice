"""MFCC extraction and fixed-length per-clip summaries."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass(frozen=True)
class MFCCConfig:
    """MFCC settings for CPU-friendly baseline features."""

    sample_rate: int = 16000
    n_mfcc: int = 20
    include_delta: bool = True
    include_delta_delta: bool = True
    n_fft: int = 400
    hop_length: int = 160
    n_mels: int = 40


def extract_mfcc(audio: np.ndarray, config: MFCCConfig) -> np.ndarray:
    """Return MFCC, optional deltas, and delta-deltas as float32 frames."""

    if audio.ndim != 1:
        raise ValueError("audio must be a one-dimensional waveform")
    if audio.size < config.n_fft:
        audio = np.pad(audio, (0, config.n_fft - audio.size))
    mfcc = librosa.feature.mfcc(
        y=np.asarray(audio, dtype=np.float32),
        sr=config.sample_rate,
        n_mfcc=config.n_mfcc,
        n_fft=config.n_fft,
        hop_length=config.hop_length,
        n_mels=config.n_mels,
    )
    features = [mfcc]
    if config.include_delta:
        features.append(librosa.feature.delta(mfcc))
    if config.include_delta_delta:
        features.append(librosa.feature.delta(mfcc, order=2))
    result = np.concatenate(features, axis=0).astype(np.float32, copy=False)
    if not np.isfinite(result).all():
        raise ValueError("MFCC extraction produced non-finite values")
    return result


def summarize_mfcc(frames: np.ndarray) -> np.ndarray:
    """Summarize feature frames into a fixed-length mean/std vector."""

    if frames.ndim != 2 or frames.shape[1] == 0:
        raise ValueError("frames must have shape (features, frames) with non-zero frames")
    summary = np.concatenate((frames.mean(axis=1), frames.std(axis=1))).astype(np.float32)
    if not np.isfinite(summary).all():
        raise ValueError("MFCC summary produced non-finite values")
    return summary