from collections import Counter

from scripts.train_for_norm_stream_candidate import (
    ensure_disjoint_filenames,
    reserve_grouped_training_holdout,
)


def _groups(count_per_class: int) -> list[list[dict[str, str]]]:
    groups = []
    for label in (0, 1):
        for index in range(count_per_class):
            groups.append(
                [
                    {
                        "path": f"fixture/{label}/recording-{label}-{index}.wav",
                        "label": str(label),
                        "split": "training",
                    }
                ]
            )
    return groups


def test_reserved_training_holdout_is_class_balanced_and_filename_disjoint() -> None:
    groups = _groups(6)

    remaining, holdout = reserve_grouped_training_holdout(groups, 2, seed=17)

    assert Counter(row["label"] for row in holdout) == {"0": 2, "1": 2}
    assert Counter(row["label"] for group in remaining for row in group) == {
        "0": 4,
        "1": 4,
    }
    remaining_rows = [row for group in remaining for row in group]
    ensure_disjoint_filenames(
        {"training": remaining_rows, "validation": [], "testing": holdout}
    )


def test_zero_reserved_holdout_leaves_original_groups_untouched() -> None:
    groups = _groups(2)

    remaining, holdout = reserve_grouped_training_holdout(groups, 0, seed=5)

    assert remaining == groups
    assert holdout == []
