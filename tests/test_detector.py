import numpy as np

from app.core.detector import Detector
from app.core.vad import speech_present
from app.core.verdict import verdict_for_score


def test_verdict_band_and_silence_gate() -> None:
    assert verdict_for_score(0.1, 0.5, 0.05) == "Likely Real"
    assert verdict_for_score(0.5, 0.5, 0.05) == "Uncertain"
    assert verdict_for_score(0.9, 0.5, 0.05) == "Likely Synthetic"
    assert not speech_present(np.zeros(16000, dtype=np.float32))


def test_detector_returns_uncertain_for_silent_audio() -> None:
    detector = Detector()
    result = detector.analyze_array(np.zeros(32000, dtype=np.float32), 16000)

    assert result["verdict"] == "Uncertain"
    assert result["mean_prob"] is None
    assert result["max_prob"] is None
    assert result["speech_ratio"] == 0.0
    assert len(result["windows"]) == 1


def test_detector_scores_one_model_window() -> None:
    detector = Detector()
    time = np.arange(32000, dtype=np.float32) / 16000.0
    audio = 0.15 * np.sin(2.0 * np.pi * 220.0 * time)
    result = detector.analyze_array(audio, 16000)

    assert result["duration_s"] == 2.0
    assert result["speech_ratio"] == 1.0
    assert 0.0 <= result["mean_prob"] <= 1.0
    assert result["windows"][0]["prob"] == result["mean_prob"]
