"""Deterministic additive-noise transformations."""

from __future__ import annotations

import numpy as np


def add_white_noise(audio: np.ndarray, snr_db: float, seed: int) -> np.ndarray:
    """Add white Gaussian noise at the requested signal-to-noise ratio."""

    rng = np.random.default_rng(seed)
    signal_power = float(np.mean(np.square(audio), dtype=np.float64))
    if signal_power == 0.0:
        return np.asarray(audio, dtype=np.float32).copy()
    noise_power = signal_power / (10.0 ** (snr_db / 10.0))
    noise = rng.normal(0.0, np.sqrt(noise_power), size=audio.shape).astype(np.float32)
    return np.asarray(audio + noise, dtype=np.float32)