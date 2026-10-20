# Frontend and API wiring

The active pages reuse the supplied Stitch design templates under `app/static/stitch/`. FastAPI
serves each template at its page route, and `stitch-runtime.js` binds page data and controls to the
real API. Data values and graphs should come from saved reports, history, or incoming model windows.

| View | Data and actions | Backend contract |
| --- | --- | --- |
| Dashboard | Current totals, recent analyses, model status, quick navigation | `GET /api/dashboard/summary`, `GET /api/model/info` |
| Analyze | File selection, profile selection, score, threshold/verdict, window detail, JSON download | `POST /api/analyze/upload`, `GET /api/model/info` |
| Live check | Microphone capture, consent gate, live level/VAD meter, FoR fake-score graph with threshold band, stop/save summary | `AudioWorklet` PCM16 → `WS /ws/live`; persisted `GET /api/settings`; demo endpoints for replay |
| Call monitor | Microphone/system-tab/demo source, consent gate, live level/VAD meter, same FoR score graph, repeatable start/stop, local history summary | `AudioWorklet` PCM16 → `WS /ws/live`; `GET /api/demo/samples`, `GET /api/demo/audio/{id}`, `POST /api/demo/analyze/{id}` |
| History | Source/verdict filters, row details, complete CSV export | `GET /api/history`, `GET /api/history/{id}`, `GET /api/history/export.csv` |
| Model and evaluation | Selected model metadata, real report metrics and confusion matrix | `GET /api/model/info`, `GET /api/model/metrics` |
| Settings | Per-profile threshold, stream band/hop/VAD/smoothing/alert values, clear history | `GET /api/settings`, `PUT /api/settings`, `DELETE /api/history` |
| Account page | Local sign up/sign in switch, credential form, theme switch, back link | `POST /api/auth/signup`, `POST /api/auth/login`; local theme preference |
| User menu (shared) | Open/close via user icon, account status, sign out, dark/light mode | `GET /api/auth/me`, `POST /api/auth/logout`; browser theme preference |

Shared controls: profile selection loads that profile's metadata and threshold; navigation and page
actions are registered in `app/static/app.js`. The model selector has no constant fallback metrics.
Unknown profiles and invalid inputs are rejected by the API. Model reports identify subset metrics
as subset results. The ASVspoof complete-clip detector is not used for WebSocket windows.

## Manual acceptance checklist

R7 browser evidence: all seven routes rendered at desktop (1280), tablet (768), and mobile (375)
widths without JavaScript exceptions; Call Monitor's 375 px overflow was corrected and retested
(`innerWidth=375, rootWidth=375, scrollWidth=375`). An isolated Edge profile with a known validation
WAV as its fake microphone exercised Live Check (19 windows; saved session detail) and Call Monitor
(2 windows; saved session detail) through AudioWorklet, WebSocket inference, and stop. This verifies
the browser stream pipeline using test audio only. Settings save and VAD preset behavior were
observed with the settings PUT intercepted to avoid changing persistent user settings.

Physical microphone permission/capture and real speech scoring, system/tab capture, demo replay
completion, Settings error toast, API-down UI, and offline behavior remain NOT VERIFIED. Verify
those paths in Chrome or Edge after opening `http://127.0.0.1:8000/`:

1. Navigate all seven views; confirm API errors and empty history show explanatory states.
2. Analyze a valid and an invalid audio file; verify only the valid one creates a history row.
3. Exercise consent, microphone selection, source switching, start/stop twice, and history save in Live Check.
4. Try the demo replay; confirm the FoR live stream reading and ASVspoof complete-clip result are
   labeled separately, with ground truth revealed only after analysis.
5. Filter and export history, update each profile's settings, and clear history.
6. Repeat with physical devices and with the API unavailable; verify offline behavior if CDN
   assets are replaced or bundled.

Call monitoring reads a microphone, system/tab stream, or local demo replay on this device; it has no
phone-network integration.

## R8 account, theme, and hardening — 2026-10-20

Added `/login` as a separate page and injected a small user popover through separate account-menu
assets. The seven Stitch page templates and graph are unchanged; runtime changes are limited to
mobile responsive layout.
New account values persist in `data/voiceguard.sqlite3` with PBKDF2-HMAC-SHA256 password hashes and
random salts; sessions use opaque HttpOnly cookies (30-day expiry) and can be logged out. The
sign-in/sign-up page and shared user menu use accessible sun/moon theme icons; theme preference is
saved per browser in localStorage. Versioned asset URLs and a no-store login response reduce stale
browser-cache issues. The account is a local profile label and does not restrict/isolate
existing APIs or analysis history; the login page states this explicitly.

Live HTTP handler flow and browser form flow were exercised with generated disposable accounts:
signup issued an HttpOnly cookie; duplicate username rejected with 409; correct login returned 200;
wrong password rejected with 401; `/me` returned authenticated; logout cleared the session; stored
rows did not contain the password; disposable accounts removed. Headless Edge confirmed sign-up
redirect, authenticated `/me`, logout, theme switching, and the accessible toggle label.

R8 hardening bounds upload reads to the 10 MB limit before staging a temporary audio file. Mobile
layout stacks grid columns, wraps controls, prevents horizontal overflow, and leaves the account icon
visible. A shared SVG favicon serves explicit links and `/favicon.ico`. Headless Edge viewport audit:

```text
login 375/768/1280: viewportWidth=documentWidth=bodyWidth; overflow=false
call monitor 375/768/1280: viewportWidth=documentWidth=bodyWidth; overflow=false; userPresent=true; display=flex
theme: darkTheme=dark; aria-label="Switch to light mode"; lightTheme=light
signupRedirect=true; signupAuthenticated=true; logoutAvailable=true; logoutAuthenticated=false
```

An upload of 10 MB + 1 byte returned HTTP 413 with `{"detail":"Upload exceeds the 10 MB limit"}`.
`tests/test_streaming.py` passed (`1 passed in 0.25s`).

Vercel deployment is not ready with local SQLite; configure a hosted persistent SQL database first.
Cookies set Secure when `VERCEL=1` or `VOICEGUARD_COOKIE_SECURE=1`. Accounts remain a local profile
label and do not isolate analysis/history endpoints. Full-suite pytest is NOT VERIFIED: the first run
had 22 passed and 12 temporary-directory setup errors; a writable-path API/streaming rerun was stopped
after its first API test stalled without output. Offline operation is NOT VERIFIED because the active
pages still load remote Tailwind, fonts, and logo assets.
