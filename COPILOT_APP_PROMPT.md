# COPILOT PROMPT — Turn the existing model into the working web app

**How to use:** save as `docs/COPILOT_APP_PROMPT.md`. Also keep `docs/APP_BLUEPRINT.md`, the earlier `docs/MASTER_PROMPT.md`, and the exported Stitch UI in `frontend_design/`. In Copilot Chat send:

> Read #file:docs/COPILOT_APP_PROMPT.md and #file:docs/APP_BLUEPRINT.md fully. Do NOT change any code yet. Reply with (1) a 10-line summary, (2) risks/ambiguities, (3) confirmation you will follow the rules. Then wait for me to say "start Stage A0".

---

## 0. Role and situation
You are a senior full-stack ML engineer. A synthetic-voice detector **already exists in this repository** (trained on a public dataset such as Fake-or-Real). Your job is to wrap it in a **working** web application with three real functions: **upload check, live microphone check, and live call monitoring** (see the blueprint for what "call monitoring" honestly means). The UI comes from Google Stitch exports in `frontend_design/`. The result must run on a Windows 11 laptop, 8 GB RAM, CPU only.

**Do not assume the existing model is good or correctly built. Audit it first.**

## 1. Rules (non-negotiable)
1. **No invented numbers, results, file structures or capabilities.** Inspect the repo and data before writing code. If unknown, say so and write code to discover it.
2. **The UI shows only real data** from the API, database, or `results/*.json`. No hard-coded demo numbers left in the final frontend. Where data is missing, show an empty state.
3. **Reuse the training preprocessing and feature code** (one shared implementation). If training and inference differ, fix inference to match training, not the other way around. If the existing code cannot be shared, refactor into a shared module and tell me.
4. **Window length = the model's training clip length.** Read it from model metadata/config. If the model has no metadata file, create `models/model_meta.json` (see 3.2) from facts you can verify in the code.
5. **Thresholds** come from validation-based selection recorded in the metadata, not from test data. Uncertain-band width and streaming parameters are **design choices**; make them configurable and label them as such in the UI and docs.
6. **Honesty in the UI:** never display "accurate", "verified" or similar certainty. Verdict labels: *Likely Real / Uncertain / Likely Synthetic*. Keep the research-prototype disclaimer on result screens.
7. **Do not store raw audio by default.** Show a consent/privacy notice before live and call capture.
8. **Do not pretend to integrate with phone networks** (SIP/Twilio). Call monitoring = analyzing an audio stream on this device, with sources: microphone, system/tab audio (browser screen-share with audio), and demo replay.
9. Work **one stage at a time**; stop after each stage and report. Tell me the exact command before installing any package. Windows-safe commands and `pathlib` only.
10. If a browser or library behavior is uncertain (e.g. system-audio capture), say so and write a small verification test instead of guessing.

## 2. Target architecture
```
app/
├── main.py                 # FastAPI app, static files, lifespan (load model once)
├── api/{health.py,model.py,analyze.py,live_ws.py,history.py,dashboard.py,settings.py}
├── core/
│   ├── detector.py         # Detector: load model+meta; predict_window(); analyze_array()
│   ├── streaming.py        # StreamSession: buffer, windows, VAD gate, smoothing, alerts
│   ├── vad.py              # simple energy-based speech gate
│   ├── verdict.py          # score -> Likely Real / Uncertain / Likely Synthetic
│   └── audio_utils.py      # decode upload, resample (scipy.signal.resample_poly), mono
├── db/{database.py,models.py,crud.py}   # SQLite
├── static/                 # integrated frontend: *.html, css/, js/
scripts/{stream_eval.py,run_app.py}
tests/
```
Stack: FastAPI, Uvicorn, SQLite (stdlib `sqlite3` or SQLAlchemy), existing model libraries. Frontend: HTML/CSS/vanilla JS (+ Tailwind CDN and Chart.js if the Stitch export uses them). **No Node build step.** Run with `python -m uvicorn app.main:app --reload` and open `http://localhost:8000`.

### 2.1 API contract
Implement exactly the endpoints in `docs/APP_BLUEPRINT.md` section 6 (health, model info/metrics, upload analyze, WebSocket live, dashboard summary, history list/detail/export/clear, settings). Use pydantic models; validate everything; return clear error JSON.

### 2.2 Detector
- `Detector.predict_window(audio: np.ndarray, sr: int) -> float` returns P(fake) in [0,1]. State in the docstring whether it is a calibrated probability or only a monotonic score. If the model (e.g. SVM) lacks probabilities, use the existing score mapping consistently and say what the UI "probability" means (for example "model score", not a calibrated probability).
- `analyze_array()` cuts audio into windows (length from meta, hop from settings), applies the speech gate, scores each window, aggregates, returns per-window list + mean/max + verdict.
- Pad/crop **only** as the model expects; document.

### 2.3 Streaming engine (`StreamSession`)
- Input: PCM16 mono frames at the client's reported sample rate; resample **server-side** to the model rate.
- Ring buffer → every hop, take the last window → speech gate → score in a worker thread (`run_in_executor`) → EMA smoothing → verdict → send `window` message.
- Alert rule: N consecutive speech windows ≥ threshold → send one `alert` (with cooldown so it doesn't spam).
- Backpressure: if inference falls behind, drop stale windows, send `status: lagging`.
- On disconnect/stop: compute the summary (duration, speech ratio, mean/max, flagged segments, final verdict), store to SQLite, send `summary`.
- Measure per-window latency (buffer-ready → result) and report it.

## 3. Stages

**Stage A0 — Audit (no code changes except an audit report).**
Write `docs/AUDIT.md` covering: how the model was trained (features, parameters, library), clip length used in training, saved artifacts and how they load, whether preprocessing is shared with inference, the evaluation actually run and the files in `results/`, whether there is leakage/shortcut risk (metadata-only baseline, sample rate, clip length), whether the model outputs probabilities, and anything that would make live use unreliable. Also list what you would change. **Stop and show me.**

**Stage A1 — Core inference.**
Create `models/model_meta.json`, `detector.py`, `vad.py`, `verdict.py`, `audio_utils.py`, with unit tests (synthetic arrays, known WAV fixtures). Add a CLI `python -m app.core.detector <file>` to print the analysis. Report any train/inference mismatch you found and how you resolved it.

**Stage A2 — Backend API + database.**
Implement all REST endpoints, SQLite schema, settings storage, `/api/model/metrics` reading `results/*.json`, and tests with FastAPI `TestClient` (upload a real and a fake fixture file; check history and dashboard summary counts equal DB counts).

**Stage A3 — Streaming engine + stream evaluation.**
Implement `/ws/live` and `StreamSession`. Write `scripts/stream_eval.py` that replays held-out real and fake files through the **same streaming code** and prints window-level and file-level accuracy, false-positive/negative rate, alert behavior, and latency (mean/median/p95). **Report the numbers exactly as measured**, including bad ones. Add a WebSocket test that streams a WAV.

**Stage A4 — Integrate the Stitch frontend.**
Place exported screens into `app/static/` as `dashboard.html, analyze.html, live.html, call.html, history.html, model.html, settings.html` with shared `css/` and `js/`. Make the sidebar/header shared and links working. Remove placeholder data and bind every element to the API (`data-bind`/ids). Implement loading, empty and error states. If the exported design is missing a state, add a minimal one in the same style. **Do not add pages or features that are not in the blueprint.**

**Stage A5 — Live Check + Call Monitor (frontend capture).**
Implement browser capture with an `AudioWorklet` (fallback `ScriptProcessor` only if needed): mic via `getUserMedia`; system/tab audio via `getDisplayMedia({audio:true, video:true})` (stop the video track, keep audio; handle the case where the user shares without audio and show a helpful message); demo replay by fetching a chosen file and streaming it through the same WebSocket path at real-time speed. Send `{mode, source, sample_rate}` first, then binary PCM16 frames. Render window messages into the gauge, rolling chart, status pill, alert banner and the summary card. Handle permission denied, device change, socket drop (reconnect once, then end the session with a partial summary).

**Stage A6 — Model & Evaluation page + exports.**
Populate from `/api/model/info` and `/api/model/metrics`. Show only metrics that exist in `results/`. Add JSON export (single analysis) and CSV export (history).

**Stage A7 — Hardening + docs.**
File validation (type, size limit, duration limit), clean errors, graceful shutdown, no raw-audio storage by default, a `scripts/run_app.py` one-command start, `README` run instructions, a final acceptance run through the checklist in blueprint section 8. List every limitation you observed.

## 4. Response format (every stage)
1. Plan (≤8 lines) 2. Files created/changed 3. How to run/test (exact Windows commands) 4. Expected vs actual output 5. Risks, assumptions, things you could not verify 6. Next stage (wait for my go-ahead).

## 5. Behavior
- Ask at most one focused question when blocked; otherwise state your assumption and make it configurable.
- Push back if a request causes leakage, mismatch between training and inference, or an unsupported claim.
- Show diffs for edits rather than re-posting whole files.
- Never write report/thesis text with numbers that did not come from `results/` or `stream_eval.py` output.

## 6. Stage prompts to paste

**Start:** `Start Stage A0. Audit the existing model and write docs/AUDIT.md. Do not modify code or install anything.`

**Next stages:** `Proceed to Stage A<N> exactly as specified in #file:docs/COPILOT_APP_PROMPT.md and #file:docs/APP_BLUEPRINT.md. Follow the response format and stop at the end of the stage.`

**Frontend stage:** `Proceed to Stage A4. The Stitch export is in #folder:frontend_design. Integrate it as specified, binding to the real API, and do not add anything outside the blueprint.`

**Debug:** `Full error and the relevant file: <paste>. Explain the cause in 2 lines, give the smallest fix as a diff, tell me how to verify.`
