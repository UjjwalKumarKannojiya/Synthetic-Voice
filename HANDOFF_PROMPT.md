# HANDOFF PROMPT — continue the project with a new coding agent (Codex / Antigravity / any)

**Goal:** the new agent must (1) work out what is *actually* done by inspecting evidence, (2) protect existing work, (3) continue with the remaining steps of the same plan.

---

## PART 1 — Student checklist BEFORE switching (5–10 minutes, do it yourself)

Open a terminal in the project folder and run these one at a time.

**A. Save a checkpoint with git** (this is your undo button):
```
git status
```
- If it says "not a git repository": run `git init`.
- Make sure `.gitignore` contains `data/`, `models/`, `.venv/`, `__pycache__/`. (The dataset is ~7 GB and must never be committed.)
```
git add -A
git commit -m "checkpoint: state when Copilot limit was reached"
git tag checkpoint-copilot-final
git checkout -b agent2-work
```
From now on the new agent works only on the branch `agent2-work`. If it damages something: `git checkout main` (or `master`) returns you to the saved state. Note: `data/` and `models/` are not in git, so **do not let the agent delete or regenerate them**.

**B. Make sure the knowledge files are inside the repo (`docs/`):**
`COPILOT_RECOVERY_PROMPT.md`, `COPILOT_ASVSPOOF_DATA_PROMPT.md`, `APP_BLUEPRINT.md`, `MASTER_PROMPT.md`, `COPILOT_APP_PROMPT.md`, `STITCH_PROMPT.md`, the synopsis PDF, the handbook PDF, the study-content `.txt`, and the Stitch exports in `frontend_design/`. Also put `AGENTS.md` (provided separately) in the repository root.

**C. Quick look at the state yourself** (paste the outputs to the agent if you like):
```
git log --oneline -20
dir /b docs
dir /b results
dir /b models
dir /b data\manifests
python -m pytest -q
```

**D. Tool settings:** use one agent at a time on this folder. Keep it in a mode that **asks approval before deleting files or running commands**. Do not use a fully automatic mode on the folder that holds your dataset.

---

## PART 2 — Paste this into the new agent (first message)

```
You are taking over an unfinished project from another coding assistant that ran out of usage limits. You have NO memory of previous work. Do not trust any claim in the docs or code comments about what is "done" unless you can verify it yourself.

READ FIRST (in this priority order; if they conflict, the earlier one wins):
1. AGENTS.md
2. docs/COPILOT_RECOVERY_PROMPT.md
3. docs/COPILOT_ASVSPOOF_DATA_PROMPT.md
4. docs/APP_BLUEPRINT.md
5. docs/MASTER_PROMPT.md, docs/COPILOT_APP_PROMPT.md (older; superseded where they conflict)
6. docs/PROJECT_STATE.md, docs/DIAGNOSIS.md, docs/DATASET_NOTES.md, docs/WIRING_MATRIX.md (if they exist)
7. The synopsis, handbook and presentation in docs/ for project intent
Wherever those documents say "Copilot", it means "you".

PROJECT IN BRIEF (for orientation; verify against the repo):
- Synthetic Voice Forensics: detect real vs AI-generated speech (label 0 = real, 1 = fake, score = P(fake)). MCA dissertation. The research angle is robustness and generalization, not just accuracy.
- Dataset: ASVspoof 2019 LA (official train / dev / eval partitions; eval contains unseen attacks). Project sets: train = official train, val = official dev, test = official eval minus demo speakers, demo_holdout = a few whole eval speakers, locked, never used for training, tuning or thresholds.
- Deliverables: working model (MFCC/CQCC + SVM/RF, small CNN), evaluation with accuracy/precision/recall/F1/FPR/FNR/EER/AUC/latency, robustness tests, and a working FastAPI + HTML/JS web app with: upload check, live microphone check, live call monitor (microphone / system-or-tab audio / demo replay; not a phone-network integration), dashboard, history, model & evaluation page, settings.
- Environment: Windows 11, 8 GB RAM, CPU only, Python venv, Chrome/Edge on localhost.
- Known earlier problem: the UI had been built as a static copy of the design (not wired to data) and the model's correctness was unverified.

PHASE H0 — STATE RECONSTRUCTION (READ-ONLY; change no existing file):
1. Check you are on branch agent2-work (do not work on main). Run `git log --oneline -30` and `git status`.
2. List the repository tree (excluding .venv, data/raw contents, node_modules) and the contents of docs/, results/, models/, data/manifests/ (names, sizes, dates only).
3. Run the existing tests (`python -m pytest -q`) and record the exact output as the BASELINE. Try to start the app with the documented command and record whether it starts. Do not fix anything yet.
4. For each item in the checklist below, decide a status using ONLY evidence you gathered: DONE-VERIFIED (you ran something and saw the proof), DONE-UNVERIFIED (files exist but you could not or did not verify), PARTIAL, BROKEN, NOT STARTED. Cite the file or command output for each.
   Checklist:
   - Dataset downloaded, extracted, integrity-checked (D0–D3 of the ASVspoof prompt)
   - Manifests and the four disjoint sets; tests/test_no_leakage.py exists and passes (D4)
   - Data quality/shortcut checks, class-imbalance handling (D5)
   - Per-attack and known/unknown breakdown (D6)
   - Shortcut metadata baseline; MFCC/CQCC + SVM/RF; CNN; model selected on val; threshold chosen on val; single test evaluation; robustness results; models/model_meta.json; results/*.json (R2)
   - Detector, VAD, verdict logic, analyze-file, REST API, SQLite, demo endpoints (R3)
   - WebSocket streaming engine and scripts/stream_eval.py with real measured output (R4)
   - Frontend pages wired to real data (Dashboard, Analyze File, History) (R5); Live Check and Call Monitor (R6); Model & Evaluation and Settings (R7)
   - Hardening, responsiveness, offline operation, scripts/scan_no_mock.py (R8); final acceptance and demo script (R9)
5. Detect half-finished work: files with TODO/stub/NotImplemented, failing or missing tests, endpoints returning constants, HTML elements with hard-coded values, imports that fail, scripts that crash.
6. Check protected assets: confirm data/ and models/ exist and are untouched; confirm demo_holdout manifest exists and report whether it is locked. Do NOT regenerate splits or retrain anything in this phase.
7. Write docs/STATE_RECONSTRUCTION.md (status table + evidence + the first incomplete phase + risks) and create or update docs/PROJECT_STATE.md. Commit only these two files.
8. STOP and show me the table. Wait for my approval before any other change.

PROTECTION RULES FOR ALL LATER WORK:
- Work only on branch agent2-work, in small commits, one logical change each, with clear messages.
- Never delete, rename or overwrite existing files, data, models, manifests or results without (a) listing them, (b) giving the reason, and (c) my explicit approval.
- Do not regenerate splits, re-download data or retrain models unless the audit proves the existing ones invalid and I approve.
- Never use or touch demo_holdout for training, validation, tuning or thresholds.
- No big rewrites. If existing code is wrong, show the minimal diff and explain; keep what works.
- Run the baseline tests before and after each phase; no regression is allowed. If a test fails, report it instead of editing the test to pass.
- Evidence over assertion: never say "works", "fixed" or "done" without the exact command and its real output. Otherwise write NOT VERIFIED.
- No fabricated data, numbers or capabilities anywhere in the app. No dead UI controls (each works or is removed).
- Install packages only after telling me the exact command.

AFTER I APPROVE H0:
Continue with the first phase that is not DONE-VERIFIED, following the phase definitions, gates and response format in docs/COPILOT_RECOVERY_PROMPT.md and docs/COPILOT_ASVSPOOF_DATA_PROMPT.md. One phase at a time; stop and show proof at the end of each; update docs/PROJECT_STATE.md after every phase.

Reply now with: (1) a 10-line summary of what you understood, (2) risks, (3) confirmation of the protection rules. Then wait for me to say "start H0".
```

---

## PART 3 — If the new agent also runs out of limit

Do not panic: the repository is the memory. Each phase ends with an updated `docs/PROJECT_STATE.md` and a git commit. In the next tool, repeat Part 2 (H0 will rebuild the state in minutes).

**Resume prompt (short):**
```
Read AGENTS.md, docs/PROJECT_STATE.md and docs/STATE_RECONSTRUCTION.md. Run `git log --oneline -15`, `git status` and `python -m pytest -q`. Report the current phase and anything unfinished or inconsistent, then wait for my go-ahead. Change nothing yet.
```
