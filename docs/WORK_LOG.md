# Work Log

This file is the durable handoff log for the synthetic voice forensics project.
It records completed phases, exact commands, measured outputs, decisions, and the
next action so work can continue from another IDE without relying on chat history.

## 2026-10-18 — R3 ASVspoof detector contract

### Goal

Add an ASVspoof-specific inference artifact without silently changing the existing
FoR backend detector.

### Files added

- `app/core/asvspoof_detector.py`
- `tests/test_asvspoof_detector.py`

### Design

- Loads only `models/asvspoof_la_svm_balanced2500/model_meta.json`.
- Rejects metadata whose `training_dataset` is not `ASVspoof2019_LA`.
- Loads the joblib model once per detector instance.
- Uses the shared MFCC, delta, delta-delta extraction and summary implementation.
- Scores the complete variable-duration clip because this model was trained on
  complete ASVspoof clips, not fixed 2-second windows.
- Uses the saved validation-EER threshold `0.8323956492443629`.
- Returns `Uncertain` without a model score for silence.
- Does not replace `app/core/detector.py` or the current FastAPI model implicitly.

### Commands and measured outputs

Previous R2 expanded training:

```powershell
Set-Location 'D:\syntheic voice clone'
& '.\.venv\Scripts\python.exe' scripts\train_asvspoof_classical.py --manifest-dir .\data\manifests --model-dir .\models\asvspoof_la_svm_balanced2500 --results .\results\asvspoof_la_svm_balanced2500.json --max-files-per-class 2500 --seed 42
```

Measured test output:

```text
accuracy=0.8808
precision=0.9440298507462687
recall=0.8096
f1=0.8716623600344531
fpr=0.048
fnr=0.1904
roc_auc=0.94184576
eer=0.128
threshold=0.8323956492443629
```

### Next command

```powershell
Set-Location 'D:\syntheic voice clone'
& '.\.venv\Scripts\python.exe' -m pytest -q tests\test_asvspoof_detector.py tests\test_asvspoof_eval_breakdown.py tests\test_no_leakage.py
```

Actual output:

```text
.......                                                                  [100%]
7 passed in 5.49s
```

Artifact smoke command:

```powershell
& '.\.venv\Scripts\python.exe' -c "from app.core.asvspoof_detector import ASVspoofDetector; print(ASVspoofDetector().meta['model_version'])"
```

Actual output:

```text
asvspoof_la_mfcc_svm_balanced2500_seed42
```

### Known limitations

- The selected model is balanced-subset trained (2,500 files per class per split),
  not full natural-distribution trained.
- The official eval protocol has unknown spoof attacks A07-A19 only; known spoof
  attack metrics are undefined.
- Existing FastAPI endpoints still use the older FoR detector until an explicit
  backend model-selection change is made.
- No full ASVspoof CNN run has been performed.

## 2026-10-18 — Explicit backend model profiles

### Decision

Expose the ASVspoof detector as `asvspoof_la_balanced2500` while retaining
`legacy_for2sec` as the default. This avoids silently changing existing behavior
and makes every analysis record its selected model version.

### API contract

- `GET /api/model/info` defaults to `legacy_for2sec`.
- `GET /api/model/info?profile=asvspoof_la_balanced2500` returns the ASVspoof
  artifact contract and balanced-subset split sizes.
- `POST /api/analyze/upload?profile=asvspoof_la_balanced2500` analyzes with the
  ASVspoof detector and persists its model version in SQLite.
- Unknown profiles return HTTP 400.
- Live WebSocket remains on the legacy fixed-window detector; ASVspoof streaming
  is not enabled because its trained contract is complete variable-duration clips.

### Files changed

- `app/main.py`
- `tests/test_api.py`

### Verification command and output

```powershell
Set-Location 'D:\syntheic voice clone'
& '.\.venv\Scripts\python.exe' -m pytest -q tests\test_api.py tests\test_asvspoof_detector.py
```

```text
........                                                                 [100%]
8 passed in 9.29s
```

## 2026-10-18 — Demo holdout API

### Decision

Expose the locked `demo_holdout` through REST without leaking labels in the
listing. Each listed ID is the manifest SHA-1; the ground truth is returned only
after the corresponding demo file is analyzed.

### API contract

- `GET /api/demo/samples` returns only `id`, `name`, and `duration_s`.
- `POST /api/demo/analyze/{sha1}` reads only a row in the locked demo manifest,
  analyzes with `asvspoof_la_balanced2500`, stores the result as source `Demo`,
  and returns `ground_truth_label`, `ground_truth`, `attack_id`, and the analysis.
- Missing manifest/files are explicit 503 errors; unknown IDs are 404.

### Verification

```powershell
Set-Location 'D:\syntheic voice clone'
& '.\.venv\Scripts\python.exe' -m pytest -q tests\test_api.py tests\test_asvspoof_detector.py
```

```text
.........                                                                [100%]
9 passed in 4.54s
```

## 2026-10-18 — R4 streaming replay and summary correctness

### Changes

- Added `scripts\stream_eval.py` to feed manifest audio in PCM-sized chunks through
  the same `StreamSession` path used by `/ws/live`. It reports window/file metrics,
  measured inference latency, and alert counts without writing to `results/`.
- Added per-window inference latency and total received-sample duration to stream
  summaries. The previous duration calculation counted hop advancement and
  underreported sessions with overlapping windows or an incomplete final hop.
- Added a focused unit test for stream duration, latency fields, and alert firing.

### Commands and measured outputs

```powershell
& '.\.venv\Scripts\python.exe' -m py_compile scripts\stream_eval.py app\core\streaming.py app\main.py tests\test_streaming.py
& '.\.venv\Scripts\python.exe' -m pytest -q -s --basetemp .pytest-streaming-test tests\test_streaming.py
```

```text
.
1 passed in 0.24s
```

```powershell
& '.\.venv\Scripts\python.exe' scripts\stream_eval.py --max-files-per-class 250
```

```text
files_requested=500; files_scored=500
window/file accuracy=0.988; FPR=0.012; FNR=0.012
window latency median=3.7632 ms; p95=5.3284 ms
alerted_files_by_ground_truth={"real": 0, "fake": 0}
separate ASVspoof demo_holdout: 50/50 files scored; accuracy=0.88;
ROC-AUC=0.9536; FPR=0; FNR=0.24; median latency=4.0992 ms
```

The `for-2sec` validation samples are exactly two seconds, so each yields one
window and cannot reach the three-window alert rule. An additional behavior replay
used 20/class `for-norm-clean` validation files at least four seconds long. It
reported 18 fake alerts and 0 real alerts; this alternate normalized variant is
not independent evaluation evidence.

The locked demo holdout belongs to ASVspoof, while the live WebSocket supports only
the FoR windowed model. The demo was evaluated separately with its matching
ASVspoof complete-clip model; it is not a WebSocket streaming result.

## 2026-10-18 — R5–R9 application wiring and site startup

### Changes

- Replaced the active served Stitch prototype with the API-backed seven-view frontend. Pages cover
  dashboard, upload analysis, live check, call monitor, history, model/evaluation, and settings.
- Bound profile thresholds to saved per-profile settings, wired model reports and history to API
  responses, and removed the nonfunctional raw-audio retention setting. Raw audio is not stored.
- Connected microphone, system/tab, and locked demo sources through AudioWorklet PCM16 to the live
  WebSocket. Demo ground truth is returned only after complete-clip analysis; it is labeled
  separately from the cross-dataset FoR stream reading.
- Added a page/API wiring matrix and replaced the obsolete README Streamlit launch instructions.
- Added a scanner for the active served application. Archived Stitch files are preserved and the
  app's static route blocks them; the scanner reports this explicit scope.

### Commands and outputs

Full suite (including socket integration, run outside the restricted sandbox):

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q --basetemp .pytest-all-2 tests
```

```text
34 passed, 2 warnings in 7.73s
```

The two warnings are librosa's `n_fft=1024 is too large for input signal` on short test arrays.
JavaScript syntax checks passed with no output:

```powershell
node --check app/static/app.js
node --check app/static/api.js
node --check app/static/state.js
node --check app/static/render.js
node --check app/static/audio-worklet.js
```

No-mock scan:

```powershell
& '.\.venv\Scripts\python.exe' scripts\scan_no_mock.py
```

```text
No mock data patterns found in 18 active application files.
Archived Stitch exports are not served; the static route returns 404 for them.
```

Start site:

```powershell
& '.\.venv\Scripts\python.exe' scripts\run_app.py
```

```text
INFO:     Started server process [9536]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

HTTP check:

```powershell
$r = Invoke-WebRequest -Uri http://127.0.0.1:8000/ -UseBasicParsing -TimeoutSec 10
"HTTP $($r.StatusCode) $($r.Headers['Content-Type'])"
$h = Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing -TimeoutSec 10
"HEALTH HTTP $($h.StatusCode) $($h.Content)"
```

```text
HTTP 200 text/html; charset=utf-8
HEALTH HTTP 200 {"status":"ok","model_loaded":true,"model_version":"classical_for_2sec","profiles":{"legacy_for2sec":true,"asvspoof_la_balanced2500":true}}
```

### Gate status and remaining verification

Backend/API, deterministic upload/history, database-backed dashboard, settings, profile metadata,
and WebSocket summary behavior are covered by the passing tests. The app is serving locally.
Real browser interactions for microphone/system-tab capture, demo playback, responsive layout, and
backend-down states remain NOT VERIFIED. Playwright was not installed: the automatic approval
reviewer rejected the proposed commands `\.venv\Scripts\python.exe -m pip install playwright` and
`\.venv\Scripts\python.exe -m playwright install chromium` because they would modify the venv and
download a third-party browser dependency without approval. The attempted existing Edge headless
launch returned no DOM or screenshot output, so it is not browser verification. Manual checklist:
`docs\WIRING_MATRIX.md`.

All existing models, datasets, splits, and results were preserved. No model training, data
generation, or package installation was performed.

## 2026-10-18 — Restore supplied page design and stream live microphone windows

The student clarified that the supplied UI and its graph layout must remain recognizable while
values come from the real application. The earlier minimal SPA became a replacement visual design;
the original seven page templates are now active again at `/dashboard`, `/analyze-file`, `/live-check`,
`/call-monitor`, `/history`, `/model-and-evaluation`, and `/settings`. The root redirects to the
dashboard. The API-backed frontend hydrates dashboards, history, model reports, settings, upload
timelines, and live graph windows. Static page values stay hidden until API hydration succeeds; API
failure displays an explicit backend-unavailable state.

Live Check captures microphone audio with the existing AudioWorklet PCM16 stream and scores speech
using the saved FoR model. A score appears after the first complete 2-second window, then advances
on the model's configured hop. Call Monitor can use the microphone, shared tab/system audio, or a
locked local demo replay. Demo ground truth is fetched only after replay and shown separately from
the cross-dataset FoR window scores. It does not connect to a phone network. Settings persist the
selected profile's threshold, uncertain band, VAD, smoothing, and alert count. Unsupported template
controls were removed or connected to real API actions.

Verification:

```powershell
node --check app/static/stitch-runtime.js
& '.\.venv\Scripts\python.exe' -m py_compile app/main.py
& '.\.venv\Scripts\python.exe' scripts\scan_no_mock.py
& '.\.venv\Scripts\python.exe' -m pytest -q --basetemp .pytest-restored-ui tests
```

```text
No mock data patterns found in 26 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
34 passed, 2 warnings in 50.95s
```

Server restart and HTTP verification after restoring these routes:

```text
HTTP 200 /
HTTP 200 /dashboard
DASHBOARD HAS SUPPLIED DESIGN: True
DASHBOARD LOADS RUNTIME: True
HTTP 200 /live-check
LIVE PAGE HAS WINDOW GRAPH: True
HTTP 200 /call-monitor
HTTP 200 /static/stitch-runtime.js
HTTP 200 /static/audio-worklet.js
HTTP 200 /api/health
```

Edge launch returned a visible window handle and title `127.0.0.1:8000/dashboard - Personal -
Microsoft Edge`. Browser microphone permission, live speech scoring, and shared-tab capture remain
NOT VERIFIED by manual interaction. Model predictions remain estimates; the FoR held-out test report
is weak and has a high false-negative rate, so live results may be wrong or uncertain.

Final post-edit checks:

```powershell
node --check app/static/stitch-runtime.js
node --check app/static/audio-worklet.js
& '.\.venv\Scripts\python.exe' -m py_compile app/main.py
& '.\.venv\Scripts\python.exe' scripts\scan_no_mock.py
& '.\.venv\Scripts\python.exe' -m pytest -q --basetemp .pytest-route-final-2 tests/test_api.py::test_frontend_and_profile_metrics_are_real_routes
```

```text
No mock data patterns found in 26 active application files.
Stitch design templates are served on page routes; direct static template URLs remain blocked.
1 passed in 2.93s
```

### Verification

- WebSocket integration check:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q -s --basetemp .pytest-ws-elevated tests\test_api.py::test_live_websocket_returns_window_and_summary
```

Running inside the sandbox stalled before application code in Starlette's local
socket-pair setup. The same integration check outside the sandbox returned:

```text
.
1 passed in 3.31s
```

Focused R4 test set, also run outside the sandbox:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q --basetemp .pytest-r4-elevated tests\test_api.py tests\test_detector.py tests\test_streaming.py
```

```text
..........                                                               [100%]
10 passed in 3.73s
```

R4 phase gate passed for FoR streaming plus separate ASVspoof demo-clip evidence.
