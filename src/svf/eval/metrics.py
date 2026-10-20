"""Metrics for binary real-versus-fake detection."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def equal_error_rate(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Return EER and its interpolated fake-score threshold."""

    false_positive_rate, true_positive_rate, thresholds = roc_curve(labels, scores)
    false_negative_rate = 1.0 - true_positive_rate
    differences = false_positive_rate - false_negative_rate
    crossing = np.where(np.signbit(differences[:-1]) != np.signbit(differences[1:]))[0]
    if crossing.size == 0:
        index = int(np.argmin(np.abs(differences)))
        return float((false_positive_rate[index] + false_negative_rate[index]) / 2.0), float(thresholds[index])

    index = int(crossing[0])
    left_difference = float(differences[index])
    right_difference = float(differences[index + 1])
    denominator = left_difference - right_difference
    weight = 0.0 if denominator == 0.0 else left_difference / denominator
    eer = float(false_positive_rate[index] + weight * (false_positive_rate[index + 1] - false_positive_rate[index]))
    threshold = float(thresholds[index] + weight * (thresholds[index + 1] - thresholds[index]))
    return eer, threshold


def threshold_at_eer(labels: np.ndarray, scores: np.ndarray) -> float:
    """Return the validation threshold associated with the EER operating point."""

    return equal_error_rate(labels, scores)[1]


def classification_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    """Compute thresholded metrics plus threshold-independent ROC-AUC and EER."""

    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    predictions = (scores >= threshold).astype(np.int64)
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    true_negative, false_positive, false_negative, true_positive = matrix.ravel()
    eer, eer_threshold = equal_error_rate(labels, scores)
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "fpr": float(false_positive / (false_positive + true_negative)) if (false_positive + true_negative) else 0.0,
        "fnr": float(false_negative / (false_negative + true_positive)) if (false_negative + true_positive) else 0.0,
        "roc_auc": float(roc_auc_score(labels, scores)),
        "eer": float(eer),
        "eer_threshold": float(eer_threshold),
        "confusion_matrix": matrix.tolist(),
        "count": int(labels.size),
    }