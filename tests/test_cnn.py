import numpy as np
import torch

from src.svf.features.spectrogram import SpectrogramConfig, extract_log_mel
from src.svf.models.cnn import SmallLogMelCNN


def test_log_mel_and_cnn_shapes() -> None:
    config = SpectrogramConfig()
    audio = np.zeros(config.sample_rate, dtype=np.float32)
    spectrogram = extract_log_mel(audio, config)
    model = SmallLogMelCNN()
    output = model(torch.from_numpy(spectrogram[None, None, :, :]))

    assert spectrogram.shape == (64, 200)
    assert spectrogram.dtype == np.float32
    assert output.shape == (1,)
    assert output.dtype == torch.float32