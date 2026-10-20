"""Telephone-style band-limiting simulation."""

from __future__ import annotations

import librosa
import numpy as np
from scipy.signal import butter, sosfilt


def telephone_bandlimit(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Band-limit to approximately 300-3400 Hz through an 8 kHz channel and back."""

    downsampled = librosa.resample(np.asarray(audio, dtype=np.float32), orig_sr=sample_rate, target_sr=8000)
    high_frequency = min(3400.0, 0.45 * 8000.0)
    sections = butter(6, [300.0, high_frequency], btype="bandpass", fs=8000, output="sos")
    filtered = sosfilt(sections, downsampled).astype(np.float32)
    return np.asarray(librosa.resample(filtered, orig_sr=8000, target_sr=sample_rate), dtype=np.float32)