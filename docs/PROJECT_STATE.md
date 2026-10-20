# Project State

## Current phase

R8 automated checks and V1–V4 local authentication/storage/browser gates are complete. V5 local
preflight is in progress: a root FastAPI entrypoint and stricter secret/data ignore rules are added.
Vercel preview, persistent PostgreSQL, and model artifact delivery are still not configured, so the
project is NOT READY for deployment. Offline packaging and physical device/source acceptance remain
pending. Local SQLite is not suitable for durable Vercel storage.

## Decisions

- Preserve the existing `for-2sec`, `for-norm`, and `for-rerec` artifacts as prior
  research evidence; do not merge them with ASVspoof without a new protocol.
- Use the project-local `.venv\Scripts\python.exe`; bare `python` is not configured.
- ASVspoof copy structure, manifests, and audio metadata are measured in
  `docs\DATASET_NOTES.md`; retain its caveat that measured speaker counts differ
  from the task prompt's stated counts.
- Keep raw ASVspoof data out of version control and do not download PA.

## Dataset facts discovered

- D drive free space: `284067926016` bytes (`264.56 GB`).
- Existing ASVspoof LA tree: `LA\LA\`, with CM/ASV protocols, ASV scores,
  train/dev/eval directories, README, and per-partition licenses.
- README claims 16 kHz, 16-bit FLAC and CM protocol columns
  `speaker file system_id unused key`; labels are `bonafide`/`spoof` and attacks
  are A01-A19.
- Measured files: train 25,380, dev 24,986, eval 71,933; all are mono 16 kHz FLAC
  with zero metadata read errors.
- Protocol rows: train 25,380, dev 24,844, eval 71,237. Dev has 142 and eval has
  696 unreferenced files; no protocol IDs are missing from the audio directories.
- Measured speakers: train 20, dev 20, eval 67. This differs from the task prompt's
  20/10/48 description and is documented in `docs\DATASET_NOTES.md`.
- Spoof attacks: train/dev A01-A06; eval A07-A19.
- Duration medians: train 3.2015 s, dev 3.2835 s, eval 2.8431 s; all are variable.
- SHA-1 manifests generated for all 121,461 protocol-referenced FLAC files.
- D4 sets: train 25,380; val 24,844; test 69,453; demo_holdout 50.
- Demo holdout: fixed seed 42, whole speaker LA_0045, balanced 25/25, spoof
  attacks A07, A10, A12-A19. The remaining test set has 66 speakers.
- `tests\test_no_leakage.py`: 3 passed; no path, SHA-1, or speaker overlap among
  the four sets. The 838 unreferenced dev/eval files are excluded and listed in
  `asvspoof_la_exclusions.csv`.
- D5 quality run used 1,000 files per class per train/val/test split, seed 42,
  silence threshold 0.01; demo holdout was not read.
- Full-set imbalance is approximately 89.6%-89.8% spoof (train 2,580/22,800,
  val 2,548/22,296, test 7,209/62,244). Demo is balanced 25/25.
- Metadata-only logistic baseline, fit on train metadata, scored on balanced
  samples: validation accuracy 0.689, ROC-AUC 0.7492; test accuracy 0.794,
  ROC-AUC 0.8658. This is a strong shortcut warning.
- D5 JSON: `results\asvspoof_la_data_quality.json`; plots:
  `results\asvspoof_la_plots\`.
- D6 evaluator added at `scripts\asvspoof_eval_breakdown.py`; it requires real
  score CSVs and reports per-attack and known/unknown metrics. It explicitly
  records min t-DCF as not computed because ASV speaker-verification scores are
  unavailable.
- Bounded R2 MFCC/SVM run: 500 files/class per train/val/test split, seed 42,
  demo excluded. Validation accuracy 0.895, ROC-AUC 0.9538, EER 0.1060;
  test accuracy 0.885, ROC-AUC 0.9412, EER 0.1220. Threshold
  0.5582105951032585 selected on validation EER.
- D6 test breakdown: eval contains only unknown spoof attacks A07-A19, so known
  spoof metrics are undefined. Per-attack JSON is
  `results\asvspoof_la_svm_breakdown.json`.
- Expanded R2 run: 2,500 files/class per train/val/test, seed 42, demo excluded.
  Validation accuracy 0.9112, ROC-AUC 0.9715, EER 0.0888; test accuracy 0.8808,
  ROC-AUC 0.9418, EER 0.1280. Frozen validation threshold
  0.8323956492443629. These are still balanced subset results.
- R3 added `app\core\asvspoof_detector.py`, which loads the explicit ASVspoof
  balanced2500 artifact, uses shared MFCC preprocessing, scores complete
  variable-duration clips, and returns an explicit model version/score definition.
  It does not replace the existing FoR detector or backend implicitly.
- R3 tests: `7 passed in 5.49s` for detector, breakdown, and leakage tests.
- Artifact smoke output: `asvspoof_la_mfcc_svm_balanced2500_seed42`.
- Backend now exposes explicit profiles: `legacy_for2sec` (default) and
  `asvspoof_la_balanced2500` for upload/model-info. Unknown profiles return 400;
  upload history persists the selected model version. Live WebSocket remains
  legacy-only because the ASVspoof model is complete-clip rather than windowed.
- Profile/API validation: `8 passed in 9.29s`.
- Demo endpoints added: `GET /api/demo/samples` hides labels; `POST
  /api/demo/analyze/{sha1}` analyzes with ASVspoof and reveals ground truth only
  in the result. Demo/API validation: `9 passed in 4.54s`.
- `data\raw\` was created; it is empty. `data\manifests\` and `data\features\`
  already existed.

## Existing model evidence

- Model: `models\classical_for_2sec\svm.joblib`.
- Contract: `models\model_meta.json`; 16 kHz, 2-second windows, MFCC plus delta and
  delta-delta summaries, validation-EER threshold `0.6786657728693419`.
- Primary SVM test: accuracy `0.5542279411764706`, ROC-AUC
  `0.7349021410034602`, EER `0.3272058823529411`, FNR `0.8235294117647058`.
- Metadata baseline test accuracy: `0.6856617647`; shortcut warning remains active.
- These are existing artifacts, not new R2 results.

## Commands

Use the project interpreter:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Open issues and limitations

- UI audit on 2026-10-19: `node --check app/static/stitch-runtime.js` exited 0; `python scripts/scan_no_mock.py` printed `No mock data patterns found in 26 active application files.` Edge rendered `/dashboard`, `/analyze-file`, `/call-monitor`, `/history`, `/model-and-evaluation`, and `/settings`; visual review found no sample upload verdict, seeded history drawer, seeded model latency/robustness cards, or seeded Call Monitor alert after cleanup. Dashboard recent rows and history rows are sourced from the local database; model test metrics remain from `results/`.
- API/browser proof: `GET /api/health` returned HTTP 200 with `model_loaded:true`; `GET /call-monitor` returned HTTP 200. Current listener PID was 16768 after the final cache-busted restart. Edge was launched to `http://127.0.0.1:8000/dashboard`.
- Responsive shell was inspected at 375 px; the menu collapses to a page selector and the supplied page design remains. Other viewport widths and interactive control paths are NOT VERIFIED.
- The no-mock scan is pattern based and does not prove all visible values are real. Several source templates still contain static content; the active UI currently removes or overwrites audited examples, but a complete per-element DOM/API acceptance audit remains outstanding.

- ASVspoof copy verification, leakage-safe four-set manifests, D5, D6, and R3
  detector contract are documented as complete.
- The recovery prompt, app blueprint, master prompt, and app prompt are present
  at repository root rather than under `docs\` as the instructions describe.
- Stitch HTML page templates are active at their named FastAPI routes; direct `/static/stitch/...`
  paths remain blocked. Template charts are hydrated from reports, saved history, or live windows.
- Microphone permissions, AudioWorklet capture, system/tab audio, demo playback, narrow viewport
  behavior, and backend-down UI behavior have NOT been manually verified in a browser. Automated
  browser dependency installation was rejected by the environment approval reviewer; see the
  work log. API/WebSocket integration coverage does not prove browser device capture.
- Existing detector performance is weak on the held-out primary test and degrades
  under robustness conditions; live audio differs from training data.
- `scripts\stream_eval.py` replays the legacy FoR stream pipeline, reports measured
  window/file metrics, inference latency, and alert counts. It does not read or
  write `results/`.
- R4 validation subset (250 files/class from the existing `for-2sec` validation
  manifest): 500 files, window/file accuracy 0.988, FPR 0.012, FNR 0.012; median
  window latency 4.2232 ms and p95 6.5219 ms. These are validation-subset results,
  not test metrics. The fixed 2-second clips produce one window each, so none can
  reach the three-window alert rule.
- A separate behavior replay on 20/class `for-norm-clean` validation files with
  duration >=4 seconds produced 18 alerts on fake files and 0 on real files. It
  is an alternate normalized variant and is not independent evaluation evidence.
- The locked demo holdout is ASVspoof, while the live stream contract is the
  windowed FoR model. Demo streaming metrics were not run to avoid reporting an
  invalid cross-dataset result.
- Focused stream unit test and WebSocket integration test passed. The WebSocket
  integration test needed to run outside the sandbox because its local socket pair
  could not be created inside the sandbox.
- Separate locked demo holdout evaluation (ASVspoof complete-clip model, 50 files):
  accuracy 0.88, ROC-AUC 0.9536, FPR 0, FNR 0.24; threshold remained the saved
  validation-EER value `0.8323956492443629`. This is demo evidence, not test-set
  performance, and it does not validate WebSocket streaming on ASVspoof.

## R7 Whole-site UI and flow audit — 2026-10-19

Reused the seven supplied Stitch views and real FastAPI data sources. Corrected model/evaluation
copy to reflect the selected detector's threshold, metrics, and input-duration contract; removed
unsupported compliance/engine claims; made Settings descriptions and VAD preset behavior match
saved values; surfaced settings request failures in-page; and wrapped Call Monitor source buttons
at narrow widths to eliminate horizontal overflow. No data, splits, models, or results changed.

- Full suite: `34 passed, 2 warnings in 146.15s`; warnings are librosa `n_fft=1024` larger than
  short test signals (1000 and 500 samples).
- Latest-source Python and JavaScript syntax checks completed successfully. No-mock scan output:
  `No mock data patterns found in 26 active application files.`
- Edge route sweep: all seven routes rendered at 1280, 768, and 375 px without JS exceptions.
  Call Monitor overflow at 375 px was fixed; targeted measurement after the fix:
  `innerWidth=375, rootWidth=375, scrollWidth=375`.
- Isolated Edge fake-audio integration exercised both pages through AudioWorklet, WebSocket
  inference, stop, and persisted session detail. Live Check produced 19 windows and saved session
  #1 on a known synthetic validation clip. Call Monitor produced 2 windows and saved session #2
  (`duration=3.841875`, verdict `Likely Synthetic`). This validates the browser pipeline with test
  audio, not physical microphone accuracy.
- Settings browser flow intercepted `PUT /api/settings` to avoid persistent user-setting changes;
  save and VAD preset behavior were observed. Error-toast behavior was not conclusively observed.
- Model & Evaluation was inspected with the ASVspoof complete-clip profile and report-derived
  metrics. Existing held-out FoR metrics remain weak: accuracy 0.5542, ROC-AUC 0.7349, EER 0.3272,
  FNR 0.8235.
- The 2026-10-20 restart used `scripts/run_app.py`; read-only HTTP checks returned 200 for the app
  routes and `/api/health` reported `model_loaded=true`, `classical_for_2sec`, and both profiles
  available. Active runtime asset is `stitch-runtime.js?v=20261020-r8mobile2`.

Remaining NOT VERIFIED: physical mic permission/capture and real speech scoring, system/tab audio,
demo replay completion, Settings error toast, offline operation (external CDN dependencies), and
API-down UI behavior. No phone-network integration is claimed.

## R8 Hardening — 2026-10-20 (in progress)

Added a separate `/login` page with sign-in/sign-up switching, backend account endpoints, PBKDF2
password hashing with random salts, opaque HttpOnly sessions, logout, and a collapsible user popover
on existing screens. Theme controls use accessible sun/moon SVG icons with descriptive labels; the
preference persists per browser. Theme assets are versioned to bypass stale caches and `/login` is
non-cacheable. Stitch page templates and graph are unchanged; runtime has mobile-only layout updates. Session cookies are
Secure when `VERCEL=1` or `VOICEGUARD_COOKIE_SECURE=1` is set.
Account sessions label a browser user but do not protect or isolate existing analysis/history
endpoints; the login page discloses this. User rows persist in `data/voiceguard.sqlite3`; a signed-in
cookie persists for 30 days unless the user signs out.

R8 hardening fixes: upload bodies are read in bounded chunks and stop at 10 MB + 1 byte before
temporary-file creation. Mobile layout stacks grid columns, wraps controls, prevents horizontal
overflow, and keeps the account icon visible. A shared SVG favicon handles both linked and default
favicon requests. Runtime JS uses a fresh cache-busting version.

Live start-control follow-up (2026-10-20): the in-app browser was pointing at a stopped local server;
`scripts/run_app.py` is now serving on 127.0.0.1:8000 (PID 1588). Removed the stale Call Monitor
inline handler that asked to terminate a fabricated session #4092 and could override the real
start/stop action. Call Monitor now starts in READY, switches to LIVE only after the WebSocket opens,
and returns to READY on cleanup. Both live pages show what capture is starting and whether a browser
microphone prompt needs attention. Runtime cache tag is `20261020-r8livefix2`; supplied page templates
and graph structure are otherwise retained. Headless Edge loaded both pages and fetched the worklet
and settings; its scripted click did not have trusted browser activation to grant microphone access,
so actual device permission/capture remains NOT VERIFIED by that check. The server log showed no
WebSocket attempt from that blocked permission flow. A final headless Edge DOM check reported both
consent checkboxes enabled, both expected start labels, runtime cache tag `20261020-r8livefix2`,
Call Monitor badge `Ready`, no legacy fake-stop text, local `.hidden` CSS active, and the static
consent showcase card computed as `display:none`. It did not grant mic permission or send audio.

Auth/deploy V1: `docs/AUTH_DEPLOY_PLAN.md` records the reconnaissance and V1 gate evidence. SQLAlchemy
Core and Alembic are installed and active. Revision `20261020_0001` adds owner-ready columns and
`login_attempts`/`ws_tickets`; `DATABASE_URL` supports local SQLite or a PostgreSQL URL. The verified
pre-migration backup is `data/backups/voiceguard-pre-v1-20261020.sqlite3` (49,152 bytes; integrity
`ok`; counts matched). The first live migration cascaded away 15 window rows during SQLite's parent
table rebuild; I restored all 15 rows from that backup, verified foreign keys, and corrected the
migration to preserve child rows. A fresh copy rehearsal then retained 2 analyses, 15 windows, and 6
settings. The live DB currently has 0 users; legacy analyses and settings remain `user_id=NULL`.
Existing user-facing auth is still PBKDF2/username based and public data endpoints remain unscoped;
V2/V3 are required before this is production authentication.
Selected installed runtime package directories total 351,951,585 bytes; the complete Vercel bundle has
not been built or measured. Current model tree is 28,008,659 bytes and is ignored by Git. Vercel-only
live-stream deployment is NOT VERIFIED; test Python FastAPI WebSockets in a preview before choosing.

Commands and outputs:

```text
node --check app\static\account-menu.js                         # exit 0 (R8 recheck)
node --check app\static\auth-page.js                             # exit 0 (R8 recheck)
.venv\Scripts\python.exe -m py_compile app\main.py app\core\auth.py app\db\database.py  # exit 0
.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 31 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
git diff --check                                               # exit 0
$env:VERCEL='1'; direct _issue_login cookie check
vercel_secure_cookie= True

Headless Edge browser audit:
login 375/768/1280: viewportWidth=documentWidth=bodyWidth; overflow=false
call-monitor 375/768/1280: viewportWidth=documentWidth=bodyWidth; overflow=false; account icon visible
theme: darkTheme=dark; aria-label="Switch to light mode"; lightTheme=light
signupRedirect=true; signupAuthenticated=true; logoutAvailable=true; logoutAuthenticated=false

HTTP upload 10 MB + 1 byte -> 413: {"detail":"Upload exceeds the 10 MB limit"}
HTTP /, /login, /dashboard, /call-monitor, /favicon.ico, /api/health -> 200
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-r8-final
..................................                                       [100%]
34 passed, 2 warnings in 110.60s (0:01:50)
node --check app\static\stitch-runtime.js; node --check app\static\account-menu.js; node --check app\static\auth-page.js
all three exit 0
.venv\Scripts\python.exe scripts\run_app.py
INFO:     Started server process [7056]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
HTTP /, /login, /dashboard, /call-monitor, /favicon.ico, /api/health -> 200
health: model_loaded=true; model_version=classical_for_2sec; both profiles=true

node --check app\static\account-menu.js                         # exit 0
node --check app\static\auth-page.js                            # exit 0
node --check app\static\stitch-runtime.js                        # exit 0
.venv\Scripts\python.exe -m py_compile app\main.py app\core\auth.py app\db\database.py  # exit 0
.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 31 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
.venv\Scripts\python.exe -c "import json,urllib.request; b=urllib.request.urlopen('http://127.0.0.1:8000/dashboard').read().decode(); print('dashboard_status=200 account_css=', '/static/account-menu.css' in b, 'account_js=', '/static/account-menu.js' in b); q=urllib.request.urlopen('http://127.0.0.1:8000/login'); print('login_status=',q.status,'auth_form=',b'vg-auth-form' in q.read()); m=urllib.request.urlopen('http://127.0.0.1:8000/api/auth/me'); print('me_status=',m.status,'me=',m.read().decode()); o=json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')); print('auth_routes=',[x for x in o['paths'] if x.startswith('/api/auth/')])"
dashboard_status=200 account_css= True account_js= True
login_status= 200 auth_form= True
me_status= 200 {"authenticated":false,"user":null}
auth_routes= ['/api/auth/signup', '/api/auth/login', '/api/auth/me', '/api/auth/logout']
```

## Auth/Deploy V2–V3 — 2026-10-20

Reused the SQLAlchemy/Alembic storage layer and existing auth UI/API. New passwords use Argon2id;
legacy PBKDF2 credentials upgrade after successful login. Added generic sign-in errors, common
password checks, database-backed login/signup throttling, JSON/same-origin checks, seven-day
HttpOnly sessions, password change, account export/deletion, and single-use 60-second WebSocket
tickets. `/ws/live` now requires a ticket before receiving audio; the existing browser stream flow
requests a ticket and waits for server authorization before sending audio.

Protected model details/metrics, upload, demo, dashboard, history/export/detail/clear, and settings
APIs with session authentication and user-scoped records. Legacy ownerless records remain inaccessible
to accounts. Upload/demo/live thresholds and live-session writes use the signed-in account. Two-user
coverage asserts history/dashboard/export isolation, 404 for guessed foreign analysis IDs, scoped
settings/clear, and rejection of mismatched/reused/invalid WS tickets. Existing Stitch page templates
and graph DOM were not edited.

```text
.venv\\Scripts\\python.exe -m pytest -q -s --basetemp .pytest-tmp-v3-accept tests\\test_auth.py tests\\test_api.py tests\\test_authorization.py
21 passed in 12.34s

.venv\\Scripts\\python.exe -m pytest -q --basetemp .pytest-tmp-v3-full
44 passed, 2 warnings in 88.24s
Warnings: librosa n_fft=1024 exceeds test input lengths 1000 and 500 samples.

node --check app\\static\\stitch-runtime.js; node --check app\\static\\auth-page.js; node --check app\\static\\account-menu.js
all exit 0
.venv\\Scripts\\python.exe -m py_compile app\\main.py app\\core\\auth.py app\\db\\crud.py
exit 0
.venv\\Scripts\\python.exe scripts\\scan_no_mock.py
No mock data patterns found in 32 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
git diff --check
exit 0
```

NOT VERIFIED: hosted PostgreSQL, email verification/reset, Vercel bundle/model deployment, Python
WebSocket preview compatibility, physical microphone/device capture, and production secrets. The
browser account flow and route guards were exercised in V4 below.

Live restart and smoke output:

```text
.venv\Scripts\python.exe scripts\run_app.py
INFO: Started server process [8336]
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000

HTTP /api/health 200
HTTP /login 200
HTTP /dashboard 200
HTTP /call-monitor 200
HTTP /static/stitch-runtime.js 200
HTTP /api/history unauthenticated 401 {"detail":"Sign in to continue."}
Listener: 127.0.0.1:8000, PID 8336
```

Live HTTP account flow used a generated, disposable local test account and removed it afterward:

```text
HTTP signup=201; duplicate=409; login=200; wrong_password=401; HttpOnly_cookie=yes;
/me authenticated=yes; logout=cleared; password_plaintext=not_stored; disposable_account=removed
```

The earlier full-suite run had Windows temporary-directory failures; the R8/V1 final run used a writable
repository temp path and passed all 34 tests, with two existing short-signal librosa warnings. Offline
operation is NOT VERIFIED because active Stitch pages load Tailwind, fonts, and some logo assets remotely. Physical
microphone permissions, real-speech scoring, system/tab audio, and completed demo replay remain
device-dependent.

Vercel deployment is NOT READY: SQLite on a function filesystem is not durable. A hosted persistent
SQL database and storage configuration are required. V2/V3 now isolate new account-owned
analysis/history/settings; legacy ownerless records remain hidden from accounts.

## Next phase

R7/R8 and Auth/Deploy V1–V3 local gates are complete. V4 browser account flow, route guards, and
account controls are next. Vercel deployment needs hosted persistent SQL, measured bundle size, and a
preview WebSocket spike. Offline packaging and real device/source acceptance remain pending. Model
retraining and new result generation were not part of this work; existing artifacts and evidence were
preserved.

## Handoff

Read `docs\WORK_LOG.md` and `docs\WIRING_MATRIX.md` first. Use
`.\.venv\Scripts\python.exe` for project commands. The local site is started with
`.\.venv\Scripts\python.exe scripts\run_app.py` and is currently serving on port 8000.

## R6 Live Check and Call Monitor repair — 2026-10-19

Reused the existing FastAPI WebSocket, `StreamSession`, FoR detector, AudioWorklet, Stitch page
shells, and measured score graph. Changed the streaming window contract to include the configured
threshold and uncertainty band; corrected the browser worklet message to carry PCM16 frames plus
measured RMS level; wired the live input meter and VAD text to those frames/windows; moved consent,
status, and results into a full-width panel before the existing graph; reset per-session state so a
second run can be stopped; escaped backend text before rendering; and made capture errors identify
the selected source. Existing detector/session constructors receive saved threshold, uncertain band,
hop, VAD gate, smoothing, and alert-window settings. No models, datasets, manifests, or results were
changed.

Verification commands and output:

```text
node --check app\static\stitch-runtime.js
node --check app\static\audio-worklet.js
.\.venv\Scripts\python.exe -m py_compile app\main.py app\core\streaming.py
.\.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 26 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-live-final tests\test_streaming.py
.                                                                        [100%]
1 passed in 0.59s
.\.venv\Scripts\python.exe -m pytest -q -s --basetemp .pytest-live-ws-final tests\test_api.py::test_live_websocket_returns_window_and_summary
.
1 passed in 7.07s
```

The WebSocket test asserts streamed threshold/band match `/api/settings`. Local app responses:

```text
HTTP 200 /api/health: model_loaded=true, model_version=classical_for_2sec
HTTP 200 /live-check; runtime query stitch-runtime.js?v=20261019-live3
HTTP 200 /call-monitor
HTTP 200 /static/stitch-runtime.js?v=20261019-live3; dynamic-meter=true
```

NOT VERIFIED: physical microphone permissions and real speech scoring in Edge; system/tab audio
sharing; demo replay completion; reconnect after an unexpected socket drop; final post-layout visual
capture (Edge headless stopped producing screenshots); narrow viewport interaction. Existing FoR
held-out test metrics remain weak (accuracy 0.5542, ROC-AUC 0.7349, EER 0.3272, FNR 0.8235). A live
score is an uncalibrated model estimate and can be wrong; uncertain output is expected.

Final combined check after the last source-switch race fix:

```powershell
node --check app\static\stitch-runtime.js; node --check app\static\audio-worklet.js; .\.venv\Scripts\python.exe -m py_compile app\main.py app\core\streaming.py; .\.venv\Scripts\python.exe scripts\scan_no_mock.py; $base=Join-Path $env:TEMP 'voiceguard-live-acceptance'; & '.\.venv\Scripts\python.exe' -m pytest -q -s --basetemp $base tests\test_streaming.py tests\test_api.py::test_live_websocket_returns_window_and_summary
```

```text
No mock data patterns found in 26 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
..                                                                       [100%]
2 passed in 11.80s
```

Final local route check returned HTTP 200 for `/api/health`, `/live-check`, `/call-monitor`,
`/static/audio-worklet.js`, and `/static/stitch-runtime.js?v=20261019-live3`; the port 8000 listener
was PID 8040.

## R6 live UI follow-up — 2026-10-19

Rechecked the Live Check and Call Monitor after the earlier R6 changes. Fixed a duplicate JavaScript
declaration that stopped the runtime, retained the original SVG timelines while clearing stale
sample overlays, removed the Call Monitor RTT placeholder, and made the ready state reflect an
inactive session. Both live pages now place their panels and timeline in a full-width single-column
layout. Consent gates the start button with visible disabled styling; the VAD indicator starts as
`VAD: Waiting`. The waiting screen shows no score before a model window exists. No model, dataset,
split, manifest, or result artifact was changed.

Evidence from the final checks:

```text
node --check app\static\stitch-runtime.js
node --check app\static\audio-worklet.js
.\.venv\Scripts\python.exe -m py_compile app\main.py app\core\detector.py app\core\streaming.py
.\.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 26 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.

$base=Join-Path $env:TEMP 'voiceguard-live-r6-final2'; & '.\.venv\Scripts\python.exe' -m pytest -q -s --basetemp $base tests\test_streaming.py tests\test_api.py::test_live_websocket_returns_window_and_summary
..
2 passed in 13.01s

HTTP 200 runtime=stitch-runtime.js?v=20261019-live9
HTTP 200 {"status":"ok","model_loaded":true,"model_version":"classical_for_2sec","profiles":{"legacy_for2sec":true,"asvspoof_la_balanced2500":true}}
Edge /live-check: consent=true, disabled=true, opacity=0.5, graph=true, VAD=VAD: Waiting, JS exceptions=[]
Edge /call-monitor: consent=true, disabled=true, graph=true, Ready, 3 source buttons, JS exceptions=[]
```

The site was then restarted after the final disabled-button styling change with:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
INFO:     Started server process [12688]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Final Edge check after restart: runtime asset `stitch-runtime.js?v=20261019-live10`, start disabled,
computed opacity `0.5`, consent present, original Live Check graph present, and `VAD: Waiting`.
The local `/api/health` previously returned HTTP 200 with `model_loaded=true` and
`model_version=classical_for_2sec`; the server is held in the active app session.

NOT VERIFIED: physical microphone permissions/input and real spoken-speech detections, system/tab
audio capture, and a completed demo replay were not exercised. Edge only verified the pages in their
idle/waiting state. These checks establish UI and server readiness, not detection accuracy. Existing
held-out FoR results remain weak (accuracy 0.5542, ROC-AUC 0.7349, EER 0.3272, FNR 0.8235); live
scores remain uncalibrated estimates and may be uncertain or wrong.

## Auth/Deploy V4 browser account flow — 2026-10-20

Added an email/display-name signup form, email-or-username sign-in, safe return to the requested
private page after sign-in, and server redirects for all seven private app pages. The account page
now exposes password change, account JSON export, password-confirmed account/data deletion, and
sign-out. Updated the account disclosure to describe per-user data and legacy ownerless records.
Kept all supplied Stitch page templates and graph markup unchanged. Refreshed runtime asset URLs so
the browser gets the current live-auth handshake.

The live SQLite schema has legacy `NOT NULL` constraints on `users.username` and `users.password_salt`.
Email-only signups now receive a generated internal username; Argon2id accounts leave the legacy
separate-salt field empty because the encoded Argon2id hash contains its own salt. Duplicate errors
are reported only for actual unique-key conflicts. A test reproduces these legacy constraints.

```text
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-v4-final
52 passed, 2 warnings in 90.18s
Warnings: librosa n_fft=1024 exceeds test input lengths 1000 and 500 samples.

Edge headless sign-in render:
edge_exit=0
Rendered email-or-username input, signup display-name input, account section, and v4account1 scripts.

Disposable Edge CDP flow:
signup_and_return= /call-monitor
account_panel_visible= True
export_ui= True
password_change= True
delete_redirect= /login
authenticated_after_delete= False
remaining_v4_test_accounts= 0

Focused legacy schema tests after Argon2 salt fix: 2 passed in 3.29s
Focused auth/authorization tests after salt fix: 18 passed in 13.81s
```

Browser verification used an ephemeral randomly named test account and deleted it through the
account UI. The updated local site is serving on `http://127.0.0.1:8000` (listener PID 16644).
External email verification/password reset, hosted PostgreSQL, Vercel packaging and
Python WebSocket preview remain NOT VERIFIED. Next: V5 deployment spike; it requires hosted Postgres
and Vercel preview configuration to verify deployment behavior.

## Auth/Deploy V5 local preflight — 2026-10-20 (in progress)

Added a root `index.py` entrypoint exporting the existing FastAPI app for Vercel. Vercel mode now
fails at import if `DATABASE_URL` is absent instead of silently storing accounts in an ephemeral
SQLite function filesystem. The health response reports degraded/model-unavailable status instead
of crashing when model metadata is absent; profile info endpoints return 503 when their model files
or reports are not present. These paths are needed because `models/`, `results/`, and `data/` remain
excluded from Git by project policy.

Provider `postgresql://` and `postgres://` connection URLs are normalized to the declared psycopg 3
SQLAlchemy driver. MongoDB is not compatible with the current relational schema/migrations.

Hardened `.gitignore` for credentials, local databases, Vercel state, logs/keys, raw data and all
known corpus roots. Before pushing, stage only reviewed source/docs/config files and check staged
names plus secret patterns. The supplied GitHub URL returned no remote refs on read-only inspection;
local Git has no commits and no configured remote.

NOT VERIFIED: Vercel build/bundle size, Postgres connectivity, cold start, inference artifact delivery,
upload payload compatibility (the current 10 MB app limit exceeds Vercel's 4.5 MB request limit),
and Python WebSocket live monitoring. A Vercel deployment still needs hosted Postgres, an approved
private delivery path for model plus matching reports/metadata, and a preview project. Do not deploy
until those inputs are configured and preview checks pass.

Local proof:

```text
.venv\Scripts\python.exe -m py_compile index.py app\main.py app\core\auth.py app\db\database.py
exit 0
.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 32 active application files.
Vercel startup without DATABASE_URL: rejected with the expected persistent-PostgreSQL error.
Missing legacy model metadata: /api/health returned degraded, model_loaded=false.
Database('postgresql://user:pass@localhost/dbname').url.drivername = postgresql+psycopg
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-v5-verified
52 passed, 2 warnings in 99.42s
scripts\run_app.py started latest local source on 127.0.0.1:8000 (Uvicorn PID 15864).
GET /api/health HTTP 200: model_loaded=true, legacy_for2sec=true, asvspoof_la_balanced2500=true.
GET /login HTTP 200. GET /call-monitor returned 303 Location=/login?next=/call-monitor.
```

Two existing warnings are librosa `n_fft=1024` exceeding test signals of 1000 and 500 samples.
The exact staged paths passed the blocked-data path check (125 files; zero matches) and the
high-confidence credential-pattern scan (zero matches). Full staged path output was inspected.

NOT VERIFIED: Vercel build/bundle size, Postgres connectivity, cold start, inference artifact delivery,
upload payload compatibility (the current 10 MB app limit exceeds Vercel's 4.5 MB request limit),
and Python WebSocket live monitoring. A Vercel deployment still needs hosted Postgres, an approved
private delivery path for model plus matching reports/metadata, and a preview project. Do not deploy
until those inputs are configured and preview checks pass.

GitHub status: source-only commit `17f11ce` and state update `aed31fe` were pushed to
`origin/codex/r4-stream-evaluation`. Follow-up inspection found GitHub's default `master` branch
still had only its original one-line README commit `09ad99e`; this is why the repository landing page
looked empty. The feature branch is being integrated into `master` while preserving that original
commit. The reviewed source tree contains 125 source, UI, test, and documentation paths; no local
database, dataset, model weights, or results were included. The blocked-path check found zero
matches; the high-confidence credential scan found zero matches.

Next: after the default-branch update, stop at the V5 hosted-preview gate until the student supplies
Vercel/PostgreSQL configuration and the model artifact delivery choice.
