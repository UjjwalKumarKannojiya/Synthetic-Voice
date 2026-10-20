from types import SimpleNamespace

import numpy as np

from app.core.streaming import StreamSession


class StubDetector:
    sample_rate = 16000
    window_samples = 8
    hop_samples = 4
    window_seconds = window_samples / sample_rate
    threshold = 0.5
    config = SimpleNamespace(vad_threshold=0.01, uncertain_band=0.05)

    def predict_window(self, window: np.ndarray, sample_rate: int) -> float:
        return 0.9


def test_stream_summary_uses_received_duration_and_reports_alert() -> None:
    session = StreamSession(StubDetector(), 16000, "test", "fixture", alert_consecutive_windows=3)
    messages = session.add_frame(np.ones(24, dtype=np.float32))
    windows = [message for message in messages if message["type"] == "window"]

    assert sum(message["type"] == "window" for message in messages) == 5
    assert sum(message["type"] == "alert" for message in messages) == 1
    assert all(message["latency_ms"] >= 0.0 for message in messages if message["type"] == "window")
    assert all(message["threshold"] == 0.5 for message in windows)
    assert all(message["uncertain_band"] == 0.05 for message in windows)
    assert session.summary()["duration_s"] == 24 / 16000
