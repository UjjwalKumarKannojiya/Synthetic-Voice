# AGENTS.md — Synthetic Voice Forensics

Tool-neutral instructions for any coding agent working in this repository. Place at the repo root.

## Project
MCA (DS & AI) dissertation, Babu Banarasi Das University. Detects **real (0)** vs **synthetic/fake (1)** speech. Score = P(fake). The research focus is **robustness and generalization** (unseen attacks, noise, compression, telephone-style audio, short clips), not a single accuracy number. Deliverables: trained model + evaluation, and a **working** FastAPI + HTML/JS app (upload check, live microphone check, live call monitor, dashboard, history, model & evaluation, settings).

## Where the truth lives
- Plan and rules: `docs/COPILOT_RECOVERY_PROMPT.md` (highest priority), `docs/COPILOT_ASVSPOOF_DATA_PROMPT.md`, `docs/APP_BLUEPRINT.md`, then `docs/MASTER_PROMPT.md`.
- Current state: `docs/PROJECT_STATE.md`, `docs/STATE_RECONSTRUCTION.md`.
- Dataset facts: `docs/DATASET_NOTES.md`. Evidence of results: `results/`. Model metadata: `models/model_meta.json`.
- Wherever older docs say "Copilot", it means "you, the current agent".

## Environment
Windows 11, ≤8 GB RAM, Intel integrated graphics, **CPU only**, Python venv. Use `pathlib`, Windows-safe commands. Never load a whole dataset into memory. Target browser: Chrome/Edge on `http://localhost`.

## Hard rules
1. **Evidence over assertion.** Do not say "works", "fixed", "done" or "verified" without the exact command and its real output. Otherwise write NOT VERIFIED.
2. **No fabricated data or numbers** in code, HTML, JS or API responses: no hard-coded demo values, `Math.random`, fake progress timers, constant-returning endpoints. Fixtures only in `tests/`.
3. **No dead UI controls.** Each control works end-to-end or is removed.
4. **No leakage.** Splits: train = official train, val = official dev (model/threshold selection), test = official eval minus demo speakers, `demo_holdout` = locked, never used for training, validation, tuning or thresholds. Scalers fit on train only.
5. **One shared preprocessing/feature implementation** for training, evaluation, upload, streaming.
6. **Protect existing work.** Do not delete, rename, overwrite, retrain or regenerate data, splits, models or results without listing them, giving the reason, and getting the student's approval. Work on a git branch, small commits, no big rewrites, no test edits to force a pass.
7. **Do not hide bad results.** Report real metrics; "Uncertain" is acceptable output; overclaiming is not.
8. **Honesty about call monitoring:** it analyzes an audio stream on this device (microphone, system/tab audio, demo replay). It is **not** integrated with any phone network.
9. Work **one phase at a time**, stop at its gate with proof, update `docs/PROJECT_STATE.md`.
10. Tell the student the exact command before installing any package. Never commit `data/`, `models/`, `.venv/`.

## Standard commands (update if they change)
- Tests: `python -m pytest -q`
- Start app: `python -m uvicorn app.main:app --reload` then open `http://localhost:8000`
- No-mock scan: `python scripts/scan_no_mock.py`
- Streaming evaluation: `python scripts/stream_eval.py`

## Response format for each phase
1. Plan (≤8 lines) 2. Files created/changed (reused vs replaced) 3. Commands run with real output 4. Proof against the phase gate 5. Risks / NOT VERIFIED items 6. PROJECT_STATE.md updated 7. Next phase (wait for go-ahead)
