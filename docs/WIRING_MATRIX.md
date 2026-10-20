# UI and API map

The active HTML views are in `app/static/stitch/`; `app/static/stitch-runtime.js` binds them to the FastAPI API. The supplied visual templates are retained. Static template HTML is not a source of analysis results: active scores and saved records come from the API or model reports.

| View/control | Expected behavior | Data/API | Current evidence |
|---|---|---|---|
| Dashboard totals, percentages, graph, recent rows | Show saved account activity; empty account has zero/empty values | `GET /api/dashboard/summary`, `GET /api/history`, `GET /api/model/info` | API integration tests pass; post-R8 visual sweep **NOT VERIFIED** |
| File analysis, profile picker, result, JSON download | Validate/upload audio; show actual model score and details; export current result | `POST /api/analyze/upload`, `GET /api/model/info` | Full API suite passes; browser upload paths after R8 **NOT VERIFIED** |
| Live Check: consent, source, start/stop, VAD and score graph | Stream captured PCM16 audio to the FoR window model; persist completed session | AudioWorklet, one-use ticket API, `WS /ws/live` | WebSocket integration tests pass; physical microphone after latest change **NOT VERIFIED** |
| Call Monitor: microphone/shared tab/demo, start/stop | Monitor browser-provided audio only; show live model windows and saved session | `GET /api/demo/samples`, `GET /api/demo/audio/{id}`, `POST /api/demo/analyze/{id}`, `WS /ws/live` | API/WebSocket tests pass; physical devices and demo replay after latest change **NOT VERIFIED** |
| History search, source/verdict filters, details, CSV | Filter the signed-in user's saved records; expand a row; download CSV | `GET /api/history`, `GET /api/history/{id}`, `GET /api/history/export.csv` | API tests pass; newly hydrated source filter and browser details **NOT VERIFIED** |
| Model & Evaluation report, hash copy, model profile | Show metadata and available saved evaluation; download JSON; copy loaded artifact hash | `GET /api/model/info`, `GET /api/model/metrics` | API tests pass; updated button/hash browser actions **NOT VERIFIED** |
| Settings save, VAD presets, clear history | Persist selected account/profile settings and delete that account's analysis records | `GET/PUT /api/settings`, `DELETE /api/history` | API/security tests pass; latest browser click path **NOT VERIFIED** |
| Sign up, login, account menu, theme, logout | Create/authenticate account, scope private routes, manage session, save browser theme | `/api/auth/*`; local theme preference | Auth and authorization suite passes; see [deployment plan](AUTH_DEPLOY_PLAN.md) for production requirements |

## Run the automated checks

```powershell
python -m pytest -q
python scripts/scan_no_mock.py
node --check app/static/stitch-runtime.js
```

Latest recorded local output is in [Project status](PROJECT_STATE.md). These checks do not replace physical-device, browser visual, offline, or hosted deployment acceptance.

## Limitations

- The legacy FoR held-out test result is weak; the score is not proof of authenticity. See [evaluation evidence](AUDIT.md).
- The ASVspoof complete-clip model is not the streaming model. Do not label one as the other.
- Monitoring reads a browser audio stream on this device. It has no phone-network integration.
- Microphone permissions, shared-tab capture, demo completion, API-down rendering, offline rendering, and the post-R8 visual flow are **NOT VERIFIED**.
