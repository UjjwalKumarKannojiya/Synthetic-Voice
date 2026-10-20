"""Inference contract for the explicitly selected ASVspoof LA model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc

from .vad import speech_present
from .verdict import verdict_for_score


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_META_PATH = ROOT / "models" / "asvspoof_la_svm_balanced2500" / "model_meta.json"


class ASVspoofDetector:
    """Score complete variable-duration ASVspoof clips with one loaded artifact."""

    def __init__(
        self,
        meta_path: str | Path = DEFAULT_META_PATH,
        uncertain_band: float = 0.05,
        threshold: float | None = None,
    ):
        self.meta_path = Path(meta_path)
        self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        if self.meta.get("training_dataset") != "ASVspoof2019_LA":
            raise ValueError("metadata is not an ASVspoof2019_LA artifact")
        self.sample_rate = int(self.meta["sample_rate"])
        self.threshold = float(self.meta["threshold"] if threshold is None else threshold)
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.uncertain_band = float(uncertain_band)
        if not 0.0 <= self.uncertain_band <= 1.0:
            raise ValueError("uncertain_band must be between 0 and 1")
        model_path = Path(self.meta["model_path"])
        if not model_path.is_absolute():
            model_path = self.meta_path.parent / model_path
        self.model = joblib.load(model_path)
        mfcc_values = {
            key: value
            for key, value in self.meta["mfcc"].items()
            if key in {"n_mfcc", "include_delta", "include_delta_delta", "n_fft", "hop_length", "n_mels"}
        }
        self.mfcc_config = MFCCConfig(sample_rate=self.sample_rate, **mfcc_values)

    def predict_clip(self, audio: np.ndarray, sample_rate: int) -> float:
        if sample_rate != self.sample_rate:
            raise ValueError(f"expected {self.sample_rate} Hz audio, got {sample_rate} Hz")
        if audio.ndim != 1 or audio.size == 0 or not np.isfinite(audio).all():
            raise ValueError("audio must be finite, non-empty, one-dimensional data")
        frames = extract_mfcc(audio, self.mfcc_config)
        vector = summarize_mfcc(frames).reshape(1, -1)
        score = float(self.model.predict_proba(vector)[0, 1])
        if not 0.0 <= score <= 1.0:
            raise ValueError("model returned a score outside [0, 1]")
        return score

    def analyze_array(self, audio: np.ndarray, sample_rate: int, vad_threshold: float = 0.01) -> dict[str, Any]:
        if audio.ndim != 1 or not np.isfinite(audio).all() or audio.size == 0:
            raise ValueError("audio must be finite, non-empty, one-dimensional data")
        duration_s = float(audio.size / sample_rate)
        speech = speech_present(audio, vad_threshold)
        score = self.predict_clip(audio, sample_rate) if speech else None
        return {
            "verdict": verdict_for_score(score, self.threshold, self.uncertain_band),
            "mean_prob": score,
            "max_prob": score,
            "threshold": self.threshold,
            "uncertain_band": self.uncertain_band,
            "duration_s": duration_s,
            "sample_rate": sample_rate,
            "speech_ratio": 1.0 if speech else 0.0,
            "windows": [{
                "t_start": 0.0,
                "t_end": duration_s,
                "speech": speech,
                "prob": score,
            }],
            "model_version": self.meta["model_version"],
            "score_definition": self.meta["score_definition"],
        }
