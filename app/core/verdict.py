"""Threshold-based verdict labels shared by file and stream inference."""

from __future__ import annotations


def verdict_for_score(score: float | None, threshold: float, uncertain_band: float) -> str:
    """Map a fake score to a semantic label without using color as meaning."""

    if score is None:
        return "Uncertain"
    if not 0.0 <= score <= 1.0:
        raise ValueError("score must be between 0 and 1")
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if uncertain_band < 0.0 or uncertain_band > 1.0:
        raise ValueError("uncertain_band must be between 0 and 1")
    lower = max(0.0, threshold - uncertain_band)
    upper = min(1.0, threshold + uncertain_band)
    if score < lower:
        return "Likely Real"
    if score > upper:
        return "Likely Synthetic"
    return "Uncertain"
