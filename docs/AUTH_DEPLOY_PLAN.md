# Accounts and deployment

## Local account behavior

- Sign-up and sign-in are backed by the project's SQL database. Passwords are stored as password hashes, and browser sessions use opaque HttpOnly cookies.
- Private analysis, dashboard, history, settings, and model endpoints require a session and scope records to that account.
- Local development defaults to SQLite at `data/voiceguard.sqlite3`. This database is ignored by Git and persists on the local machine.
- New passwords must be 10–128 characters and common passwords are rejected. Login and signup attempts are rate-limited.
- Email verification and password reset by email are not implemented. Do not describe account recovery as available.

## PostgreSQL configuration

The app supports PostgreSQL via `DATABASE_URL` using the declared psycopg driver and Alembic migrations. Set this value only in the deployment provider's secret/environment settings; never commit a real connection string. On Vercel the app refuses to start without `DATABASE_URL`, because serverless local files are not durable storage.

MongoDB is not supported by the current relational schema or migrations. Use PostgreSQL (for example, Neon) unless the storage layer is deliberately replaced and retested.

## Vercel readiness

**Prepared for deployment configuration; not deployment-verified.** Required but not configured or verified:

1. A Vercel project and preview build.
2. Persistent hosted PostgreSQL with successful startup migrations and an account/data-isolation smoke test.
3. Private HTTPS delivery for the generated model bundle. The packaging script creates a small archive from the local trained models and reports; it excludes datasets and is written only to ignored `.local-notes/`.
4. Hosted tests for cold start, upload limits, database connections, and authenticated WebSocket live monitoring.

The API uses Python WebSockets for live scoring. Vercel's current material describes WebSockets as beta, while its Limits page conflicts about support, so local tests do not establish hosted compatibility. If the Vercel preview cannot sustain that stream, use a long-running WebSocket-capable Python host. Do not claim deployment readiness until each required gate has actual preview evidence.

See [the Vercel deployment runbook](VERCEL_DEPLOY.md) for the private bundle, environment variables, build exclusions, and preview acceptance steps.

Never put passwords, `.env` files, SQLite data, audio, datasets, model weights, or results in Git. `.env.example` contains placeholders only. Review the staged file list and secret scan before every push.
