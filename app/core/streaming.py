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
    finalized: bool = False

    def __post_init__(self) -> None:
        if self.sample_rate != self.detector.sample_rate:
            raise ValueError(f"expected {self.detector.sample_rate} Hz stream")
        if not 0.0 < self.smoothing_alpha <= 1.0:
            raise ValueError("smoothing_alpha must be in (0, 1]")

    def add_frame(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """Consume PCM samples and return zero or more window messages."""

        if self.finalized:
            raise ValueError("cannot add audio after the stream session is finalized")
        if frame.ndim != 1 or not np.isfinite(frame).all():
            raise ValueError("stream frame must be finite mono audio")
        self.total_samples_received += frame.size
        self.buffer = np.concatenate((self.buffer, frame.astype(np.float32, copy=False)))
        messages: list[dict[str, Any]] = []
        while self.buffer.size >= self.detector.window_samples:
            window = self.buffer[: self.detector.window_samples]
            start = self.samples_seen / self.sample_rate
            self.buffer = self.buffer[self.detector.hop_samples :]
            self.samples_seen += self.detector.hop_samples
            messages.extend(self._score_window(window, start))
        return messages

    def flush(self) -> list[dict[str, Any]]:
        """Score a sufficiently long final partial window after zero-padding it.

        A new stream needs at least one hop of audio. After a full window has
        already been scored, a trailing window is emitted only when at least
        half a hop of new audio remains beyond the overlap. This prevents
        duplicating an exact-window session while retaining useful final speech.
        """

        if self.finalized:
            return []
        self.finalized = True
        remaining = self.buffer.size
        if remaining == 0:
            return []

        if self.windows:
            overlap_samples = max(
                0, self.detector.window_samples - self.detector.hop_samples
            )
            new_samples = max(0, remaining - overlap_samples)
            minimum_new_samples = max(1, self.detector.hop_samples // 2)
        else:
            new_samples = remaining
            minimum_new_samples = max(1, self.detector.hop_samples)

        if new_samples < minimum_new_samples:
            self.buffer = np.empty(0, dtype=np.float32)
            return []

        window = self.buffer[: self.detector.window_samples]
        if window.size < self.detector.window_samples:
            window = np.pad(window, (0, self.detector.window_samples - window.size))
        self.buffer = np.empty(0, dtype=np.float32)
        start = self.samples_seen / self.sample_rate
        return self._score_window(window, start)

    def _score_window(self, window: np.ndarray, start: float) -> list[dict[str, Any]]:
        started = perf_counter()
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
        messages: list[dict[str, Any]] = [window_result]
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
                    "t_end": min(
                        duration, window["t"] + self.detector.window_seconds
                    ),
                    "prob": window["prob"],
                    "speech": window["speech"],
                }
                for window in self.windows
            ],
        }
