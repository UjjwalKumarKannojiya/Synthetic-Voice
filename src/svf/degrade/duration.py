"""Fixed-duration crop and pad transformations."""

from __future__ import annotations

import numpy as np


def center_crop_or_pad(audio: np.ndarray, sample_rate: int, seconds: float) -> np.ndarray:
    """Center-crop or zero-pad audio to the requested duration."""

    if seconds <= 0:
        raise ValueError("seconds must be positive")
    target_length = int(round(sample_rate * seconds))
    if audio.size >= target_length:
        start = (audio.size - target_length) // 2
        return np.asarray(audio[start : start + target_length], dtype=np.float32)
    result = np.zeros(target_length, dtype=np.float32)
    start = (target_length - audio.size) // 2
    result[start : start + audio.size] = audio
    return result