# Vercel deployment runbook

The app uses PostgreSQL, not MongoDB. Vercel detects the FastAPI application from the root `index.py`; `.python-version` and `requirements.txt` pin the Python runtime and tested inference dependencies. `vercel.json` includes authenticated UI assets and migration files in the function while excluding datasets, weights, results, tests, and local notes.

## 1. Create the private model bundle

From the repository root, with the local trained model and result artifacts present, run:

```powershell
.venv\Scripts\python.exe scripts\package_runtime_artifacts.py
```

The script writes `.local-notes/deployment/voiceguard-runtime.zip`, prints the SHA-256 digest, and refuses to overwrite an existing bundle. The archive contains only the two active SVM models, their metadata, their evaluation JSON files, and counts derived from the local training manifest. It does not contain audio, dataset manifests, split rows, feature caches, or training score CSVs. Keep this file out of Git.

Upload that archive to private HTTPS object storage. Configure the Vercel project with:

| Variable | Value |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL. Use the provider's pooled URL when available. |
| `VOICEGUARD_ARTIFACTS_URL` | Private HTTPS download URL for the ZIP. Do not use a public bucket URL. |
| `VOICEGUARD_ARTIFACTS_SHA256` | The digest printed by the packaging command. |
| `VOICEGUARD_ARTIFACTS_TOKEN` | Optional bearer token if the private object endpoint requires one. |

Set these as Vercel environment variables for Preview and Production. Do not put the values in Git or expose the bundle URL in application logs. The app downloads the bundle into Vercel's writable `/tmp`, validates the checksum and exact allowed file list, then loads model weights from that directory. A missing URL, invalid digest, bad archive, or missing PostgreSQL URL fails startup clearly instead of serving unscored results.

## 2. Import and preview the GitHub project

Import `UjjwalKumarKannojiya/Synthetic-Voice` in Vercel. Keep the FastAPI preset/automatic detection, no custom build command, and the repository root as the project root. Vercel's Python runtime detects the `app` object in `index.py`; the application serves its HTML through authenticated FastAPI routes.

The app runs Alembic migrations during startup. PostgreSQL advisory locking serializes simultaneous cold-start migrations, and the serverless SQLAlchemy pool is limited to one connection per function instance. The readiness response checks database connectivity and model/report availability.

## 3. Verify the Preview before Production

After Vercel has built a Preview deployment, visit `/api/health`. It must return `ready: true`, `database_connected: true`, and both model profiles available. Then create a disposable account, upload an audio clip under the configured 4 MB limit, confirm the response includes a real model score, and confirm the saved result appears in History. Delete the disposable account afterward.

Live Check and Call Monitor use the FastAPI `/ws/live` endpoint. Vercel's WebSocket support is described as beta and the platform's Limits page has conflicting language about Functions acting as WebSocket servers. A Preview must prove microphone streaming, scoring windows, session save, and reconnect/stop behavior before relying on those pages. If the Preview does not upgrade `/ws/live`, host the FastAPI service on a WebSocket-capable Python host; this source cannot honestly promise live streaming without that test.

The public repository excludes demo audio and manifests, so Demo Replay has no hosted samples until separately provisioned. Microphone live monitoring and uploaded-file analysis use the bundled model artifacts and do not require the training dataset.

## Deployment status

**Prepared for configuration; not yet deployment-verified.** This repository has no linked Vercel project, PostgreSQL URL, private object-store URL/token, or Preview URL. A successful `vercel build`/Preview and the checks above are still required before calling the deployment ready. Login has no email verification or password-reset flow.
