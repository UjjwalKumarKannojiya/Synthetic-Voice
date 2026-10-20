import numpy as np

from src.svf.features.spectrogram import SpectrogramConfig, extract_log_mel


def test_log_mel_is_fixed_and_finite() -> None:
    config = SpectrogramConfig()
    audio = np.random.default_rng(3).normal(size=config.sample_rate).astype(np.float32)

    result = extract_log_mel(audio, config)

    assert result.shape == (64, 200)
    assert np.isfinite(result).all()