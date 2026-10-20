# UI and API map

The active HTML views are in `app/static/pages/`; `app/static/app-runtime.js` binds them to the FastAPI API. The page templates provide the UI; active scores and saved records come from the API or model reports.

| View/control | Expected behavior | Data/API | Current evidence |
|---|---|---|---|
| Dashboard totals, percentages, graph, recent rows | Show saved account activity; empty account has zero/empty values | `GET /api/dashboard/summary`, `GET /api/history`, `GET /api/model/info` | Full API suite passes; post-rename Edge route pass showed READY and no backend error; document width matched viewport at 375/768/1280 px across all seven routes |
| File analysis, profile picker, result, JSON download | Validate/upload audio; show actual model score and details; export current result | `POST /api/analyze/upload`, `GET /api/model/info` | API suite passes; Edge upload returned a measured result and persisted an Upload history row |
| Live Check: consent, source, start/stop, VAD and score graph | Stream captured PCM16 audio to the FoR window model; persist completed session | AudioWorklet, one-use ticket API, `WS /ws/live` | Full suite passes; headless Edge fake-audio stream produced model windows and history; physical microphone remains **NOT VERIFIED** |
| Call Monitor: microphone/shared tab/demo, start/stop | Monitor browser-provided audio only; show live model windows and saved session | `GET /api/demo/samples`, `GET /api/demo/audio/{id}`, `POST /api/demo/analyze/{id}`, `WS /ws/live` | Headless Edge demo replay completed and saved a 3.9 second session with two windows; shared-tab/system audio and physical devices remain **NOT VERIFIED** |
| History search, source/verdict filters, details, CSV | Filter the signed-in user's saved records; expand a row; download CSV | `GET /api/history`, `GET /api/history/{id}`, `GET /api/history/export.csv` | Edge source filter retained the uploaded row; API suite passes; details and CSV download were not separately browser-verified in this pass |
| Model & Evaluation report, hash copy, model profile | Show metadata and available saved evaluation; download JSON; copy loaded artifact hash | `GET /api/model/info`, `GET /api/model/metrics` | Edge verified download/hash controls are present; API suite passes; clipboard and file content were not separately browser-verified in this pass |
| Settings save, VAD presets, clear history | Persist selected account/profile settings and delete that account's analysis records | `GET/PUT /api/settings`, `DELETE /api/history` | Edge Settings Save returned its real success toast; API/security suite passes; VAD presets and clear-history were not separately verified in this pass |
| Sign up, login, account menu, theme, logout | Create/authenticate account, scope private routes, manage session, save browser theme | `/api/auth/*`; local theme preference | Disposable signup/session worked; account menu, theme, and cleanup worked in Edge; see [deployment plan](AUTH_DEPLOY_PLAN.md) for production requirements |

## Run the automated checks

```powershell
python -m pytest -q
python scripts/scan_no_mock.py
node --check app/static/app-runtime.js
```

Latest recorded local output is in [Project status](PROJECT_STATE.md). The Tailwind stylesheet is generated locally and served without the Tailwind CDN; Google Fonts, Material Symbols, and the logo still use remote resources. These checks do not replace physical-device, shared-tab audio, full viewport, fully offline, or hosted deployment acceptance.

## Limitations

- The legacy FoR held-out test result is weak; the score is not proof of authenticity. See [evaluation evidence](AUDIT.md).
- The ASVspoof complete-clip model is not the streaming model. Do not label one as the other.
- Monitoring reads a browser audio stream on this device. It has no phone-network integration.
- Physical microphone, shared-tab capture, API-down rendering, offline rendering, and full offline rendering is **NOT VERIFIED**; responsive width check passed at 375/768/1280 px across all seven routes.
