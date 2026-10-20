"""Constant-Q cepstral coefficient extraction."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from scipy.fftpack import dct


@dataclass(frozen=True)
class CQCCConfig:
    """CPU-oriented CQCC settings."""

    sample_rate: int = 16000
    n_coefficients: int = 20
    bins_per_octave: int = 24
    n_bins: int = 144
    fmin: float = 32.70319566257483
    hop_length: int = 160


def extract_cqcc(audio: np.ndarray, config: CQCCConfig) -> np.ndarray:
    """Return CQCC frames as (coefficients, time), using a documented approximation."""

    if audio.ndim != 1:
        raise ValueError("audio must be a one-dimensional waveform")
    if audio.size < config.hop_length * 2:
        audio = np.pad(audio, (0, config.hop_length * 2 - audio.size))
    # This is our implementation of the CQCC recipe associated with Todisco et al.;
    # verify parameterization against the original paper before publication.
    constant_q = np.abs(
        librosa.cqt(
            np.asarray(audio, dtype=np.float32),
            sr=config.sample_rate,
            hop_length=config.hop_length,
            fmin=config.fmin,
            bins_per_octave=config.bins_per_octave,
            n_bins=config.n_bins,
        )
    ) ** 2
    log_power = np.log(np.maximum(constant_q, np.finfo(np.float32).eps))
    coefficients = dct(log_power, type=2, axis=0, norm="ortho")[: config.n_coefficients]
    result = np.asarray(coefficients, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError("CQCC extraction produced non-finite values")
    return result


def summarize_cqcc(frames: np.ndarray) -> np.ndarray:
    """Return fixed-length mean/std CQCC summary."""

    if frames.ndim != 2 or frames.shape[1] == 0:
        raise ValueError("frames must have shape (coefficients, frames) with non-zero frames")
    result = np.concatenate((frames.mean(axis=1), frames.std(axis=1))).astype(np.float32)
    if not np.isfinite(result).all():
        raise ValueError("CQCC summary produced non-finite values")
    return result