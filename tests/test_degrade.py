import numpy as np

from src.svf.degrade.duration import center_crop_or_pad
from src.svf.degrade.noise import add_white_noise
from src.svf.degrade.telephone import telephone_bandlimit


def test_noise_is_reproducible() -> None:
    audio = np.ones(16000, dtype=np.float32)

    first = add_white_noise(audio, snr_db=10.0, seed=7)
    second = add_white_noise(audio, snr_db=10.0, seed=7)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, audio)


def test_duration_crop_and_pad_shape() -> None:
    audio = np.ones(16000, dtype=np.float32)

    assert center_crop_or_pad(audio, 16000, 1.0).shape == (16000,)
    assert center_crop_or_pad(audio, 16000, 3.0).shape == (48000,)


def test_telephone_output_is_finite() -> None:
    audio = np.sin(np.linspace(0, 10, 16000)).astype(np.float32)

    result = telephone_bandlimit(audio, 16000)

    assert result.dtype == np.float32
    assert np.isfinite(result).all()