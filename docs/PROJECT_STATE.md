# Project status

Last updated: 2026-10-20. This page is the short, current handoff; older working notes are kept locally in `.local-notes/` and are not part of the public repository.

## Current state

- FastAPI app and seven primary views are in the repository. Account sign-up/login, session handling, per-account data authorization, local SQLite, and PostgreSQL URL support are implemented.
- File analysis supports the legacy FoR window model and the ASVspoof complete-clip model. Live Check and Call Monitor use the FoR window model over a browser audio stream.
- Model weights, evaluation reports, dataset audio, and demo audio are intentionally excluded from Git. A checkout without matching local artifacts cannot perform detector inference.
- Before the page-folder rename, `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-r8-final` returned `53 passed, 2 warnings in 93.10s`; both warnings were librosa short-input `n_fft=1024` warnings. After the rename, the full suite returned `53 passed, 2 warnings in 66.31s`; details and browser acceptance are recorded below.
- Post-rename Edge acceptance covered all seven routes plus upload, live fake-audio stream, call-monitor demo replay, history source filter, settings save, account menu, and theme. Physical microphone and shared-tab/system audio remain **NOT VERIFIED**.

## Research limits

- The existing FoR held-out test result is weak: accuracy `0.5542`, ROC-AUC `0.7349`, EER `0.3272`, and false-negative rate `0.8235`. Do not market this as a reliable authenticity verdict.
- The ASVspoof metrics in the project are from balanced subsets; they are not full-set performance. See the saved report and dataset notes before quoting any number.
- Audio scores are estimates, not proof. Uncertain outcomes are valid. Performance on new generators, codecs, microphones, and noisy conditions is not established.
- Live monitoring analyzes a browser-provided microphone, shared-tab/system stream, or replay. It is not integrated with a phone network.

## Deployment gate

**Deployment source is prepared; hosted deployment is NOT VERIFIED.** The app now requires persistent PostgreSQL on Vercel, downloads a private model bundle into `/tmp`, verifies its SHA-256 and exact file allowlist, and uses those packaged model/report paths for API inference. No Vercel project, PostgreSQL URL, or private artifact URL is configured here. Hosted WebSocket behavior, model cold start, request limits, migrations, and account isolation remain **NOT VERIFIED**. Local SQLite is not durable serverless storage.

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
- Physical microphone and shared-tab/system audio are still **NOT VERIFIED**. Responsive checks at 375, 768, and 1280 px were completed later (see the R8 local stylesheet section). The app is running locally at `http://127.0.0.1:8000/`; this does not clear the Vercel deployment gate.
- This later acceptance supersedes the earlier headless microphone-start failure recorded above: fake-audio Live Check succeeded in the later run. Physical devices still need interactive-browser verification.


## R8 local stylesheet and final regression — 2026-10-20

- Reused the exact shared Tailwind theme from all seven existing page templates and generated a checked-in local CSS bundle. The pages no longer request Tailwind from `cdn.tailwindcss.com`; no layout markup or detector logic was replaced for this change. `package.json` and `package-lock.json` pin the build-only Tailwind CLI. Regenerate with `npm ci --ignore-scripts --no-audit --no-fund` then `npm run build:css`; normal app startup does not require Node.
- `npm run build:css` output: `Done in 751ms.` (Tailwind warns its bundled Browserslist data is outdated.) The bundle is 31,854 bytes. External Google Fonts/Material Symbols and the hosted logo remain network resources, so full offline rendering is **NOT VERIFIED**.
- Final regression command `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-r8-final-css` returned `53 passed, 2 warnings in 92.21s`; warnings are librosa short-input `n_fft=1024` warnings. `scripts/scan_no_mock.py` reported no mock patterns in 32 active app files and confirmed authenticated page routing. Node syntax checks, Python compilation, and `git diff --check` exited 0.
- Post-build `.local-notes\browser_demo_acceptance.py` Edge run opened all seven authenticated routes without backend error panels; upload and history, settings save, live fake-audio stream, Call Monitor demo replay, account menu/theme toggles all completed. Browser JS exceptions were `[]`; disposable account cleanup returned HTTP 200. A second Edge run at 375, 768, and 1280 px found `document.documentElement.scrollWidth == innerWidth` on all seven routes at each width; the 375 px dashboard screenshot was visually inspected. Physical microphone, shared-tab/system audio, full offline use, and hosted Vercel behavior remain **NOT VERIFIED**.

## Current streaming evaluation command — 2026-10-20

`.venv\Scripts\python.exe scripts\stream_eval.py` exited 0. It scored 100 files from the validation manifest (first 50 per class): file accuracy 0.99, ROC-AUC 0.9976, EER 0.02, FPR 0.02, FNR 0.00; file latency mean 15.69 ms, median 3.80 ms, p95 4.61 ms. This is a small validation sample, not the official test set or a generalization claim. The separately reported locked 50-file `demo_holdout` was scored using the ASVspoof complete-clip model (not the live FoR stream model): accuracy 0.88, ROC-AUC 0.9536, EER 0.16, FPR 0, FNR 0.24; mean latency 4.33 ms. It was not used for fitting, validation, threshold selection, or tuning. The weak FoR held-out test result above remains the relevant warning against claiming reliable authenticity detection.

## Vercel runtime packaging and regression — 2026-10-20

- Added Vercel runtime configuration, Python 3.14 selection, pinned inference dependencies, and deployment exclusions so datasets, trained weights, results, tests, and local notes are not in the Git/Vercel source bundle. `requirements-dev.txt` keeps research/test packages separate from the server runtime.
- Added a deployment artifact loader that requires a configured HTTPS bundle URL and SHA-256 on Vercel, rejects unexpected/unsafe ZIP members, and installs verified files under `/tmp`. PostgreSQL is enforced for Vercel; concurrent cold-start migrations use a PostgreSQL transaction advisory lock, and each function instance uses a one-connection pool.
- Added Supabase transaction-pooler support: Vercel PostgreSQL URLs on port 6543 use SQLAlchemy `NullPool` and Psycopg `prepare_threshold=None`, as required by Supabase's SQLAlchemy guidance. Preview startup migrations still need verification; use the Supabase session pooler if the transaction pooler rejects them.
- Added `scripts/package_runtime_artifacts.py`. The generated local-only bundle `.local-notes/deployment/voiceguard-runtime-r8.zip` is 2,287,845 bytes with SHA-256 `1354d50f1157c8e902bdd557f7285fb61be31ea237f0bdecc500c0bc3f4d341f`. It contains seven approved model, metadata, report, and count-manifest files; no dataset audio/manifests. The archive is ignored and must be uploaded to private HTTPS storage during Vercel setup.
- `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-supabase-final` returned `62 passed, 2 warnings in 120.45s`; the warnings are the existing librosa short-input `n_fft=1024` warnings. The first deployment regression run exposed a stale ASVspoof loader call in demo analysis; it was corrected before this passing run. Regression tests cover Supabase pooler settings and confirm download errors do not expose a signed artifact URL.
- Bundle verification loaded both real packaged detector classes successfully from the extracted bundle (`bundle_validation=passed`, both detectors loaded, seven members). `scripts/scan_no_mock.py` reported no mock patterns in 32 active application files and confirmed authenticated page routing. Python compilation, `node --check app\\static\\app-runtime.js`, and `python -m json.tool vercel.json` exited 0 (`vercel.json: valid JSON`).
- **NOT VERIFIED:** Vercel Preview/Production deployment, hosted PostgreSQL migrations and account isolation, private artifact download using a real storage provider, actual Vercel model inference, and hosted `/ws/live` upgrade/streaming. Vercel's WebSocket knowledge-base article says Functions natively support WebSockets, while its Limits page says they cannot act as a WebSocket server; complete the Preview acceptance in [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md) before relying on Live Check or Call Monitor there. Demo Replay has no hosted samples because demo audio/datasets remain excluded.

## Remaining gate / next phase

R8's remaining device checks are physical-microphone, shared-tab/system audio, and offline behavior; these remain separate from the deployment work above. Deployment requires PostgreSQL and private artifact environment variables in Vercel, uploading the ignored local bundle to private HTTPS storage, then completing the Preview acceptance steps in [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md). The weak held-out FoR metric remains a research limitation regardless of successful deployment.

## Deployment follow-up — 2026-10-20

- The local site is already running. An elevated read-only request to `http://127.0.0.1:8000/api/health` returned HTTP 200 with `{"status":"ok","ready":true,"database_connected":true,"model_loaded":true,"model_version":"classical_for_2sec","profiles":{"legacy_for2sec":true,"asvspoof_la_balanced2500":true}}`.
- The public `https://voicegaurd.vercel.app` does not serve this repository's current app: its `/api/health` returns only `{"status":"ok","application":"VoiceGuard"}`, and `/login` returns HTTP 404. This conflicts with `app/main.py`, which returns readiness, database, and model fields and defines `/login`. The current Vercel deployment/alias therefore remains **NOT VERIFIED** for this repository.
- `npx --yes vercel@latest whoami` downloaded Vercel CLI 64.7.0, then exited 1 while saving CLI config (`EXDEV: cross-device link not permitted`). No `.vercel/project.json`, `VERCEL_TOKEN`, or saved Vercel auth file was present, so project settings could not be inspected or changed.
- The ignored model bundle remains local at `.local-notes/deployment/voiceguard-runtime-r8.zip` (2,287,845 bytes; SHA-256 `1354d50f1157c8e902bdd557f7285fb61be31ea237f0bdecc500c0bc3f4d341f`). No private artifact URL/token or Vercel database environment was configured in this phase.

## Vercel Preview runtime gate — 2026-10-20

- Authenticated Vercel CLI access was recovered using an ignored local config directory. The `voicegaurd` project is linked, a private Blob store is connected, and the Preview/Production artifact URL and SHA-256 environment entries are configured as Vercel secrets. No credentials or private Blob URL were added to tracked files.
- `npx --yes vercel@latest deploy --yes --global-config .local-notes/vercel-cli` returned `readyState: READY` for Preview deployment `dpl_Cemth4VfZSzCBFUxMNx5AeFUipDh` at `https://voicegaurd-ramdkp1jh-ujjwal21822s-projects.vercel.app`. The Python 3.14 build completed in 28 seconds; Vercel reported a 465.90 MB optimized dependency bundle.
- Protected request `npx --yes vercel@latest curl https://voicegaurd-ramdkp1jh-ujjwal21822s-projects.vercel.app/api/health` reached the function but returned `FUNCTION_INVOCATION_FAILED`. Sanitized Vercel runtime logs show PostgreSQL could not resolve the host parsed from `DATABASE_URL`; reserved characters in its credentials were not URL-encoded. The current DB password was shared in chat and must be rotated before Production use. Copy Supabase's transaction-pooler URL into Vercel `DATABASE_URL` after rotation; percent-encode reserved characters such as `@` (`%40`) and `#` (`%23`). Do not record credentials here or send them in chat.
- The function traceback reaches `DATABASE.initialize()` after `prepare_runtime_artifacts()` and `configure_artifact_root()`. This confirms the protected Preview passed private Blob download, ZIP validation, and artifact-root setup; model loading/inference remains unverified because startup stops at the database step.
- The same cold-start log window also contains `ImportError: cannot import name 'vc_handler' from 'vercel_runtime.vc_init'`. It is **NOT VERIFIED** whether this is a separate runtime issue or a secondary failure after application startup aborts. Recheck after `DATABASE_URL` is corrected.
- Local verification after the deployment change: `.venv\Scripts\python.exe -m pytest -q tests\test_deployment_artifacts.py --basetemp .pytest-tmp-vercel-preview` returned `11 passed in 0.88s`; Python compilation exited 0; `scripts/scan_no_mock.py` found no mock data patterns in 32 active application files and confirmed authenticated page routing; `git diff --check` exited 0 (only line-ending warnings).
- Hosted database connection and migrations, runtime model loading/inference, account isolation, upload/history, `/ws/live`, Demo Replay, and Production are **NOT VERIFIED**. Production has not been promoted. The original URL-encoding diagnosis below has been superseded by the current IPv6 route finding and Supabase access blocker recorded in the follow-up section.

## Supabase connection follow-up — 2026-10-20

- Rechecked the latest Vercel Preview log evidence: the encoded Preview URL gets past URL parsing, then the direct Supabase database endpoint resolves to IPv6 and the Vercel Function reports `psycopg.OperationalError ... Cannot assign requested address`. The earlier invalid-host diagnosis is superseded for the current Preview deployment. Vercel's IPv4-only runtime requires the exact Supabase shared-pooler endpoint (or a separately configured IPv4 route); pooler hostnames and usernames must be copied from this project's connection settings, not guessed.
- The user supplied an `sb_secret_...` Supabase API key in chat. It was not used, copied to a file, sent to Vercel, or committed. Supabase documents this key as elevated data API access that bypasses RLS, not a PostgreSQL URL or Management API credential. It should be rotated immediately. The previously shared database password also remains exposed and requires rotation before production.
- Supabase access became available through the connected project integration. `supabase_get_project` reported project `voiceguard` as `ACTIVE_HEALTHY` in `ap-northeast-1`; `supabase_list_migrations` returned `migrations: []`, `supabase_list_tables` returned `tables: []`, and the security advisor returned `lints: []`. The project is fresh, so no database contents were changed; the app's existing Alembic startup migrations remain responsible for schema creation.
- The connected tools do not expose the project's exact Supavisor connection URL or database/API-key rotation controls. The secret API key was not used, copied to a file, sent to Vercel, or committed. Without the exact pooler host/username and authorized secret-rotation control, Vercel's Preview `DATABASE_URL` cannot be safely corrected and the exposed credentials cannot be rotated here. Hosted readiness remains **NOT VERIFIED**; Production was not promoted and no GitHub push was made.
- Local site check: `Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing | Select-Object -ExpandProperty Content` returned `{"status":"ok","ready":true,"database_connected":true,"model_loaded":true,"model_version":"classical_for_2sec","profiles":{"legacy_for2sec":true,"asvspoof_la_balanced2500":true}}` (exit 0).
- `git diff --check` exited 0; only documentation changed in this follow-up, so no application tests were rerun. The local tree remains on `codex/frontend-pages-naming`; these documentation changes are not pushed.
- Official references checked: Supabase [API keys](https://supabase.com/docs/guides/getting-started/api-keys), [Management API](https://supabase.com/docs/reference/api/introduction), [PostgreSQL connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres), and [IPv4/IPv6 compatibility](https://supabase.com/docs/guides/troubleshooting/supabase--your-network-ipv4-and-ipv6-compatibility-cHe3BP).
