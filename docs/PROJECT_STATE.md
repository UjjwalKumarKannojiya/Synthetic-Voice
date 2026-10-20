# Project status

Last updated: 2026-10-20. This page is the short, current handoff; older working notes are kept locally in `.local-notes/` and are not part of the public repository.

## Current state

- FastAPI app and seven primary views are in the repository. Account sign-up/login, session handling, per-account data authorization, local SQLite, and PostgreSQL URL support are implemented.
- File analysis supports the legacy FoR window model and the ASVspoof complete-clip model. Live Check and Call Monitor use the FoR window model over a browser audio stream.
- Model weights, evaluation reports, dataset audio, and demo audio are intentionally excluded from Git. A checkout without matching local artifacts cannot perform detector inference.
- Before the page-folder rename, `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-r8-final` returned `53 passed, 2 warnings in 93.10s`; both warnings were librosa short-input `n_fft=1024` warnings. After the rename, the full suite returned `53 passed, 2 warnings in 66.31s`; details and browser acceptance are recorded below.
- Post-rename Edge acceptance covered all seven routes plus upload, live fake-audio stream, call-monitor demo replay, history source filter, settings save, account menu, and theme. Physical microphone, shared-tab/system audio, and additional viewport sizes remain **NOT VERIFIED**.

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
node --check app\static\app-runtime.js
exit 0
.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 32 active application files.
Page templates are served through authenticated routes; direct static template URLs remain blocked.
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

## Frontend naming and repository artifact check — 2026-10-20

- Renamed active templates from `app/static/stitch/` to `app/static/pages/` and the runtime from `stitch-runtime.js` to `app-runtime.js`. Updated the FastAPI page route, direct-template protection, no-mock scanner, route test, and setup/wiring references. All seven page files remain; no UI content was intentionally removed.
- `.venv\Scripts\python.exe -m py_compile app\main.py scripts\scan_no_mock.py tests\test_api.py` exited 0. `node --check app\static\app-runtime.js` exited 0. `.venv\Scripts\python.exe scripts\scan_no_mock.py` printed `No mock data patterns found in 32 active application files.` and `Page templates are served through authenticated routes; direct static template URLs remain blocked.`
- `git ls-files -- data models results` returned no paths (`Tracked research artifacts: 0`). `git check-ignore -v data models results` confirmed all three roots are ignored. Local files were left untouched.

## Post-rename route and browser acceptance — 2026-10-20

- `.venv\Scripts\python.exe -m pytest -vv -q tests\test_api.py::test_frontend_and_profile_metrics_are_real_routes --basetemp .pytest-tmp-r8-route-acceptance` returned `1 passed in 1.94s`. `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-r8-pages-full` returned `53 passed, 2 warnings in 66.31s`; both warnings are librosa short-input `n_fft=1024` warnings.
- Local site after restart: `/api/health` returned HTTP 200 with `model_loaded: true`; `/static/app-runtime.js` returned HTTP 200 (97,204 bytes); direct `/static/pages/dashboard.html` returned HTTP 404; unauthenticated `/dashboard` returned HTTP 303 to login.
- Headless Edge opened all seven authenticated routes without backend error panels or JS exceptions. A file upload returned a measured FoR result and persisted history; the Upload filter kept its record; Settings Save displayed its API-backed success toast; account menu and theme toggles worked.
- A fake-audio browser stream completed Live Check, produced model windows, and persisted history. Call Monitor demo replay completed a 3.9 second clip, produced two live FoR windows, saved history, and revealed the separate ASVspoof complete-clip result afterward. Disposable test accounts were deleted (HTTP 200).
- Physical microphone and shared-tab/system audio are still **NOT VERIFIED**. The app is running locally at `http://127.0.0.1:8000/`; this does not clear the Vercel deployment gate.
- This later acceptance supersedes the earlier headless microphone-start failure recorded above: fake-audio Live Check succeeded in the later run. Physical devices still need interactive-browser verification.
