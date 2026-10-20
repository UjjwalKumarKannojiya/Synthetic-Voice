# Repository guidance

## Project contract

This is a CPU-oriented speech-forensics research project. Labels are `0 = real/bona fide` and `1 = synthetic/spoof`; scores are estimates, not proof. The research goal is robustness and generalization. Current performance and deployment limitations are in [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md).

## Evidence and implementation rules

1. Report exact commands and outputs. Mark anything without direct evidence **NOT VERIFIED**.
2. Do not add hard-coded/demo scores, fake progress, sample records, `Math.random`, or constant-returning APIs. Test fixtures belong only in `tests/`.
3. Every visible control must work through to its real behavior or be removed.
4. Keep train/validation/test/demo splits leakage-safe. Fit preprocessing/scalers on train only; use validation for selection; never train/tune on locked demo holdout.
5. Reuse the same audio preprocessing/features for training, evaluation, uploads, and streaming.
6. Preserve datasets, manifests, models, reports, and results. Do not delete, regenerate, overwrite, or retrain them without the student's approval.
7. Report weak results and uncertainty plainly. Do not overclaim detector accuracy or certification.
8. Call Monitor analyzes audio provided by this device/browser. It is not connected to a phone network.
9. Work one phase at a time and update [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) with proof and remaining risks.
10. Never commit `.env`, credentials, databases, audio, datasets, `data/`, `models/`, `results/`, or `.venv/`. The repository intentionally excludes model and evaluation artifacts.
11. Before installing a package, tell the student the exact command.

## Environment and commands

Windows 11, Python virtual environment, CPU-only, target browser Chrome/Edge on localhost. Use `pathlib` and do not load full datasets into memory.

```powershell
python -m pytest -q
python scripts/scan_no_mock.py
node --check app/static/app-runtime.js
python scripts/run_app.py
```

See [README.md](README.md) for the short setup and [docs/WIRING_MATRIX.md](docs/WIRING_MATRIX.md) for page/API behavior. Dataset details are in [docs/DATASET_NOTES.md](docs/DATASET_NOTES.md).
