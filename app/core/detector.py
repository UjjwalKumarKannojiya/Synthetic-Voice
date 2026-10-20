"""Reusable MFCC/SVM detector for file and future streaming inference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from src.svf.audio_io import AudioConfig, load_audio
from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc

from .vad import speech_present
from .verdict import verdict_for_score


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_META_PATH = ROOT / "models" / "model_meta.json"


@dataclass(frozen=True)
class DetectorConfig:
    """Runtime choices that are not part of the trained model artifact."""

    hop_seconds: float = 1.0
    uncertain_band: float = 0.05
    vad_threshold: float = 0.01
    threshold: float | None = None


class Detector:
    """Load model metadata once and score fixed-size audio windows.

    The returned score is scikit-learn's SVM ``predict_proba`` estimate for
    class 1 (fake). It is not a claim of calibrated real-world probability.
    """

    def __init__(self, meta_path: str | Path = DEFAULT_META_PATH, config: DetectorConfig | None = None):
        self.meta_path = Path(meta_path)
        self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.config = config or DetectorConfig()
        self.sample_rate = int(self.meta["sample_rate"])
        self.window_seconds = float(self.meta["window_seconds"])
        self.threshold = float(self.meta["threshold"] if self.config.threshold is None else self.config.threshold)
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if self.window_seconds <= 0.0 or self.config.hop_seconds <= 0.0:
            raise ValueError("window and hop durations must be positive")
        model_path = Path(self.meta["model_path"])
        if not model_path.is_absolute():
            model_path = self.meta_path.parent / model_path
        self.model = joblib.load(model_path)
        self.mfcc_config = MFCCConfig(sample_rate=self.sample_rate, **self.meta["mfcc"])
        self.window_samples = round(self.window_seconds * self.sample_rate)
        self.hop_samples = round(self.config.hop_seconds * self.sample_rate)
        if self.hop_samples < 1:
            raise ValueError("hop_seconds must span at least one model sample")

    def predict_window(self, audio: np.ndarray, sample_rate: int) -> float:
        """Return the model's estimated fake score for one model-sized window."""

        if sample_rate != self.sample_rate:
            raise ValueError(f"expected {self.sample_rate} Hz audio, got {sample_rate} Hz")
        if audio.ndim != 1 or audio.size != self.window_samples:
            raise ValueError("audio must be one-dimensional and exactly one model window")
        features = summarize_mfcc(extract_mfcc(audio, self.mfcc_config)).reshape(1, -1)
        score = float(self.model.predict_proba(features)[0, 1])
        if not 0.0 <= score <= 1.0:
            raise ValueError("model returned a score outside [0, 1]")
        return score

    def analyze_array(self, audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
        """Score all model-sized windows and aggregate speech windows."""

        if audio.ndim != 1 or not np.isfinite(audio).all():
            raise ValueError("audio must be finite one-dimensional data")
        if sample_rate != self.sample_rate:
            raise ValueError(f"expected {self.sample_rate} Hz audio, got {sample_rate} Hz")
        if audio.size == 0:
            raise ValueError("audio is empty")
        source_duration = audio.size / sample_rate
        padded = np.pad(audio, (0, max(0, self.window_samples - audio.size)))
        starts = list(range(0, max(1, padded.size - self.window_samples + 1), self.hop_samples))
        last_start = max(0, padded.size - self.window_samples)
        if starts[-1] != last_start:
            starts.append(last_start)
        windows: list[dict[str, Any]] = []
        speech_scores: list[float] = []
        for start in starts:
            window = padded[start : start + self.window_samples]
            is_speech = speech_present(window, self.config.vad_threshold)
            result: dict[str, Any] = {
                "t_start": start / sample_rate,
                "t_end": min(source_duration, (start + self.window_samples) / sample_rate),
                "speech": is_speech,
                "prob": None,
            }
            if is_speech:
                score = self.predict_window(window, sample_rate)
                result["prob"] = score
                speech_scores.append(score)
            windows.append(result)
        mean_score = float(np.mean(speech_scores)) if speech_scores else None
        max_score = float(np.max(speech_scores)) if speech_scores else None
        return {
            "verdict": verdict_for_score(mean_score, self.threshold, self.config.uncertain_band),
            "mean_prob": mean_score,
            "max_prob": max_score,
            "threshold": self.threshold,
            "uncertain_band": self.config.uncertain_band,
            "duration_s": source_duration,
            "sample_rate": sample_rate,
            "speech_ratio": len(speech_scores) / len(windows),
            "windows": windows,
        }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    args = parser.parse_args()
    audio, sample_rate = load_audio(args.audio, AudioConfig())
    print(json.dumps(Detector().analyze_array(audio, sample_rate), indent=2))


if __name__ == "__main__":
    main()
