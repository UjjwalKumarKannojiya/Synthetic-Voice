# Vercel deployment runbook

The app uses PostgreSQL, not MongoDB. Vercel detects the FastAPI application from the root `index.py`; `.python-version` and `requirements.txt` pin the Python runtime and tested inference dependencies. `vercel.json` includes authenticated UI assets and migration files in the function while excluding datasets, weights, results, tests, and local notes.

## 1. Create the private model bundle

From the repository root, with the local trained model and result artifacts present, run:

```powershell
.venv\Scripts\python.exe scripts\package_runtime_artifacts.py
```

The script writes `.local-notes/deployment/voiceguard-runtime.zip`, prints the SHA-256 digest, and refuses to overwrite an existing bundle. The archive contains only the two active SVM models, their metadata, their evaluation JSON files, and counts derived from the local training manifest. It does not contain audio, dataset manifests, split rows, feature caches, or training score CSVs. Keep this file out of Git.

Upload that archive to private HTTPS object storage. Vercel Blob is supported directly: link the correct Vercel project, create a private store, and upload the ignored archive:

```powershell
npx --yes vercel@latest blob create-store voiceguard-models --access private --yes
npx --yes vercel@latest blob put .local-notes\deployment\voiceguard-runtime-r8.zip --access private
```

Keep the private URL printed by `blob put` for `VOICEGUARD_ARTIFACTS_URL`. When a private Blob store is connected to the Vercel project, the app prefers Vercel's short-lived OIDC token and falls back to the store's `BLOB_READ_WRITE_TOKEN`; either token is sent only to `*.private.blob.vercel-storage.com`. See Vercel's [private Blob authentication guide](https://vercel.com/docs/vercel-blob/private-storage).

Configure the Vercel project with:

| Variable | Value |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL. For Supabase, use Dashboard → Connect → Transaction pooler (port 6543) and include `sslmode=require`. Percent-encode reserved characters in the username or password (`@` as `%40`, `#` as `%23`). The runtime selects SQLAlchemy `NullPool` and disables Psycopg auto-prepared statements for this port. |
| `VOICEGUARD_ARTIFACTS_URL` | Private HTTPS download URL for the ZIP. Do not use a public bucket URL. |
| `VOICEGUARD_ARTIFACTS_SHA256` | The digest printed by the packaging command. |
| `VOICEGUARD_ARTIFACTS_TOKEN` | Optional bearer token for other private HTTPS storage. Private Vercel Blob uses project OIDC or its connected Blob token automatically. |

Set these as Vercel environment variables for Preview and Production. Do not put the values in Git or expose the bundle URL in application logs. The app downloads the bundle into Vercel's writable `/tmp`, validates the checksum and exact allowed file list, then loads model weights from that directory. A missing URL, invalid digest, bad archive, or missing PostgreSQL URL fails startup clearly instead of serving unscored results.

Treat database passwords and Supabase secret API keys as secrets: enter them only in Supabase/Vercel settings, never in Git or chat. If either was shared, rotate it before using the project for Production. A Supabase `sb_secret_...` key grants elevated project data access; it is not a PostgreSQL connection string or a Supabase Management API token, and must never be stored in this app.

Supabase is supported because it provides PostgreSQL. Its [connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres) recommends the IPv4 shared transaction pooler for serverless functions; copy the exact host and username from the Supabase dashboard rather than constructing them. The app follows Supabase's [SQLAlchemy guidance](https://supabase.com/docs/guides/troubleshooting/using-sqlalchemy-with-supabase-FUqebT) by using `NullPool` and disabling Psycopg auto-prepared statements on port 6543. The app keeps Alembic's migration and its transaction-scoped advisory lock within one transaction. Verify startup migrations against the Preview database: Supabase recommends direct connections for migration tools, so if the transaction pooler rejects startup migrations, switch `DATABASE_URL` to Supabase's session pooler and monitor the database connection limits.

## 2. Import and preview the GitHub project

Import `UjjwalKumarKannojiya/Synthetic-Voice` in Vercel. Keep the FastAPI preset/automatic detection, no custom build command, and the repository root as the project root. Vercel's Python runtime detects the `app` object in `index.py`; the application serves its HTML through authenticated FastAPI routes.

The app runs Alembic migrations during startup. PostgreSQL advisory locking serializes simultaneous cold-start migrations, and the serverless SQLAlchemy pool is limited to one connection per function instance. Alembic revision `20261020_0003` enables RLS on VoiceGuard's app tables, revokes table/sequence grants from Supabase's `anon`, `authenticated`, and `service_role` API roles, and removes those roles from default privileges for future objects created by the app database role. The FastAPI backend uses its server-side PostgreSQL role; database credentials must never reach browser code. The readiness response checks database connectivity and model/report availability.

## 3. Verify the Preview before Production

After Vercel has built a Preview deployment, visit `/api/health`. It must return `ready: true`, `database_connected: true`, and both model profiles available. Then create a disposable account, upload an audio clip under the configured 4 MB limit, confirm the response includes a real model score, and confirm the saved result appears in History. Delete the disposable account afterward.

Live Check and Call Monitor use the FastAPI `/ws/live` endpoint. Vercel's WebSocket knowledge-base article says Functions natively support WebSockets, while its Limits page still says Functions cannot act as a WebSocket server. A Preview must prove microphone streaming, scoring windows, session save, and reconnect/stop behavior before relying on those pages. If the Preview does not upgrade `/ws/live`, host the FastAPI service on a WebSocket-capable Python host; this source cannot honestly promise live streaming without that test.

The public repository excludes demo audio and manifests, so Demo Replay has no hosted samples until separately provisioned. Microphone live monitoring and uploaded-file analysis use the bundled model artifacts and do not require the training dataset.

## Earlier Preview failure notes (superseded by the current status below)

**Preview is deployed but not runtime-ready.** The private Blob artifact download and bundle validation completed. The most recent protected `/api/health` call returned `FUNCTION_INVOCATION_FAILED`; sanitized runtime logs show the connection attempt resolves to Supabase's direct IPv6 database endpoint and fails with `Cannot assign requested address` from Vercel. The previous URL-encoding parse error was corrected for Preview, so this is now an IPv4/IPv6 route issue. Vercel needs the exact Supabase shared-pooler hostname, project-qualified username, port, and SSL options from the Supabase project connection settings; do not guess a pooler hostname. The connected Supabase tools confirmed the project is healthy and its database has no tables or migrations yet. The app's startup migrations are designed to create the schema. For the app's `postgres` database role, table and sequence defaults were tightened in Supabase and verified; the app migration also enforces table RLS and revokes Supabase API-role grants when it creates the schema. The connection metadata is not available from the `sb_secret_...` API key. That key was shared in chat and must be rotated immediately; the previously shared database password must also be rotated before Production. The connected tools do not expose the pooler URL or credential-rotation controls, so Vercel's database URL and credential rotation remain blocked. Production has not been promoted. Hosted migrations, inference, account isolation, upload/history, and WebSocket streaming remain **NOT VERIFIED**. Login has no email verification or password-reset flow.

Additional Preview proof on 2026-10-20: Vercel's request log recorded HTTP 500 for `/api/health`. Matching Python 3.14 runtime logs show both the direct-IPv6 database connection failure and `ImportError: cannot import name 'vc_handler' from 'vercel_runtime.vc_init'`; recheck the adapter error after a fresh Preview build. The no-upload `vercel deploy --dry --json` manifest reports 88 included files (740,442 bytes), 77 ignored paths, and no included `.env*`, local data, model, result, or SQLite paths. `.vercelignore` now explicitly excludes environment files, local Vercel state, pytest scratch folders, and local database files.

## Current verified Preview — 2026-10-20

GitHub-triggered protected Preview deployment `dpl_5pw7UaBXRLbqNYg3qz8YHHFt7iF6` is READY at [voicegaurd-ev9sij6nz](https://voicegaurd-ev9sij6nz-ujjwal21822s-projects.vercel.app). The stable branch alias is [voicegaurd-git-codex-frontend-page](https://voicegaurd-git-codex-frontend-page-63029f-ujjwal21822s-projects.vercel.app). Vercel CLI `/api/health` returned:

```json
{"status":"ok","ready":true,"database_connected":true,"model_loaded":true,"model_version":"classical_for_2sec","profiles":{"legacy_for2sec":true,"asvspoof_la_balanced2500":true}}
```

The hosted auth check passed signup (`201`), login (`200`), authenticated `/api/auth/me`, account deletion (`200`), and confirmed the deleted account's session no longer authenticated. A generated 2-second tone from the existing test helper was uploaded through both `legacy_for2sec` and `asvspoof_la_balanced2500`; both returned HTTP `200` with a model window, and History returned two saved `Upload` records. The temporary account and its analyses were deleted. The tone is not speech, so this proves the server-side inference and storage path runs; it is not a model accuracy check.

The latest full local suite returned `66 passed, 2 warnings in 93.34s`; warnings are librosa short-input `n_fft=1024` notices. `node --check app\static\app-runtime.js`, Python compilation, and the no-mock scan passed. Vercel's upload-free dry run included 88 files (749,421 bytes), ignored 86 paths, and included zero sensitive paths; environment files, local notes, virtualenv, data, models, results, and tests were ignored.

The temporary cleanup endpoint and its Preview-only token were removed before this clean deployment; a POST to that route returns `404`. The Preview database URL uses a separate limited app role. The database owner password and Supabase API secret shared in chat have not been rotated and must be rotated before Production.

**Not verified:** Vercel WebSocket upgrade/streaming for `/ws/live`, microphone/shared-tab capture on the hosted site, and Demo Replay (demo audio is excluded). Local browser fake-audio acceptance is recorded in [PROJECT_STATE.md](PROJECT_STATE.md), but it does not prove Vercel WebSocket support. Production has not been promoted.
