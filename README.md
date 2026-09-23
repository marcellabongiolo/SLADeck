# SLADeck

SLADeck is a full-stack SaaS project for teams that manage incoming requests, ownership, priorities and service-level deadlines.

The project is being built as a multi-tenant product with a Python/FastAPI backend, PostgreSQL, Redis-backed background work and a Next.js/TypeScript frontend.

> Status: early development. The initial FastAPI + Next.js foundation is being implemented through Issue #1. Features are documented as implemented only after they are merged and covered by tests.

## Product idea

A workspace receives operational requests. Team members can assign owners, set priorities, collaborate through comments and track whether each request is on time, approaching its SLA deadline or overdue.

The MVP will support:

- user accounts and authentication;
- organizations/workspaces and team membership;
- role-based permissions;
- requests with status, priority, assignee and SLA deadline;
- comments and immutable audit events;
- SLA policies and deadline calculation;
- background escalation/notification jobs;
- searchable/filterable dashboard;
- API documentation;
- automated tests, Docker and CI.

## Planned architecture

```text
Next.js + TypeScript
        |
        | REST API
        v
FastAPI
   |         \
   |          \ background jobs
   v           v
PostgreSQL   Redis + worker
```

See `docs/architecture.md` for the current design.

## Development workflow

Work is developed through:

```text
Issue -> branch -> implementation -> tests -> pull request -> CI -> merge
```

The repository will evolve issue by issue so the Git history reflects the engineering process rather than a single generated code dump.


## Foundation development

The first implementation milestone introduces:

- a FastAPI backend package;
- environment-based backend settings;
- a health endpoint at `GET /health`;
- a Next.js 16 + React 19 + TypeScript frontend shell;
- strict TypeScript validation;
- pytest + Ruff backend checks;
- GitHub Actions for backend and frontend validation.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn sladeck.api:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The web app will be available at `http://localhost:3000`.

PostgreSQL, Alembic, authentication and the SLA domain model belong to later issues and are intentionally not claimed as implemented yet.


## PostgreSQL domain foundation

The database layer uses SQLAlchemy 2 with PostgreSQL and Alembic migrations.

The initial relational model contains:

- `User`
- `Organization`
- `Membership`
- `SLAPolicy`
- `Request`

`Membership` connects a user to an organization with one of the planned roles. Requests
store an explicit `organization_id`, and requester/assignee references are constrained
against memberships in that same organization. This adds a database-level tenant-safety
invariant before application authorization is implemented.

With `SLADECK_DATABASE_URL` pointing to a PostgreSQL database:

```bash
cd backend
alembic upgrade head
```

To roll the current schema back:

```bash
alembic downgrade base
```

CI starts a real PostgreSQL service and verifies both the ORM relationships and the
ability to create the schema from an empty database using Alembic.
