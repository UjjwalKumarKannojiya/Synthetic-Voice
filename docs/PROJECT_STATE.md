# Project status

Last updated: 2026-10-20. This page is the short, current handoff; older working notes are kept locally in `.local-notes/` and are not part of the public repository.

## Current state

- FastAPI app and seven primary views are in the repository. Account sign-up/login, session handling, per-account data authorization, local SQLite, and PostgreSQL URL support are implemented.
- File analysis supports the legacy FoR window model and the ASVspoof complete-clip model. Live Check and Call Monitor use the FoR window model over a browser audio stream.
- Model weights, evaluation reports, dataset audio, and demo audio are intentionally excluded from Git. A checkout without matching local artifacts cannot perform detector inference.
- Local checks on 2026-10-20: `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-r8-final` returned `53 passed, 2 warnings in 93.10s`; both warnings are librosa short-input `n_fft=1024` warnings. `node --check app\static\stitch-runtime.js` exited 0. `.venv\Scripts\python.exe scripts\scan_no_mock.py` printed `No mock data patterns found in 32 active application files.`
- The latest HTML/runtime cleanup was covered by syntax and no-mock checks. A new browser interaction/visual sweep after those exact edits is **NOT VERIFIED**.

## Research limits

- The existing FoR held-out test result is weak: accuracy `0.5542`, ROC-AUC `0.7349`, EER `0.3272`, and false-negative rate `0.8235`. Do not market this as a reliable authenticity verdict.
- The ASVspoof metrics in the project are from balanced subsets; they are not full-set performance. See the saved report and dataset notes before quoting any number.
- Audio scores are estimates, not proof. Uncertain outcomes are valid. Performance on new generators, codecs, microphones, and noisy conditions is not established.
- Live monitoring analyzes a browser-provided microphone, shared-tab/system stream, or replay. It is not integrated with a phone network.

## Deployment gate

**Not ready for production or Vercel deployment.** No Vercel preview or persistent PostgreSQL connection has been tested, and model/report artifact delivery is not configured. Hosted WebSocket behavior, model cold start, request limits, and hosted database migration remain **NOT VERIFIED**. Local SQLite is not durable serverless storage. Do not deploy until the student configures hosted PostgreSQL and private model/report delivery, then completes a Vercel preview test.

The local app is started with `python scripts/run_app.py` and opened at `http://127.0.0.1:8000/`. Read [README.md](../README.md) for setup and [AUTH_DEPLOY_PLAN.md](AUTH_DEPLOY_PLAN.md) for the deployment gate.

## Current code changes in R8 hardening

- Removed seeded dashboard and history rows, bogus archive metadata, misleading compliance/latency claims, and simulated evaluation report progress.
- Dashboard counters, saved-analysis count, and history source/verdict filters are populated from API data.
- Evaluation export downloads the available report JSON; model hash display/copy uses loaded model metadata.
- Removed the fake analysis telemetry export and nonfunctional batch/calibration controls from the upload view.
- Preserved original long-form status notes locally before shortening this document. No data, split, model, or result artifact was changed.

These specific latest UI changes have not had a browser-based click/visual acceptance pass yet.
