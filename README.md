# Synthetic-Voice — Synthetic Voice Forensics

This repository contains a CPU-friendly research system for real-versus-synthetic speech analysis.
The fixed label convention is `0 = real/bona fide` and `1 = fake/spoof`. Scores are model estimates,
not calibrated real-world probabilities or proof of authenticity.

## Current stage

The repository contains leakage-aware manifests, classical baselines, bounded CQCC/CNN experiments,
robustness reports, latency measurement, and a FastAPI/HTML application. The FoR streaming model has
weak held-out test performance; ASVspoof metrics are from balanced subsets and must be described as
such. See `docs/PROJECT_STATE.md` before interpreting results.

## Run the application

Start the local site from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\run_app.py
```

Open `http://127.0.0.1:8000/`. The seven-page HTML/JavaScript frontend uses FastAPI endpoints for
upload analysis, live device audio, history, model and evaluation, settings, and the locked demo set.
Its API and UI do not use fabricated scores or seeded demo records. See
[docs/WIRING_MATRIX.md](docs/WIRING_MATRIX.md) for the page-to-endpoint map and
[docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) for evidence and limitations.

The user icon opens account controls for signup, sign-in, sign-out, theme, password changes, data
export, and account deletion. Private analysis and history routes require a signed-in account and
are scoped to that account. Local users, sessions, settings, and analyses use SQLite at
`data/voiceguard.sqlite3`; cookies are HttpOnly and Secure in Vercel deployments.

**Deployment status: not ready yet.** Vercel's function filesystem is not durable, and this source
checkout intentionally does not contain the ignored model weights, evaluation reports, manifests,
or audio. A deployment needs a persistent PostgreSQL `DATABASE_URL` and an approved way to provide
the required model/evaluation artifacts. The Python WebSocket path also needs a real Vercel preview
test before live monitoring can be promised. Do not deploy with local SQLite or claim model checks
are operational until those gates are complete. See [docs/AUTH_DEPLOY_PLAN.md](docs/AUTH_DEPLOY_PLAN.md).

SQLite history is stored at `data/voiceguard.sqlite3`; raw audio is not retained. Upload analysis
defaults to the legacy FoR profile and offers ASVspoof as an explicit complete-clip profile. Live
streaming uses the FoR window model. Stream analysis observes a device audio source and is not
connected to a phone network.

The active Stitch pages load Tailwind, fonts, and some logo assets from external URLs. Internet access
is currently required for the full intended appearance; offline rendering has not been verified.

## Audit command

After installing the listed dependencies, run one audit per extracted variant:

```powershell
python scripts/audit_data.py --data-path .\for-2sec\for-2seconds --output .\results\audit_for_2sec.json
python scripts/audit_data.py --data-path .\for-rerec\for-rerecorded --output .\results\audit_for_rerec.json
```

The audit streams file metadata and saves counts, labels, splits, sample rates, durations, channels,
formats, and read errors. It does not infer speaker or generator identity.

The current audit reports show that both variants are mono 16 kHz WAV data with official-looking
training, validation, and testing folders. They remain separate until provenance and overlap checks
are complete.

## Manifest command

Build one manifest per variant after the audit:

```powershell
py scripts/build_manifest.py --data-path .\for-2sec\for-2seconds --dataset-variant for-2sec --output .\data\manifests\for_2sec.csv
py scripts/build_manifest.py --data-path .\for-rerec\for-rerecorded --dataset-variant for-rerec --output .\data\manifests\for_rerec.csv
```

The manifest preserves the dataset split and maps `real` to label `0` and `fake` to label `1`.
It records audio metadata and SHA-256 hashes, rejects duplicate content within a variant, and leaves
speaker/generator fields empty until those identifiers are verified from authoritative metadata.

## MFCC cache command

For a small CPU smoke run, cache 20 files per class per split:

```powershell
\.venv\Scripts\python.exe scripts/extract_mfcc.py --manifest .\data\manifests\for_2sec.csv --output-dir .\data\features\mfcc_for_2sec_smoke --max-files-per-class 20
```

The cache stores one `float32` `.npy` vector per clip plus an index CSV. The subset limit is for
development only; full extraction will be run after the smoke output is inspected.

## Shortcut baseline command

Run the metadata-only baseline before trusting acoustic-model results:

```powershell
\.venv\Scripts\python.exe scripts/metadata_baseline.py --manifest .\data\manifests\for_2sec.csv --output .\results\metadata_baseline_for_2sec.json
```

This baseline uses only duration, sample rate, channels, file size, RMS, and silence ratio. A strong
score would indicate dataset shortcuts and must be reported prominently.

The first primary-dataset run was above chance, so this warning is active. Do not interpret later
acoustic-model scores without comparing their behavior against this baseline and the class-wise
metadata distributions.

## Classical baseline command

After full MFCC extraction, train the approved baselines:

```powershell
\.venv\Scripts\python.exe scripts/train_classical.py --feature-index .\data\features\mfcc_for_2sec\index.csv --output-dir .\models\classical_for_2sec --results .\results\classical_for_2sec.json
```

The threshold is selected from validation EER and applied unchanged to test scores.

## Environment

The project targets Python 3.10+ on Windows and CPU-only execution. Dependencies are listed in
`requirements.txt`; they are not installed by this scaffold.

## New `for-norm` audit

The added `for-norm` corpus is audited separately in
`results/audit_for_norm.json`. It contains variable-length audio, two
zero-frame files, and two exact-content overlaps with the original
`for-2sec` corpus. The reproducible exclusions are recorded in
`results/for_norm_exclusions.json`; the resulting clean manifest is
`data/manifests/for_norm_clean.csv`.

Do not use `for-norm` as independent held-out evidence until its provenance
and preprocessing relationship are established.

## Detector smoke test

Stage A1 adds verified model metadata and a reusable detector. To inspect one
2-second WAV with the same MFCC path used by training:

```powershell
\.venv\Scripts\python.exe -m app.core.detector .\for-2sec\for-2seconds\testing\real\<file>.wav
```

Scores are scikit-learn SVM fake-class estimates, not calibrated real-world
probabilities. See `docs/AUDIT.md` for the measured test and robustness
limitations before interpreting a result.

>>>>>>> codex/r4-stream-evaluation
