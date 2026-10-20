# COPILOT RECOVERY PROMPT — Make it a real, working system (not a demo)

**Where it goes:** save as `docs/COPILOT_RECOVERY_PROMPT.md`. Keep these in `docs/` too: `APP_BLUEPRINT.md`, `MASTER_PROMPT.md`, `COPILOT_APP_PROMPT.md`, the synopsis, and the handbook. This prompt **takes priority** over the older ones wherever they conflict.

**Use Copilot Agent mode** (it can edit files and run terminal commands). Start every new chat with:

> Read #file:docs/COPILOT_RECOVERY_PROMPT.md, #file:docs/APP_BLUEPRINT.md and #file:docs/PROJECT_STATE.md (if it exists). Do NOT change code yet. Reply with (1) your understanding in 10 lines, (2) the risks you see, (3) confirmation that you will follow every rule. Then wait for me to say "start Phase R0".

---

## 1. Situation (read carefully)

The project is a **Synthetic Voice Forensics** system: it decides whether speech is real or AI-generated. A first version was built, but **it is effectively a demo**:
- The UI is a static copy of the design. Charts, numbers, tables and buttons do not respond to real data.
- Many components exist visually but do nothing.
- The model's correctness is unverified; the model may not be wired to the app at all.

**Goal:** a **fully working** system where every number on screen comes from the real model, database, or evaluation files, every control does what its label says, and the whole thing can be demonstrated live to an audience. "Working" is defined only by **evidence** (Section 9), never by your statement that it works.

Environment: Windows 11, ≤8 GB RAM, Intel integrated graphics, CPU only. Python via the project's venv. Target browser: Chrome/Edge on `http://localhost`.

## 2. Non-negotiable rules

1. **Evidence over assertion.** You may not write "works", "fixed", "done" or "verified" unless the same message contains the **exact command you ran and its real output**. If you could not run something, say "NOT VERIFIED" and why.
2. **No fabricated data anywhere.** Forbidden in application code, HTML, JS, and API responses: hard-coded demo numbers, `Math.random()`, `faker`, lorem ipsum, `setTimeout` used to fake progress/latency/results, constant-returning endpoints, mock servers, sample JSON served as if real. Test fixtures are allowed **only in `tests/`**.
3. **No dead controls.** Every button, tab, dropdown, slider, toggle, filter, pagination control, drawer, export link and form field must either work end-to-end or be **removed**. A control that looks real but does nothing is a bug.
4. **Do not hide failures.** If the model is weak, report the real metrics. Never tune, cherry-pick, or evaluate on data in a way that inflates results. Bad results are acceptable; fake or leaked results are not.
5. **No data leakage.** Never choose a model, hyperparameter, or threshold using test or demo data. Fit scalers on training data only.
6. **One shared preprocessing/feature implementation** for training, evaluation, upload, streaming and tests.
7. **Do not guess about the data.** Inspect the real dataset files first. If something is unknown, write code that discovers it and report what it found.
8. **Work one phase at a time.** Stop at the end of each phase and wait for my go-ahead. Do not start the next phase.
9. **Tell me the exact command before installing any package.** Windows-safe commands only; use `pathlib`.
10. **Do not rewrite blindly.** Reuse existing code that is correct; replace what is wrong. Say which is which.
11. **Keep context in the repo.** After every phase, update `docs/PROJECT_STATE.md` (see Section 10). A new chat must be able to continue from that file alone.
12. **If a library or browser behavior is uncertain** (e.g. system-audio capture), write a tiny verification test instead of assuming.

## 3. Data protocol (the dataset is provided by the student)

The student has provided a final dataset. **Do not assume which one or its structure.** Phase R0 must discover and report: folder layout, file formats, counts per class and per existing split, sample rates, durations, channels, speaker or generator information if present, duplicates, class balance.

Create **four disjoint sets**, stored as manifest CSVs in `data/manifests/` (columns: `path, label, split, speaker?, generator?, sr, duration_s, sha1`):

| Set | Purpose | Rules |
|---|---|---|
| `train` | fit models | the only data models learn from |
| `val` | choose model, hyperparameters, **decision threshold** | never used for fitting |
| `test` | final reported metrics | touched only for final evaluation |
| `demo_holdout` | live presentation | **never** used in training, validation, tuning, thresholding or the test table; locked and read-only |

- If the dataset has an official train/val/test split, **keep it** and carve `demo_holdout` out of the official *test* part. Otherwise create a seeded, stratified split, **speaker-disjoint when speaker info exists**, and document it.
- `demo_holdout` size: a balanced set, default **25 real + 25 fake** (design choice, configurable) or the largest balanced number available if smaller (minimum 10 per class). Choose files at random with a fixed seed. Do not hand-pick "nice" files.
- Implement `tests/test_no_leakage.py`: asserts zero overlap of file paths **and** content hashes across all four sets, and that `demo_holdout` files are never read by any training/validation code path. This test must pass before any model is trained.
- 8 GB RAM: stream files, cache features as float32 `.npy`, provide `max_files_per_class` for quick runs.

## 4. Model requirements

Follow the experiments in `docs/MASTER_PROMPT.md` (label `0 = real`, `1 = fake`, score = P(fake)), prioritized as:

1. **Shortcut check first:** a metadata-only baseline (duration, sample rate, channels, file size, RMS, silence ratio). If it beats chance clearly, report it prominently and mitigate (e.g. fixed-length clips, consistent resampling) before trusting any accuracy.
2. **Classical baselines:** MFCC (+delta) and CQCC features → SVM and Random Forest, same protocol.
3. **A small CNN on log-mel spectrograms** (CPU-friendly, early stopping on `val`, seeded). If CPU training is impractical, reduce subset/input size and **document it**.
4. **Select the final model on `val`** (primary criterion: EER; also report F1 and AUC). Choose the decision threshold on `val`.
5. Evaluate the chosen model **once** on `test`. Report accuracy, precision, recall, F1, FPR, FNR, EER, ROC-AUC, confusion matrix, latency (mean/median/p95).
6. Robustness tests (noise, compression if `ffmpeg` exists, telephone-style band-limiting, short clips) on `test` audio only, each clearly labeled; skipped experiments are logged as "not run" with the reason.
7. Save artifacts: `models/final_model.*`, `models/model_meta.json` (model type, features and parameters, training dataset name, window/clip length, sample rate, threshold and how it was chosen, seed, library versions, training date), and `results/*.json` + CSV (these feed the Model & Evaluation page).

If the audit shows the existing model is unusable (leakage, near-chance, training/inference mismatch), **say so plainly** and retrain properly.

## 5. Backend requirements

Implement what `docs/APP_BLUEPRINT.md` specifies (FastAPI, SQLite, `/api/*`, `/ws/live`, streaming engine with speech gate, smoothing, alert rule, verdict logic). Additions:

- The `Detector` loads `models/model_meta.json` and the final model **once**; window length comes from the metadata. If the model has no probability output, define what the displayed "probability" means (e.g. "model score") and use that wording in the UI.
- Verdict from score and threshold with a configurable uncertain band (design choice, labeled as such).
- Every analysis is stored with the threshold, band, model version and per-window scores.
- Demo set endpoint: `GET /api/demo/samples` lists `demo_holdout` files (id, name, duration — **ground-truth label hidden**); `POST /api/demo/analyze/{id}` analyzes one and the response **includes ground truth** so the UI can show "Model said X · Actual: Y ✓/✗" *after* the result. Demo replay in Call Monitor streams a chosen demo file in real time through the normal WebSocket path.
- Clear errors for bad files, oversized files, unsupported formats, model not loaded, DB errors.

## 6. Frontend rewiring (the core of the failure)

The exported Stitch screens are **layout and styling only**. Rebuild their behavior:

- Structure: `app/static/js/api.js` (all fetch/WebSocket calls, one place), `state.js`, `render.js` (pure functions that turn data into DOM), one small module per page. Vanilla JS, **no build step**. Use `<template>` elements or DOM builders; never leave sample markup in the page.
- In the HTML source, every data-bound element must contain only a neutral placeholder (`—` or empty) and a `data-bind="..."` attribute. **All values appear only after the API responds.**
- Charts (Chart.js or canvas) are created from API data, updated incrementally for live data, and destroyed/recreated cleanly on page changes. Vendor Chart.js **locally** so the demo works **offline**. If the Stitch export uses the Tailwind CDN, either confirm the presentation machine has internet or generate static CSS with Tailwind's standalone CLI (verify it works on Windows); report which you chose.
- Verdict chips, colors, icons, gauge fill, threshold marker, uncertain band, timeline highlights, KPI cards, tables, drawers, status pills and alert banners are **computed from data**. Color is never the only signal (icon + text).
- Every page has loading, empty and error states, handles backend-down (clear message, not stale data), and re-fetches after relevant actions (e.g. dashboard and history update after an analysis or a finished live session).
- Responsive: layout must work at 375, 768 and 1280 px widths (sidebar collapses on narrow screens; tables scroll horizontally; charts resize).
- Live Check and Call Monitor: `AudioWorklet` capture; mic via `getUserMedia`; system/tab audio via `getDisplayMedia` (handle "no audio shared"); demo replay; send `{mode, source, sample_rate}` then PCM16 frames; render `window`, `status`, `alert`, `summary` messages live; handle permission denied, device change, socket drop (one reconnect, then end with a partial summary).
- Settings controls persist through `/api/settings`, and **change the behavior of subsequent analyses** (threshold, band, smoothing, alert N, silence gate, store-raw-audio toggle).

### 6.1 Wiring matrix (mandatory deliverable)
Create `docs/WIRING_MATRIX.md`: one row per interactive or data-showing element on every page: `page | element | user action or data shown | endpoint/WS message | data source (model/DB/results file) | automated test or manual check | status (working / removed / not verified)`. Every row must reach "working" or be removed.

### 6.2 No-mock scanner (mandatory deliverable)
Write `scripts/scan_no_mock.py` that fails (non-zero exit) if it finds in `app/` (excluding `tests/`): `Math.random`, `faker`, `lorem`, fake-progress `setTimeout` patterns, any `data-bind` element whose source text is not `—`/empty, hard-coded numeric arrays passed to chart constructors, or API handlers returning literal constants for metrics. Run it and show the output. It must pass before the final phase.

## 7. Phases (stop after each; show proof)

**R0 — Diagnosis (no code changes).** Write `docs/DIAGNOSIS.md`: what exists, what is wired and what is not (backend, model, each page), how the model was trained and evaluated, existing `results/`, train/inference mismatches, leakage risks, every dead or fake UI element, and the dataset discovery from Section 3. Create `docs/PROJECT_STATE.md`. Show me.

**R1 — Data & splits.** Build manifests, the four disjoint sets, the leakage test, and a data-summary table. Proof: `pytest tests/test_no_leakage.py` output and the summary table.

**R2 — Model pipeline.** Shortcut check, baselines, CNN, model selection on `val`, threshold on `val`, single evaluation on `test`, robustness, `model_meta.json`, `results/`. Proof: results tables from the real run and the metadata file.

**R3 — Inference core + backend.** `Detector`, VAD, verdict, analyze-file, REST endpoints, SQLite, demo endpoints, tests. Proof: pytest output; two different fixture files give different, plausible results; the same file twice gives identical scores.

**R4 — Streaming engine + stream evaluation.** `/ws/live`, `StreamSession`, `scripts/stream_eval.py` replaying `val` files (and report `demo_holdout` results separately). Proof: window-level and file-level accuracy, FPR/FNR, alert behavior and latency, exactly as measured.

**R5 — Frontend rewiring: Dashboard, Analyze File, History.** Proof: wiring-matrix rows for these pages marked working with evidence, plus mutation tests M1–M4 and M7 (Section 8).

**R6 — Live Check + Call Monitor.** Proof: mutation tests M5, M6, plus the live checklist in Section 8.

**R7 — Model & Evaluation + Settings.** Page reads only `results/` and `model_meta.json`; settings change subsequent behavior (M3). Proof: tests plus screenshots or Playwright output.

**R8 — Hardening, responsiveness, offline, scanner.** File validation and limits, error handling, responsive check at 375/768/1280, offline check (internet disabled), `scripts/scan_no_mock.py` passing, `scripts/run_app.py` one-command start, `README` run instructions.

**R9 — Final acceptance + presentation pack.** Run the whole Section 9 checklist, update `docs/PROJECT_STATE.md`, and list every known limitation. Provide a short **demo script** (the exact click path using `demo_holdout` samples and what the audience should see).

## 8. Verification scenarios (automate where possible)

Prefer **Playwright for Python** with Chromium for browser tests (tell me the install commands first). For the live tests use Chromium's fake-media flags (`--use-fake-ui-for-media-stream`, `--use-fake-device-for-media-stream`, `--use-file-for-fake-audio-capture=<wav>`); **verify they work here**, and if not, give me a manual checklist instead. System/tab-audio capture usually cannot be automated, so give me a manual checklist for it.

- **M1** Upload a known real and a known fake `val` file → different results, per-file durations, timeline length matches duration, saved to history.
- **M2** Upload the same file twice → identical scores, two history rows.
- **M3** Set threshold to 0.0, analyze → "Likely Synthetic"; set 1.0, analyze → "Likely Real"; stored rows keep their own threshold.
- **M4** Clear history → dashboard shows zeros and empty states; history empty.
- **M5** Stop the backend → every page shows an error state, no stale numbers.
- **M6** Stream 3 s of silence → status "no speech", no scores; stream a known fake file → report whether the alert fired; stream a known real file → report whether it did **(report actual outcomes, even if wrong)**.
- **M7** Insert/modify a DB row directly → dashboard and history reflect it after refresh.
- **M8** Resize to 375/768/1280 px → no broken layout.
- **Live manual checklist:** mic reading moves with speech and flattens on silence; permission-denied message; Stop → summary saved to history; demo replay of a fake sample → expected reading shown with ground-truth reveal.

## 9. Definition of Done (all must be proven with real output)
- [ ] `pytest` passes, including the no-leakage test.
- [ ] `scripts/scan_no_mock.py` passes.
- [ ] `docs/WIRING_MATRIX.md` has no row that is not "working" or "removed".
- [ ] Model metrics on the UI equal the numbers in `results/`; dashboard numbers equal database counts.
- [ ] Upload, live mic, call monitor (mic, system audio, demo replay), history, settings, exports all function end-to-end.
- [ ] `demo_holdout` was never used for training, validation, tuning or thresholding (test + hash check).
- [ ] The app runs offline with one command.
- [ ] Limitations are listed honestly (live audio differs from the training data; results may be wrong or "Uncertain").

## 10. `docs/PROJECT_STATE.md` (update after every phase)
Keep: current phase and status; decisions made and why; dataset facts discovered; split sizes; chosen model and metrics (with file paths); exact commands to run, test and start the app; open issues and known limitations; the next phase. Keep it short and factual.

## 11. Response format (every phase)
1. Plan (≤8 lines) 2. Files created/changed (and what was reused vs replaced) 3. Commands run **with real output** 4. Proof against the phase's gate 5. Risks, assumptions, things NOT VERIFIED 6. `PROJECT_STATE.md` updated ✔ 7. Next phase (wait for my go-ahead).

## 12. Paste-ready prompts

**Start:** `Start Phase R0. Diagnose the repository and write docs/DIAGNOSIS.md and docs/PROJECT_STATE.md. Do not modify application code or install anything. Include the dataset discovery.`

**Next phases:** `Proceed to Phase R<N> exactly as specified in #file:docs/COPILOT_RECOVERY_PROMPT.md. Follow the response format and show real command output as proof. Stop at the end of the phase.`

**If you claim something works without proof:** `You did not show command output. Re-run, paste the real output, and mark anything unverified as NOT VERIFIED.`

**Debug:** `Full error and the relevant file: <paste>. Explain the cause in 2 lines, give the smallest fix as a diff, and show how you verified it.`
