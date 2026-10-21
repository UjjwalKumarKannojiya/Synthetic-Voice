import numpy as np

from scripts.evaluate_asvspoof_external import confusion_metrics


def test_confusion_metrics_preserves_bona_fide_and_spoof_label_order():
    labels = np.asarray([0, 0, 1, 1], dtype=np.int64)
    scores = np.asarray([0.1, 0.9, 0.4, 0.8], dtype=np.float64)

    result = confusion_metrics(labels, scores, threshold=0.5)

    assert result["confusion_matrix_labels_0_1"] == [[1, 1], [1, 1]]
    assert result["accuracy"] == 0.5
    assert result["fpr"] == 0.5
    assert result["fnr"] == 0.5
    assert result["roc_auc"] == 0.5


def test_confusion_metrics_reports_auc_unavailable_for_single_class():
    labels = np.asarray([0, 0], dtype=np.int64)
    scores = np.asarray([0.1, 0.8], dtype=np.float64)

    result = confusion_metrics(labels, scores, threshold=0.5)

    assert result["confusion_matrix_labels_0_1"] == [[1, 1], [0, 0]]
    assert result["roc_auc"] is None
