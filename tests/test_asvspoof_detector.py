import numpy as np
import pytest

from app.core.asvspoof_detector import ASVspoofDetector


def test_asvspoof_detector_is_deterministic_and_reports_contract() -> None:
    detector = ASVspoofDetector()
    time = np.arange(24000, dtype=np.float32) / 16000.0
    audio = (0.12 * np.sin(2.0 * np.pi * 220.0 * time)).astype(np.float32)
    first = detector.analyze_array(audio, 16000)
    second = detector.analyze_array(audio, 16000)

    assert first["model_version"].startswith("asvspoof_la_")
    assert first["mean_prob"] == second["mean_prob"]
    assert first["duration_s"] == 1.5
    assert first["windows"][0]["t_end"] == 1.5


def test_asvspoof_detector_does_not_score_silence() -> None:
    result = ASVspoofDetector().analyze_array(np.zeros(16000, dtype=np.float32), 16000)

    assert result["verdict"] == "Uncertain"
    assert result["mean_prob"] is None
    assert result["speech_ratio"] == 0.0


def test_asvspoof_detector_rejects_wrong_sample_rate() -> None:
    with pytest.raises(ValueError, match="expected 16000"):
        ASVspoofDetector().analyze_array(np.ones(16000, dtype=np.float32), 8000)
