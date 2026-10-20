import numpy as np

from src.svf.eval.metrics import classification_metrics, equal_error_rate


def test_perfect_scores_have_zero_eer() -> None:
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.8, 0.9])

    eer, _ = equal_error_rate(labels, scores)

    assert eer == 0.0


def test_metrics_use_fake_score_threshold() -> None:
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.7, 0.8, 0.2])

    result = classification_metrics(labels, scores, threshold=0.5)

    assert result["confusion_matrix"] == [[1, 1], [1, 1]]
    assert result["accuracy"] == 0.5
    assert 0.0 <= result["eer"] <= 1.0
    assert 0.0 <= result["roc_auc"] <= 1.0


def test_random_scores_produce_finite_metrics() -> None:
    labels = np.array([0, 1] * 10)
    scores = np.linspace(0.05, 0.95, num=20)

    result = classification_metrics(labels, scores, threshold=0.5)

    assert np.isfinite(list(result.values())[:-2]).all()