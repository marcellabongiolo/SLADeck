# Deployment preparation

The default Compose stack is for local evaluation. Cloud hosting has not yet been verified. This guide describes required services and configuration, without assuming an existing provider account or creating resources.

## Services

- PostgreSQL with persistent storage and backups.
- Redis reachable only by the API and background services.
- A one-off migration job running `alembic upgrade head` before serving requests.
- FastAPI, Celery worker and a single Celery Beat scheduler, all built from `backend/Dockerfile`.
- Next.js built from `frontend/Dockerfile`.

The current Compose database credentials are local demo values. Use separate generated credentials and secret-managed connection strings when hosting. Do not publicly expose PostgreSQL or Redis. Apply HTTPS, request limits and controlled ingress to the API and frontend.

## API and frontend addresses

The browser calls the API directly. The API URL must be reachable from the visitor's browser; a private Docker service hostname is insufficient.

Set `NEXT_PUBLIC_API_URL` to the HTTPS API origin **before building** the frontend. Set `SLADECK_CORS_ORIGINS` to the exact frontend HTTPS origin. For a local Compose address change, update these values in root `.env` and rebuild with `docker compose up --build`. They default to http://localhost:8000 and http://localhost:3000.

For native development, Next.js reads `frontend/.env.local`; backend settings read `backend/.env`. The repository-root example is loaded by Compose, not automatically by processes started in subdirectories.

Configure the API and background services with `SLADECK_ENVIRONMENT=production`, a unique random `SLADECK_JWT_SECRET`, database URL and Redis URL. The migration job must point to that same database. Never put the JWT secret or database credentials in NEXT_PUBLIC variables.

## Hosted acceptance checks

After selecting hosting and configuring domains, verify HTTPS, API /health, successful migrations, registration and login, workspace and SLA creation, request lifecycle, tenant isolation, background escalation notifications and persistent data across restarts. The existing frontend browser tests mock API responses; they do not establish that these cloud services are connected.

Keep exactly one Beat scheduler per deployment. Define database backup/restore and telemetry/log retention before accepting real user data. The MVP stores access tokens in browser local storage and does not provide managed operations or high availability.
