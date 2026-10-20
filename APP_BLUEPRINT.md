# APP BLUEPRINT — Synthetic Voice Forensics Web App

Single source of truth for the UI (Stitch) and the backend (Copilot). Save as `docs/APP_BLUEPRINT.md`.

## 1. What the app does (and does not)

**Does:** analyzes speech and reports how likely it is to be synthetic (AI-generated/cloned), in three ways:
1. **Upload check** — analyze a saved audio file.
2. **Live check** — analyze the microphone in real time.
3. **Live call monitor** — analyze the audio of an ongoing call, in real time, with a call-level risk reading and alerts.

**Is honest about what it is:** a research prototype that gives an *additional verification signal*, not proof of identity or forgery.

**Does NOT:** connect to the phone network. "Live call monitoring" means analyzing an audio stream available on this computer:
- **Microphone source:** phone call on speaker near the mic, or the user's own mic.
- **System / tab audio source:** audio of a softphone, WhatsApp Web, a meeting tab, etc., captured by the browser (Chrome/Edge screen-share with "share audio"). Browser behavior must be verified on the student's machine.
- **Demo replay source:** a recorded call/audio file pushed through the *same* streaming pipeline, so the demo works reliably even without a real call.
Real telephony integration (SIP/Twilio etc.) is **future work** and must not appear as a working feature.

**Known limitation (must be shown in the Model page and thesis):** the model is trained on a public dataset (Fake-or-Real). Live microphone and call audio is a different condition. Readings can be wrong or "Uncertain". The app must never present a live reading as a guaranteed verdict.

## 2. End-to-end flow

```
Audio source (file / mic / system audio / replay)
        │
        ▼
Browser captures PCM (live) or uploads file (upload)
        │   WebSocket binary frames (live)  |  multipart POST (upload)
        ▼
FastAPI backend
  1. Resample to model rate, mono
  2. Cut into windows (window length = model's training clip length; hop configurable)
  3. Voice-activity gate: skip near-silent windows ("no speech")
  4. Shared preprocessing + feature extraction (SAME code as training)
  5. Model → P(fake) per window
  6. Aggregate: smoothing + call/file-level verdict
  7. Verdict rule: score ≥ high → "Likely synthetic"; ≤ low → "Likely real"; between → "Uncertain"
  8. Save results (scores + metadata) to SQLite; raw audio NOT stored by default
        │
        ▼
UI updates: verdict, probability gauge, timeline, alerts, history, dashboard
```

## 3. Pages (only these; no extra pages, no login, no marketing content)

| # | Page | Purpose | Shows (all from real backend data) |
|---|------|---------|------------------------------------|
| 1 | **Dashboard** | Overview | KPI cards: total analyses, flagged synthetic (count + %), uncertain count, average latency. Recent analyses table. Chart: fake probability across recent analyses. Model status card (loaded?, model name, dataset, threshold). Quick actions. |
| 2 | **Analyze File** | Upload check | Drag-and-drop zone, accepted formats, progress, then result: verdict, probability gauge with threshold and uncertain band, per-window timeline, details (duration, original sample rate, speech ratio, windows analyzed, latency, model version), disclaimer, export JSON. |
| 3 | **Live Check** | Mic check | Start/Stop, input device selector, level meter, rolling probability chart, current + smoothed verdict, status (Listening / No speech / Lagging), window counter; on stop → session summary saved to history. |
| 4 | **Call Monitor** | Live call | Source selector (Microphone / System or tab audio / Demo replay), call timer, call-level risk reading, rolling timeline with flagged segments, alert banner when the alert rule triggers, session summary on end (flagged segments list), export. Label: "Analyzes audio on this device; not connected to a phone network." |
| 5 | **History** | Past work | Table of uploads and sessions; filters (source, verdict, date); detail view with timeline; export CSV. |
| 6 | **Model & Evaluation** | Honest evidence | Model card (type, features, training data, split, window length, threshold). Metrics from `results/` files: accuracy, precision, recall, F1, FPR, FNR, EER, ROC-AUC, confusion matrix. Robustness table (clean vs other conditions). Latency stats. Limitations text. If no results files exist → empty state, never placeholder numbers. |
| 7 | **Settings** | Tuning | Decision threshold (default = validated threshold), uncertain band, smoothing, alert rule (N consecutive flagged windows), silence gate, "store raw audio" toggle (default OFF), clear history. |

Navigation: left sidebar with these 7 items. Header: app name + model status dot.

## 4. Verdict & alert logic (design choices — must be configurable and documented as such)

- Window length = the model's training clip length (e.g. 2 s if trained on FoR-2sec). Hop default 1 s.
- Silence gate: windows whose energy is below a configurable level are marked "no speech" and excluded from scoring.
- Smoothing: exponential moving average of window scores (configurable α).
- Call-level risk: derived from the smoothed score and the fraction of speech windows flagged in a recent span. Display as words ("No concern / Uncertain / Suspected synthetic voice") plus the number.
- Alert: raised when N consecutive speech windows are ≥ threshold (N configurable). Alerts are advisory.
- File-level verdict: aggregate (mean and max reported) over speech windows; verdict from the mean vs threshold/band. Show the timeline so the user can see where it flagged.
- Color is never the only signal: use text + icon (✓ real, ! uncertain, ✕ synthetic).

## 5. Backend stack
- **FastAPI** (Python) + **Uvicorn**; **SQLite** for history; model loaded once at startup.
- Static frontend served by the same app. Frontend = HTML/CSS/vanilla JS (+ Tailwind CDN and Chart.js if the Stitch export uses them). No Node build step.
- Heavy inference runs in a worker thread so the WebSocket loop stays responsive. If processing falls behind the hop rate, drop stale windows and show "Lagging".
- Privacy: no raw audio stored by default; show a consent/privacy notice before live capture and call monitoring.
- Browsers: target Chrome/Edge on `http://localhost` (mic and screen-capture work on localhost).

## 6. API contract (frontend ↔ backend)

- `GET  /api/health` → `{status, model_loaded, model_version}`
- `GET  /api/model/info` → `{name, features, training_dataset, window_s, sample_rate, threshold, uncertain_band, trained_at?}`
- `GET  /api/model/metrics` → contents of available `results/*.json` summaries (or `{available:false}`)
- `POST /api/analyze/upload` (multipart `file`) → `{id, verdict, mean_prob, max_prob, threshold, uncertain_band, duration_s, sample_rate, speech_ratio, windows:[{t_start,t_end,prob,speech}], latency_ms, model_version}`
- `WS   /ws/live` — client first sends JSON `{mode:"mic"|"call", source:"mic"|"system"|"replay", sample_rate:<int>}`, then binary frames of 16-bit mono PCM. Server sends:
  - `{type:"window", t, prob, smoothed, verdict, speech, latency_ms, level}`
  - `{type:"alert", t, message}`
  - `{type:"status", state:"listening"|"no_speech"|"lagging"}`
  - on stop: `{type:"summary", session_id, ...}`
- `GET  /api/dashboard/summary` → `{total, flagged, uncertain, flagged_pct, avg_latency_ms, recent:[...], series:[...]}`
- `GET  /api/history?source=&verdict=&from=&to=` · `GET /api/history/{id}` · `GET /api/history/export.csv`
- `GET/PUT /api/settings`
- `DELETE /api/history` (clear)

## 7. Data tables (SQLite)
`analyses(id, created_at, source, name, duration_s, sample_rate, mean_prob, max_prob, verdict, speech_ratio, latency_ms, model_version, threshold, band)`,
`windows(analysis_id, t_start, t_end, prob, speech)`, `settings(key, value)`.

## 8. Definition of "working" (acceptance checklist)
- [ ] Upload a known real file and a known fake file → verdicts returned, timeline shown, saved to history.
- [ ] Live check shows moving readings from the microphone; stop → summary saved.
- [ ] Call monitor works with all three sources; Demo replay of a fake file triggers the alert rule; replay of a real file does not (report what actually happens).
- [ ] Dashboard numbers equal database counts.
- [ ] Model page shows only numbers that exist in `results/`.
- [ ] `stream_eval` script reports window-level accuracy/latency of the *streaming* pipeline on held-out files.
- [ ] Every page has loading, empty and error states.
