from pathlib import Path

from scripts.asvspoof_eval_breakdown import group_metrics, load_scores


def test_breakdown_separates_known_and_unknown_attacks(tmp_path: Path) -> None:
    score_file = tmp_path / "scores.csv"
    score_file.write_text(
        "path,label,attack_id,score\n"
        "real,0,-,0.1\n"
        "known,1,A01,0.9\n"
        "unknown,1,A07,0.8\n",
        encoding="utf-8",
    )
    rows = load_scores(score_file)
    assert group_metrics(rows, 0.5)["count"] == 3
    assert group_metrics([rows[0], rows[1]], 0.5)["spoof"] == 1
    assert group_metrics([rows[0], rows[2]], 0.5)["roc_auc"] == 1.0
