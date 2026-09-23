# SLADeck

SLADeck is a portfolio-ready multi-tenant SaaS for support and operations teams. It manages service requests, SLAs, assignments, comments, immutable audit events, automated escalation notifications and operational analytics.

## Architecture

```
Next.js + TypeScript
        |
        v
     FastAPI
        |
        v
   PostgreSQL <---- Celery worker
        ^              ^
        |              |
        +---------- Redis
                       ^
                       |
                  Celery Beat
```

The Docker Compose stack includes PostgreSQL, Redis, a migration job, FastAPI, Celery Worker, Celery Beat and the Next.js frontend.

## Implemented capabilities

- authentication with access/refresh tokens;
- organization-scoped RBAC and tenant isolation;
- request inbox with search and status/priority filters;
- SLA policies and first-response/resolution deadlines;
- request assignment and lifecycle controls;
- comments and request activity timeline;
- immutable audit events;
- idempotent SLA warning/breach notifications;
- in-app notification center;
- operational analytics for workload and SLA health;
- PostgreSQL migrations;
- automated backend tests and coverage gate;
- frontend typecheck and production build;
- Docker Compose local stack;
- GitHub Actions validation for backend, frontend and container builds.

## Quickstart with Docker

Prerequisites: Docker with Compose support.

1. Create a local environment file:

```bash
cp .env.example .env
```

2. Set a non-default `SLADECK_JWT_SECRET` in `.env`.

3. Start the complete stack:

```bash
docker compose up --build
```

4. Open:

- Frontend: http://localhost:3000
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs

The migration container applies the current Alembic schema before the API and worker services start.

To stop the stack:

```bash
docker compose down
```

To remove the local PostgreSQL volume as well:

```bash
docker compose down -v
```

## Local development

### Backend

```bash
cd backend
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn sladeck.api:app --reload
```

Set `SLADECK_DATABASE_URL` and `SLADECK_REDIS_URL` when PostgreSQL and Redis are not running on their defaults.

Run quality checks:

```bash
ruff check .
pytest -q --cov=sladeck --cov-report=term-missing
```

The backend coverage configuration requires at least 90%.

### Frontend

```bash
cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

For the frontend to call a non-default API, set `NEXT_PUBLIC_API_URL`.

## Main workflow

1. Register or sign in.
2. Create/select an organization.
3. Create an SLA policy.
4. Create a request.
5. Assign and update the request.
6. Record first response and comments.
7. Worker/Beat checks SLA deadlines.
8. Notifications and audit events are persisted.
9. Analytics show workload and SLA health.

## Security and tenant isolation

Business data is constrained by organization membership. Cross-tenant access is covered by integration tests, including request and activity access. Request, policy and membership relationships also enforce organization ownership at the database/API boundary.

Secrets are provided through environment variables. Production configuration rejects the default development JWT secret.

## CI

GitHub Actions validates:

- Python 3.12 and 3.13;
- Ruff;
- PostgreSQL/Redis-backed pytest suite;
- 90% backend coverage gate;
- frontend TypeScript checks;
- frontend production build;
- Docker Compose configuration;
- backend and frontend container builds.

## Known limitations

- This is an MVP, not a production deployment platform.
- There is no external email/SMS notification provider.
- Analytics are intentionally focused on operational request/SLA metrics.
- The Compose configuration is designed for reproducible local/demo environments rather than high availability.
- The frontend currently uses a browser-side API client and local session storage rather than a dedicated BFF.
- No cloud deployment manifests are included.

## Architecture documentation

See [docs/architecture.md](docs/architecture.md) for the domain model, tenant isolation, SLA engine, background processing and API boundaries.
