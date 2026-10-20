# R0 Diagnosis and D0 ASVspoof Pre-flight

## Scope

This diagnosis inspects the repository without downloading data, installing packages, or
changing application behavior. The D0 pre-flight created `data/raw/`; the existing
`data/manifests/` and `data/features/` directories were preserved. The project-local
interpreter is `.venv\Scripts\python.exe` (Python 3.14.3). The bare `python` command is
not configured and resolves to the Microsoft Store alias.

## Repository state

The repository contains:

- A primary `for-2sec` WAV corpus with 17,870 files, balanced real/fake labels, and
  training/validation/testing directories.
- Separate `for-norm` and `for-rerec` corpora and their audit/manifests.
- A copied ASVspoof 2019 Logical Access tree under `LA\LA\`.
- Cached MFCC/CQCC/spectrogram features, classical model artifacts, CNN smoke/subset
  reports, robustness/latency reports, and a SQLite database.
- A FastAPI application in `app\main.py`, a separate Streamlit research prototype in
  `app\streamlit_app.py`, shared audio/features under `src\svf\`, and SQLite CRUD code.
- Seven Stitch HTML pages under `app\static\stitch\` and a shared
  `stitch-runtime.js`.

Expected recovery-prompt files that are not currently present in `docs\` include
`APP_BLUEPRINT.md`, `MASTER_PROMPT.md`, and `COPILOT_APP_PROMPT.md`. Existing
`AUDIT.md`, `decision.md`, and `flow.md` provide partial prior documentation.

## Existing model and evaluation wiring

The saved detector is `models\classical_for_2sec\svm.joblib`, loaded by
`app\core\detector.py` using `models\model_meta.json`. It uses the shared audio loader
and MFCC implementation, fixed 2-second windows, VAD gating, and a validation-EER
threshold of `0.6786657728693419`. The model score is an SVC class-1 estimate and is
not a calibrated real-world probability.

The FastAPI upload endpoint decodes an uploaded file, calls the detector, stores the
analysis and per-window rows in SQLite, and exposes health, model info/metrics,
dashboard summary, history, CSV export, settings, and a live WebSocket. Existing API
tests cover upload/history, settings/clear, and a basic live session.

The saved primary SVM report records test accuracy `0.5542279411764706`, precision
`0.7218045112781954`, recall `0.17647058823529413`, F1 `0.28360413589364847`,
FPR `0.06801470588235294`, FNR `0.8235294117647058`, ROC-AUC
`0.7349021410034602`, and EER `0.3272058823529411`. Validation performance is much
higher, so it must not be presented as test performance.

The metadata-only baseline is above chance on the primary test split
(accuracy `0.6856617647`), which is an active shortcut warning. Existing documents
also report severe robustness degradation and no MP3 compression experiment because
`ffmpeg` was unavailable.

## Backend gaps and risks

- Settings currently persist uncertain band, hop, VAD, smoothing, alert count, and
  raw-audio preference, but the model threshold is fixed from the saved metadata and
  there is no demo-sample API or ground-truth reveal flow.
- The live backend accepts PCM frames and emits window/alert/summary messages, but
  disconnect/reconnect behavior, system/tab audio, AudioWorklet capture, demo replay,
  and explicit partial-session handling are not complete.
- `app\main.py` has limited error handling around health/model artifact reads and the
  WebSocket path; failure states need explicit, user-visible handling.
- The model info endpoint contains a hard-coded training count (`13956`) rather than
  deriving all counts from a manifest/result artifact.
- Existing database history stores results and windows but does not store ground truth,
  demo provenance, or a full model metadata snapshot per analysis.
- No leakage test for four disjoint sets exists yet.

## Frontend gaps and risks

The FastAPI routes serve the Stitch HTML pages, each of which includes substantial
static design content, external Google Fonts, and a Tailwind CDN reference. The shared
`stitch-runtime.js` performs text replacement against static labels and binds only a
subset of controls:

- Dashboard, model, history, and status text are partly replaced from API responses,
  but the HTML source contains many static numeric values and labels before API
  responses.
- Analyze File has a real upload binding, but the page still includes static telemetry
  and control surfaces that are not all wired.
- Live Check and Call Monitor currently bind microphone capture with
  `ScriptProcessorNode`, not the required AudioWorklet; system/tab capture and demo
  replay are not wired end-to-end.
- Settings loads and saves a subset of controls, but error reporting is console-only,
  the threshold is intentionally disabled, and the store-raw-audio toggle depends on
  page-specific DOM state.
- History, export, drawers, search/filter/pagination, spectral views, and several
  buttons appear in the HTML but are not proven to have complete behavior.
- Pages depend on external fonts and Tailwind CDN resources, so offline operation is
  not established.
- There is no wiring matrix or no-mock scanner yet.

The older `app\static\app.js` is a separate DOM-rendered single-page implementation
with broader fetch/WebSocket logic, but the FastAPI routes serve Stitch pages instead,
so it is not the active frontend path.

## ASVspoof LA discovery from the existing copy

The existing `LA\LA\` tree matches the official logical-access layout at a high level:

- `ASVspoof2019_LA_cm_protocols`
- `ASVspoof2019_LA_asv_protocols`
- `ASVspoof2019_LA_asv_scores`
- `ASVspoof2019_LA_train`
- `ASVspoof2019_LA_dev`
- `ASVspoof2019_LA_eval`
- `README.LA.txt`

The README states that audio is 16 kHz, 16-bit FLAC. CM protocol rows have the
columns `SPEAKER_ID AUDIO_FILE_NAME SYSTEM_ID - KEY`, with `bonafide` and `spoof`
labels and attack IDs A01-A19. The checked training protocol begins with rows such
as `LA_0079 LA_T_1138215 - - bonafide`. The README describes the ASV protocol
formats separately. Per-partition `LICENSE.txt` files are present; they begin with
the Open Data Commons Attribution License and warn that contents can have separate
rights, so the dataset must not be committed or redistributed.

Counts by partition, speaker coverage, attack IDs, audio metadata distributions,
hashes, and the official license/README summary have not yet been measured by a
dedicated discovery script. Those are D3/D4 work and remain **NOT VERIFIED**.
The existing ASVspoof copy is not in `data\raw\` and must be verified before use.

## D0 pre-flight result

- Free space on drive D: `284067926016` bytes (`264.56 GB`).
- `curl.exe`: available, version `8.21.0`.
- Bare `python`: unavailable via PATH/Microsoft Store alias.
- Project interpreter: `.venv\Scripts\python.exe`, Python `3.14.3`.
- `data\raw\`: created and empty before any download.
- Existing ASVspoof copy: present under `LA\LA\`; no `LA.zip` was found.
- No download, extraction, package installation, or model training was performed.

## Gate conclusion

R0/D0 diagnosis and pre-flight are complete. The current system is a measured
research prototype, not yet the complete recovery-prompt system. The next permitted
step is D1/D3 verification of the existing ASVspoof copy (or a separately approved
download decision), followed by manifest/split work. Model retraining and frontend
rewiring must not begin before the data gate is complete.
