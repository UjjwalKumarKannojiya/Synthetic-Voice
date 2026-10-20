"""Train the small log-mel CNN on a cached spectrogram index."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.eval.metrics import classification_metrics, threshold_at_eer
from src.svf.models.cnn import SmallLogMelCNN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-index", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_split(index_path: Path, split: str) -> tuple[torch.Tensor, torch.Tensor]:
    images: list[np.ndarray] = []
    labels: list[int] = []
    with index_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["split"] != split:
                continue
            images.append(np.load(row["feature_path"], allow_pickle=False).astype(np.float32, copy=False))
            labels.append(int(row["label"]))
    if not images:
        raise ValueError(f"No cached features for split {split}")
    return torch.from_numpy(np.stack(images)[:, None, :, :]), torch.tensor(labels, dtype=torch.float32)


def scores(model: SmallLogMelCNN, features: torch.Tensor) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(features)).cpu().numpy()


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    train_x, train_y = load_split(args.feature_index, "training")
    validation_x, validation_y = load_split(args.feature_index, "validation")
    test_x, test_y = load_split(args.feature_index, "testing")
    train_loader = DataLoader(
        TensorDataset(train_x, train_y), batch_size=args.batch_size, shuffle=True, generator=torch.Generator().manual_seed(args.seed)
    )
    model = SmallLogMelCNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_function = nn.BCEWithLogitsLoss()
    best_loss = float("inf")
    stale_epochs = 0
    best_state = None
    history: list[dict[str, float]] = []
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for features, labels in train_loader:
            optimizer.zero_grad()
            loss = loss_function(model(features), labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * labels.numel()
        with torch.no_grad():
            validation_loss = float(loss_function(model(validation_x), validation_y).item())
        train_loss = total_loss / len(train_y)
        history.append({"epoch": epoch + 1, "train_loss": train_loss, "validation_loss": validation_loss})
        print(f"epoch={epoch + 1} train_loss={train_loss:.6f} validation_loss={validation_loss:.6f}")
        if validation_loss < best_loss:
            best_loss = validation_loss
            stale_epochs = 0
            best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
        else:
            stale_epochs += 1
            if stale_epochs >= args.patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    validation_scores = scores(model, validation_x)
    test_scores = scores(model, test_x)
    threshold = threshold_at_eer(validation_y.numpy(), validation_scores)
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "threshold": threshold, "seed": args.seed}, args.model_output)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "log_mel_small_cnn",
        "feature_index": str(args.feature_index.resolve()),
        "model_path": str(args.model_output.resolve()),
        "seed": args.seed,
        "device": "cpu",
        "history": history,
        "threshold_source": "validation_eer",
        "validation": classification_metrics(validation_y.numpy(), validation_scores, threshold),
        "test": classification_metrics(test_y.numpy(), test_scores, threshold),
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved CNN results: {args.results}")


if __name__ == "__main__":
    main()