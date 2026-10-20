import numpy as np

from src.svf.features.cqcc import CQCCConfig, extract_cqcc, summarize_cqcc


def test_cqcc_shape_and_finite_values() -> None:
    sample_rate = 16000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    audio = 0.2 * np.sin(2 * np.pi * 220 * time)
    config = CQCCConfig(sample_rate=sample_rate)

    frames = extract_cqcc(audio, config)
    summary = summarize_cqcc(frames)

    assert frames.shape[0] == 20
    assert summary.shape == (40,)
    assert frames.dtype == np.float32
    assert summary.dtype == np.float32
    assert np.isfinite(frames).all()
    assert np.isfinite(summary).all()