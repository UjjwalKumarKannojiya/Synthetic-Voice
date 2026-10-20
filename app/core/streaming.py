"""Windowed streaming inference shared by live and call modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import numpy as np

from .detector import Detector
from .vad import speech_present
from .verdict import verdict_for_score


@dataclass
class StreamSession:
    detector: Detector
    sample_rate: int
    mode: str
    source: str
    smoothing_alpha: float = 0.4
    alert_consecutive_windows: int = 3
    buffer: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float32))
    samples_seen: int = 0
    total_samples_received: int = 0
    scores: list[float] = field(default_factory=list)
    windows: list[dict[str, Any]] = field(default_factory=list)
    smoothed: float | None = None
    consecutive_flagged: int = 0
    alert_sent: bool = False

    def __post_init__(self) -> None:
        if self.sample_rate != self.detector.sample_rate:
            raise ValueError(f"expected {self.detector.sample_rate} Hz stream")
        if not 0.0 < self.smoothing_alpha <= 1.0:
            raise ValueError("smoothing_alpha must be in (0, 1]")

    def add_frame(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """Consume PCM samples and return zero or more window messages."""

        if frame.ndim != 1 or not np.isfinite(frame).all():
            raise ValueError("stream frame must be finite mono audio")
        self.total_samples_received += frame.size
        self.buffer = np.concatenate((self.buffer, frame.astype(np.float32, copy=False)))
        messages: list[dict[str, Any]] = []
        while self.buffer.size >= self.detector.window_samples:
            started = perf_counter()
            window = self.buffer[: self.detector.window_samples]
            start = self.samples_seen / self.sample_rate
            self.buffer = self.buffer[self.detector.hop_samples :]
            self.samples_seen += self.detector.hop_samples
            speech = speech_present(window, self.detector.config.vad_threshold)
            score = self.detector.predict_window(window, self.sample_rate) if speech else None
            if score is not None:
                self.scores.append(score)
                self.smoothed = score if self.smoothed is None else (
                    self.smoothing_alpha * score + (1.0 - self.smoothing_alpha) * self.smoothed
                )
                if self.smoothed >= self.detector.threshold:
                    self.consecutive_flagged += 1
                else:
                    self.consecutive_flagged = 0
            verdict = verdict_for_score(self.smoothed, self.detector.threshold, self.detector.config.uncertain_band)
            window_result = {
                "type": "window",
                "t": start,
                "prob": score,
                "smoothed": self.smoothed,
                "verdict": verdict,
                "speech": speech,
                "level": float(np.sqrt(np.mean(np.square(window, dtype=np.float64)))),
                "latency_ms": (perf_counter() - started) * 1000.0,
                "threshold": self.detector.threshold,
                "uncertain_band": self.detector.config.uncertain_band,
            }
            self.windows.append(window_result)
            messages.append(window_result)
            if self.consecutive_flagged >= self.alert_consecutive_windows and not self.alert_sent:
                self.alert_sent = True
                messages.append(
                    {
                        "type": "alert",
                        "t": start,
                        "message": "Sustained synthetic-like speech detected — verify the caller through another channel",
                    }
                )
        return messages

    def summary(self) -> dict[str, Any]:
        mean_prob = float(np.mean(self.scores)) if self.scores else None
        max_prob = float(np.max(self.scores)) if self.scores else None
        duration = self.total_samples_received / self.sample_rate
        return {
            "type": "summary",
            "mode": self.mode,
            "source": self.source,
            "duration_s": duration,
            "sample_rate": self.sample_rate,
            "mean_prob": mean_prob,
            "max_prob": max_prob,
            "speech_ratio": len(self.scores) / len(self.windows) if self.windows else 0.0,
            "verdict": verdict_for_score(mean_prob, self.detector.threshold, self.detector.config.uncertain_band),
            "threshold": self.detector.threshold,
            "uncertain_band": self.detector.config.uncertain_band,
            "latency_ms": sum(float(window.get("latency_ms", 0.0)) for window in self.windows),
            "windows": [
                {
                    "t_start": window["t"],
                    "t_end": window["t"] + self.detector.window_seconds,
                    "prob": window["prob"],
                    "speech": window["speech"],
                }
                for window in self.windows
            ],
        }
