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


## Authentication and organization RBAC

SLADeck uses Argon2 password hashing, signed short-lived access tokens and opaque refresh
tokens backed by revocable database sessions.

Implemented authentication endpoints:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

Organization endpoints require a valid Bearer access token. Creating an organization
automatically makes the creator its `owner`.

Roles:

- `owner` — highest organization role;
- `admin` — can manage ordinary members and managers;
- `manager` — organization member with elevated domain permissions reserved for later features;
- `member` — standard organization member.

Membership is checked separately from authentication. A valid access token does not grant
access to another organization's data.

Refresh tokens are random opaque secrets. Only their SHA-256 hashes are persisted, and
refreshing rotates the token by revoking the previous session and issuing a new one.

For production, `SLADECK_JWT_SECRET` must be configured with a strong random secret; the
application rejects the development default when `SLADECK_ENVIRONMENT=production`.

Ownership transfer is deliberately not part of the generic role-update endpoint. This
prevents accidental creation or removal of owners before a dedicated ownership-transfer
workflow is designed.


## Request workflow and SLA engine

SLADeck requests are organization-scoped operational records with a requester, optional
assignee, priority, status and required SLA policy.

Implemented request statuses:

- `open`
- `in_progress`
- `waiting`
- `resolved`
- `closed`

Implemented priorities:

- `urgent`
- `high`
- `normal`
- `low`

The SLA engine is independent from FastAPI and persistence. It receives the request
creation timestamp, priority and SLA policy durations and returns first-response and
resolution deadlines.

Priority scales the policy's base durations:

| Priority | SLA factor |
| --- | ---: |
| urgent | 0.25x |
| high | 0.50x |
| normal | 1.00x |
| low | 2.00x |

The API exposes SLA state as `healthy`, `warning`, `breached` or `completed`.
Before the first response, SLA health is calculated against the first-response deadline;
after a first response, it is calculated against the resolution deadline.

Deadlines are stored as a snapshot on each request. Editing an SLA policy does not
retroactively rewrite existing request deadlines. A request recalculates its deadlines
when its own priority or SLA policy changes.

Tenant safety is enforced twice: API queries require organization membership, and the
database prevents a request from referencing an assignee or SLA policy belonging to a
different organization.

### SLA policy endpoints

- `GET /organizations/{organization_id}/sla-policies`
- `POST /organizations/{organization_id}/sla-policies`
- `GET /organizations/{organization_id}/sla-policies/{policy_id}`
- `PATCH /organizations/{organization_id}/sla-policies/{policy_id}`
- `DELETE /organizations/{organization_id}/sla-policies/{policy_id}`

Policies in use cannot be deleted.

### Request endpoints

- `GET /organizations/{organization_id}/requests`
- `POST /organizations/{organization_id}/requests`
- `GET /organizations/{organization_id}/requests/{request_id}`
- `PATCH /organizations/{organization_id}/requests/{request_id}`
- `DELETE /organizations/{organization_id}/requests/{request_id}`
- `POST /organizations/{organization_id}/requests/{request_id}/first-response`

Request listing supports filters for status, priority and assignee.


## Comments and immutable audit trail

Requests now have a chronological collaboration and audit history.

Any organization member can add and read request comments:

- `GET /organizations/{organization_id}/requests/{request_id}/comments`
- `POST /organizations/{organization_id}/requests/{request_id}/comments`

The combined activity timeline is available at:

- `GET /organizations/{organization_id}/requests/{request_id}/activity`

The audit trail records important request lifecycle events, including:

- request creation;
- first response;
- status changes;
- priority changes;
- assignee changes;
- SLA policy changes;
- comment creation.

Audit events are append-only. SLADeck does not expose update/delete APIs for audit events,
and PostgreSQL also installs a trigger that rejects direct `UPDATE` or `DELETE` operations
against the `audit_events` table.

Requests are retained for audit history, so the normal request API no longer physically
deletes them. A request should be completed through the `resolved` / `closed` status
workflow instead.

Comments and audit records are constrained to the same organization and request at the
database level, preserving tenant isolation even if application code is changed later.


## Background SLA worker

SLA deadline checks now run outside the HTTP request/response path.

SLADeck uses:

- **Redis** as the Celery broker/result backend;
- **Celery worker** for asynchronous SLA checks;
- **Celery Beat** for the recurring one-minute schedule;
- PostgreSQL for durable notification records and audit events.

The worker evaluates active requests and creates at most one notification for each request/stage/kind combination:

- `first_response` + `warning`;
- `first_response` + `breached`;
- `resolution` + `warning`;
- `resolution` + `breached`.

Idempotence is enforced at the database level with a unique constraint, so retrying the same scheduled job does not create duplicate escalation records. Worker-created escalations are also written to the immutable audit trail.

The notification history is available at:

- `GET /organizations/{organization_id}/requests/{request_id}/sla-notifications`

### Run the worker locally

Start Redis first, then run the API and worker processes separately.

```bash
redis-server
```

Worker:

```bash
cd backend
celery -A sladeck.worker.celery_app worker --loglevel=INFO
```

Scheduler:

```bash
cd backend
celery -A sladeck.worker.celery_app beat --loglevel=INFO
```

Only one Beat scheduler should own a given periodic schedule in a deployment.
