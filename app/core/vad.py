"""Small, deterministic energy gate for speech-window selection."""

from __future__ import annotations

import numpy as np


def speech_present(audio: np.ndarray, threshold: float = 0.01) -> bool:
    """Return whether an audio window has enough RMS energy to score."""

    if audio.ndim != 1:
        raise ValueError("audio must be one-dimensional")
    if threshold < 0.0:
        raise ValueError("threshold must not be negative")
    if audio.size == 0:
        return False
    if not np.isfinite(audio).all():
        raise ValueError("audio contains non-finite samples")
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    return rms >= threshold
