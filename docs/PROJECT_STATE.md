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

At the initial code-cleanup gate, these UI changes had not yet had a browser click/visual acceptance
pass; the follow-up below records the browser checks and remaining live-capture limitation.

## R8 browser follow-up — 2026-10-20

Fixed two issues found during the authenticated browser pass: History's `All Verdicts` option now
has an empty value so it does not filter out every record, and the sidebar model status now follows
the selected profile's `/api/health` readiness instead of always showing `ONLINE`.

Local proof:

```text
node --check app\static\stitch-runtime.js
exit 0
.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 32 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-r8-browser-audit
53 passed, 2 warnings in 81.66s
```

Headless Edge acceptance used `.local-notes\browser_acceptance_r8.py` and a disposable account; the
account plus its temporary records were deleted (cleanup returned HTTP 200). All seven authenticated
routes rendered without a `Backend unavailable` panel, and the browser reported `Browser JS
exceptions: []`. The dashboard showed `READY` from health. Uploading one existing local training WAV
produced an API-backed result and one saved `Upload` history row; the source filter kept that row.
Settings save returned the real `Settings saved` toast. User menu open/Escape close and both dashboard
and login theme toggles changed state. No seeded voicemail telemetry was present.

Live capture is **NOT VERIFIED in this headless run**: consent correctly kept Start disabled until
checked, but Edge's fake microphone attempt returned `Microphone could not be started: Not supported`
and saved no live session. The device does not expose physical mic/system-tab capture to this run.
Although the earlier R7 acceptance recorded a successful Edge fake-audio stream, repeat that test in
the user's interactive Chrome/Edge browser before claiming current live capture acceptance. System/tab
audio, demo replay, mobile widths beyond the measured 360 px headless viewport, API-down rendering,
offline use, and Vercel/PostgreSQL remain **NOT VERIFIED**.
