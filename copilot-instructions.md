# Copilot Instructions — Synthetic Voice Forensics

> Place this file at `.github/copilot-instructions.md` in the repository root.
> VS Code loads it automatically for Copilot Chat in this workspace.

## Project in one paragraph
MCA (DS & AI) dissertation, Babu Banarasi Das University. Binary classifier that labels speech as **real (0)** or **synthetic/fake (1)**, plus a robustness study (noise, compression, telephone-style audio, short clips). The point of the research is **generalization and reliability under changing conditions**, not one high accuracy number. Full brief: `docs/MASTER_PROMPT.md`. Source documents are in `docs/`.

## Environment (do not assume anything better)
- Windows 11, 8 GB RAM or less, Intel integrated graphics, **CPU only**. No CUDA.
- Use `pathlib`, never hard-coded `/` or `\` separators. Commands must work in Windows Command Prompt/PowerShell, not bash-only.
- Never load a whole dataset into memory. Stream files, cache features to disk as `.npy`/`.npz`, use `float32`.

## Non-negotiable rules
1. **Never invent results, accuracy numbers, dataset sizes, file counts, or folder structure.** Inspect the real files first, then write code. If something is unknown, say "unknown" and write code to discover it.
2. **Numbers in the presentation slides marked "illustrative" are not results.** Only numbers produced by our own scripts and saved under `results/` may be reported.
3. **Label convention is fixed:** `0 = real/bona fide`, `1 = fake/spoof`. Score = predicted probability of fake. Higher score = more fake.
4. **No data leakage.** Use the dataset's official train/validation/test split when it exists; never re-mix them. Fit scalers/PCA/etc. on train only. Choose decision thresholds on validation, never on test. Check for speaker overlap when speaker info is available, and document it when it is not.
5. **Identical preprocessing for train, validation, test, and the app.** One shared function, imported everywhere.
6. **Fixed random seed** (from `configs/config.yaml`) everywhere; log it.
7. **Report more than accuracy:** precision, recall, F1, FPR, FNR, EER, ROC-AUC, confusion matrix, latency.
8. **Do not silently substitute.** If a tool is missing (for example `ffmpeg`), raise a clear error or mark that experiment "not run". Never fake a codec with something else and label it as the real thing.
9. **Small steps.** Work on one stage at a time. Do not generate the entire project in one response. Do not install packages without telling me the exact command first.
10. **Always finish a stage with:** what changed, how to run it (exact command), what output to expect, and known risks.

## Code style
- Python 3.10+ compatible, type hints, short docstrings stating assumptions.
- Config in `configs/config.yaml`; no magic numbers in code.
- Every script runnable as `python -m src.<module>` or `python scripts/<name>.py` and prints a clear summary.
- Write tests in `tests/` for metrics, splitting, and preprocessing (small synthetic arrays, no big data).
- Save every experiment as a JSON in `results/` with the reproducibility fields listed in `docs/MASTER_PROMPT.md`.

## Things to warn me about
If I ask for something that risks leakage, shortcut learning (for example the model learning sample rate or clip length instead of synthetic artifacts), or an unsupported claim, say so before writing the code.
