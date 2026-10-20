# Synthetic Voice Forensics

CPU-oriented research prototype for estimating whether speech is real or synthetic. The label is `0 = real` and `1 = synthetic`; scores are model estimates, not proof of authenticity.

## Run locally

Use Python 3.14. Install the runtime dependencies with `python -m pip install -r requirements.txt`, then start the app from the repository root:

```powershell
python -m pip install -r requirements.txt
python scripts/run_app.py
```

Open <http://127.0.0.1:8000/>. Create an account from the sign-in page. Local accounts, settings, and saved analyses use SQLite under the ignored `data/` directory. Passwords are hashed; credentials and the database are not part of this repository.

The source repository does not include datasets, trained model files, evaluation reports, or demo audio. Real scoring requires the matching local artifacts described in [Project status](docs/PROJECT_STATE.md). Without them, the app cannot provide model inference. Do not replace missing artifacts with sample scores.

Tests and research/training scripts also use development dependencies: install those with `python -m pip install -r requirements-dev.txt`.

## What is included

- File analysis, live microphone check, and on-device audio stream monitoring for microphone, shared tab audio, or demo replay.
- Dashboard, saved analysis history, model/evaluation view, account settings, and theme controls.
- FastAPI APIs, authenticated user accounts, SQLite for local use, and PostgreSQL support through `DATABASE_URL`.
- Research scripts, leakage checks, model evaluation, and regression tests.

Call Monitor inspects audio supplied by this browser; it is not connected to a phone network. Model performance is limited on held-out and out-of-distribution speech. Read the evaluation caveats before interpreting results.

## Frontend stylesheet build

The generated Tailwind stylesheet is committed and served locally; Node is not needed to run the app. If you change Tailwind classes or the theme, regenerate it with the locked development dependency:

```powershell
npm ci --ignore-scripts --no-audit --no-fund
npm run build:css
```

## Checks

Run from the repository root:

```powershell
python -m pytest -q
python scripts/scan_no_mock.py
node --check app/static/app-runtime.js
```

## Read next

- [Project status and limitations](docs/PROJECT_STATE.md)
- [Page and API wiring](docs/WIRING_MATRIX.md)
- [Evaluation evidence and caveats](docs/AUDIT.md)
- [Dataset protocol notes](docs/DATASET_NOTES.md)
- [Authentication and deployment requirements](docs/AUTH_DEPLOY_PLAN.md)
- [Local presentation/demo steps](docs/DEMO_GUIDE.md)
- [Vercel deployment runbook](docs/VERCEL_DEPLOY.md)

## Deployment status

**Not ready for production deployment.** A Vercel project, persistent hosted PostgreSQL, private delivery for model/report artifacts, and a hosted live-monitoring preview test are not configured. Do not deploy this source-only checkout as a working detector. See [authentication and deployment requirements](docs/AUTH_DEPLOY_PLAN.md).
