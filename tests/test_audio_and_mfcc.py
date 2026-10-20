import numpy as np

from src.svf.audio_io import AudioConfig
from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc


def test_mfcc_summary_shape_and_finite_values() -> None:
    sample_rate = 16000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    audio = 0.2 * np.sin(2 * np.pi * 220 * time)
    config = MFCCConfig(sample_rate=sample_rate)

    frames = extract_mfcc(audio, config)
    summary = summarize_mfcc(frames)

    assert frames.shape[0] == 60
    assert summary.shape == (120,)
    assert frames.dtype == np.float32
    assert summary.dtype == np.float32
    assert np.isfinite(frames).all()
    assert np.isfinite(summary).all()


def test_audio_config_keeps_risky_transforms_disabled_by_default() -> None:
    config = AudioConfig()

    assert config.trim_silence is False
    assert config.normalize is False