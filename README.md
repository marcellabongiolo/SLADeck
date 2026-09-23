# SLADeck

SLADeck is a full-stack SaaS project for teams that manage incoming requests, ownership, priorities and service-level deadlines.

The project is being built as a multi-tenant product with a Python/FastAPI backend, PostgreSQL, Redis-backed background work and a Next.js/TypeScript frontend.

> Status: early development. Features are documented as implemented only after they are merged and covered by tests.

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
