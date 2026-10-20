# Authentication and deployment reconnaissance

Status: V0 reconnaissance and V1–V4 local storage, auth, authorization, and browser account-flow
gates are implemented. Vercel deployment is not configured.

## Current implementation

- Auth helpers in `app/core/auth.py` and routes in `app/main.py` support email or username identity,
  Argon2id for new credentials, automatic PBKDF2 upgrade, hashed opaque sessions, DB-backed rate
  limits, same-origin JSON checks, password changes, export, deletion, and WebSocket tickets.
- `app/db/database.py` wraps SQLAlchemy 2 and Alembic; `DATABASE_URL` selects local SQLite or hosted
  PostgreSQL. Analyses and settings carry nullable owner IDs so legacy records remain ownerless.
- Model metrics/info, uploads, demo resources, dashboard, history/export/detail/clear, settings, and
  live streaming require authentication and scope personal records to the session owner. Health and
  auth routes remain available without a session. WebSockets require a one-use ticket.
- The login screen supports email signup/display name and email-or-username login. Private pages
  redirect to sign-in and return to their requested page. The account menu supports theme/logout;
  account controls include password change, JSON export, and password-confirmed account deletion.
  External email verification/reset, production credentials, and hosted storage are not configured.
- The HTML pages and JS/CSS are served by FastAPI from `app/static/`; there is no separate `public/`
  static deployment or `vercel.json`. Runtime files include seven supplied Stitch templates and
  the `stitch-runtime.js` hydrator.
- There are 28,008,659 bytes across the current `models/` tree. `models/` is ignored by `.gitignore`,
  so none of those local artifacts can be assumed to reach a deployment. The selected legacy SVM
  is in `models/classical_for_2sec/svm.joblib`; model metadata and reports are also local files.
- Demo audio is resolved from local files via `data/manifests/asvspoof_la_demo_holdout.csv` and
  the ASVspoof dataset tree. Public redistribution is not approved by this reconnaissance; review
  the dataset license before enabling it on a public deployment.
- Current dependency declarations are in `requirements.txt`; they include NumPy, SciPy, pandas,
  scikit-learn, librosa, soundfile, matplotlib, joblib, FastAPI, multipart, Uvicorn, httpx2,
  pytest, SQLAlchemy, Alembic, argon2-cffi, and psycopg 3. The selected installed package trees
  measured 351,951,585 bytes before these auth/DB additions; the deployment bundle must be measured
  from Vercel's built artifact rather than inferred from the venv directory.

## V1 database layer — completed locally, 2026-10-20

- SQLAlchemy Core now provides the connection engine. Alembic revision `20261020_0001` upgrades
  the existing SQLite schema and creates the login-attempt and WebSocket-ticket tables. `DATABASE_URL`
  selects SQLite or PostgreSQL; `.env.example` contains placeholders only.
- `analyses` and `settings` now have nullable `user_id` foreign keys. The two pre-existing analyses
  remain ownerless, and the six legacy settings remain ownerless; no account can claim them as part
  of this phase. Settings support a separate key namespace per user while preserving the legacy
  global-key upsert behavior.
- `data/backups/voiceguard-pre-v1-20261020.sqlite3` is the pre-migration SQLite backup. Backup
  validation: `integrity_check=ok`; source/backup counts matched (`analyses=2`, `windows=15`,
  `settings=6`, `users=0`, `auth_sessions=0`). The first live migration triggered a cascade that
  removed 15 child window rows; I immediately restored them from the verified backup and confirmed
  `foreign_key_check=[]`. The migration was corrected to preserve windows around SQLite's parent
  table rebuild, and a fresh copy rehearsal retained all `2/15/6` analysis/window/settings rows.
- Full suite after the SQLAlchemy adapter and settings compatibility repair:
  `34 passed, 2 warnings in 56.49s`. API tests: `11 passed, 12 Alembic configuration warnings`
  before `path_separator=os` was added; final full run has only the two existing librosa short-signal
  warnings. A disposable auth HTTP smoke test returned signup 201, duplicate 409, wrong-password
  401, login 200, `/me` true after signup and false after logout; it used a temporary database.
- At the V1 gate, the login flow was still PBKDF2/username-based and data routes were public. Those
  gaps were addressed in the V2 and V3 sections below; browser page guards/account UI remain in V4.
- Rollback is by restoring the verified backup; the initial Alembic revision is deliberately
  forward-only to prevent silently dropping user-specific settings.

## V2 authentication hardening — completed locally, 2026-10-20

- New credentials use Argon2id; legacy PBKDF2 accounts are upgraded after a successful login.
  Invalid and missing accounts use a dummy Argon2 verification and share a generic login error.
- Password length is 10–128 characters and a small common-password list is rejected. Login failures
  (5 per email/IP in 15 minutes) and signup attempts (10 per IP per hour) are stored in the database.
- Sessions are random opaque HttpOnly/SameSite=Lax cookies backed by hashed database tickets and
  expire after seven days. Cookie Secure follows `VERCEL`, `COOKIE_SECURE`, or the legacy setting.
- Auth mutations require JSON and an allowed same-origin Origin. Password change revokes other
  sessions; account export and deletion endpoints operate on that user's records.
- Focused test coverage includes Argon2id storage, generic failures, rate limits, origin checks,
  cookie attributes/expiry, password change, one-use WebSocket tickets, export, and deletion.

## V3 data authorization — completed locally, 2026-10-20

- Analysis upload/demo results, dashboard, history/detail/export/clear, model information, and
  settings now require a valid session. Each query, mutation, and setting uses the session owner ID;
  guessed cross-user analysis IDs return 404. Legacy `user_id=NULL` rows are not shown to accounts.
- Upload and demo detector settings now use the current account's threshold/band; streaming settings
  and persisted live sessions also use the ticket owner.
- `/ws/live` requires a short-lived, single-use ticket issued through the authenticated JSON API.
  The browser obtains and sends the ticket before beginning audio transmission. Tickets reject
  missing, invalid, expired/reused, and other-account attempts.
- Two-account tests cover no-session rejection, history/dashboard/export separation, IDOR 404,
  isolated settings, scoped clear, and WebSocket ticket ownership/reuse.
- Focused auth/API/authorization suite: `21 passed in 12.34s` after correcting the per-user upload
  threshold path. Full-suite result is recorded in `PROJECT_STATE.md` after its current run.

## Main risks and proposed change list

1. Preserve current local SQLite and history with a verified backup before a schema migration.
2. Introduce SQLAlchemy 2 and Alembic; support local SQLite and hosted Postgres from `DATABASE_URL`.
   Add users, hashed auth sessions, database-backed login attempts, one-time WebSocket tickets,
   per-user settings, and nullable-to-backfilled ownership migration for existing local rows.
   Existing records need an explicit owner decision; do not silently expose them to future accounts.
3. Implement Argon2id, generic login failures, input validation, CSRF Origin/Host and JSON checks,
   persistent rate limits, revocation/expiry, account export/deletion, and single-use short-lived
   WebSocket tickets. Keep DB work off the async event loop.
4. Require authentication for data routes and `/ws/live`; scope every read/write by `user_id`.
   Unknown or cross-user IDs must return 404. Verify with two-user isolation tests.
5. Update login/menu UI for email and display name, route guards, logout/session expiry, and account
   management while preserving the supplied dashboard and analysis UI.
6. For deployment, separate static assets from API routing where practical, use only environment
   configuration, and replace local file persistence with hosted Postgres/object storage.
   Keep `.env` and dataset/audio out of git. Evaluate the model artifact and dependency footprint.
7. Do not assume the live WebSocket is deployable on Vercel. The current app is a FastAPI ASGI app;
   Vercel's current documentation describes FastAPI/Python support and a 500 MB uncompressed
   function bundle limit, a 4.5 MB function payload limit, and up to 300 seconds on Hobby with
   Fluid Compute. Current Vercel docs announce WebSockets in public beta, but the examples are
   Node.js; compatibility of this Python FastAPI WebSocket endpoint must be proven by a preview
   spike. If it fails, use Vercel for static frontend and a long-running backend host for FastAPI.
8. The existing upload cap is 10 MB, above Vercel's 4.5 MB function body limit. Before Vercel,
   normalize/trim in the browser or upload directly to object storage with a clear duration/size
   disclosure.

## Gates

- V1 gate: local DB abstraction, migration and restore proof on a copied SQLite DB are complete.
- V2 gate: local auth/security and persistence checks; external hosted-email verification is not
  part of this local phase.
- V3 gate: focused API suite plus two-user authorization and WebSocket-ticket isolation tests.
- V4 gate: Edge signup/return-to-private-page, account page, export, password change, deletion,
  and signed-out state verified with one disposable account (removed after the flow).
- V5: deployability spike: built bundle size, cold start/model load, DB connection, payload, and
  Python WebSocket preview test. Recommend Vercel-only or split hosting based on measured output.
- V6-V8: preview smoke tests, security review, and final acceptance after the student configures
  hosted Postgres and Vercel secrets.

## Verified platform references

- [Vercel Python runtime and FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel function limits](https://vercel.com/docs/functions/limitations)
- [Vercel WebSocket support announcement](https://vercel.com/changelog/websocket-support-is-now-in-public-beta)

These platform details can change; recheck them when starting V5.

## V5 preflight — local preparation (2026-10-20)

GitHub preflight: the supplied repository URL was reachable with `git ls-remote`; it returned no
refs, so the remote had no branch HEAD before the initial push. The reviewed source-only root commit
`17f11ce` was pushed to `codex/r4-stream-evaluation` without force. The staged set contained 125
files and passed the blocked-path and high-confidence credential-pattern checks. It excludes
research data and runtime artifacts.

Added root `index.py`, which exports the existing `app.main:app` instance through a documented
FastAPI entrypoint. Vercel's current official FastAPI guide supports `index.py` and Python FastAPI
deployments. This source-level entrypoint is not proof of a successful Vercel build. A local Python
environment cannot establish the built bundle size, cold start, hosted database connectivity, or
WebSocket compatibility.

The project `.gitignore` now excludes `.env*` except the placeholder `.env.example`,
SQLite/database files, all `data/`, `LA/`, `for-*` datasets, model artifacts, and result files. Before
any push, inspect the complete staged path list and run credential-pattern scans. Excluding these
files means the GitHub source alone does not include the trained models or evaluation reports and
cannot provide real detector inference until the deployment's artifact-delivery plan is configured.
Do not copy research data or trained models into Git to work around that missing deployment input.

Required student-side inputs before V5 can pass: a hosted PostgreSQL connection string in Vercel
Environment Variables (never committed); a secure artifact delivery decision for the trained model
plus matching metadata/reports; and access to a Vercel preview project for build, cold-start,
database, payload, and Python WebSocket tests. The repository may be source-pushed before these are
connected, but that is not a deployable/working production release.

The SQLAlchemy adapter accepts provider-style `postgresql://` and `postgres://` URLs and routes them
through the declared psycopg 3 driver. MongoDB is not a compatible replacement for this app's
relational schema and Alembic migrations; use PostgreSQL (Neon is suitable) unless the persistence
layer is deliberately redesigned and revalidated.

Local code checks after this preflight:

```text
.venv\Scripts\python.exe -m py_compile index.py app\main.py app\core\auth.py app\db\database.py
exit 0
.venv\Scripts\python.exe scripts\scan_no_mock.py
No mock data patterns found in 32 active application files.
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-v5-verified
52 passed, 2 warnings in 99.42s
```

The full suite had to run outside the restricted sandbox because Windows asyncio's loopback socket
pair creation blocked Starlette TestClient startup inside it. Warnings are existing short-signal
librosa `n_fft=1024` warnings.

Git push output:

```text
To https://github.com/UjjwalKumarKannojiya/Synthetic-Voice.git
 * [new branch]      codex/r4-stream-evaluation -> codex/r4-stream-evaluation
branch 'codex/r4-stream-evaluation' set up to track 'origin/codex/r4-stream-evaluation'.
```
