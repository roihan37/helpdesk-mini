# HelpDesk Mini

HelpDesk Mini is a multi-tenant support-ticket application being built for the SVO Connect Junior Developer technical assessment.

## Implementation Status

M0 provides a verified project foundation: a minimal Next.js frontend, a FastAPI health endpoint, typed environment settings, PostgreSQL connectivity, and Alembic configuration. Authentication, domain models, ticket management, and WebSocket behavior are intentionally not implemented yet.

See [ARCHITECTURE.md](ARCHITECTURE.md), [requirements](docs/REQUIREMENTS.md), [security](docs/SECURITY.md), and the [API contract](docs/API_CONTRACT.md) for the planned application behavior.

## Prerequisites

The M0 checks were run with:

- Node.js 24.18.0 and npm 11.16.0.
- Python 3.12.12 managed by `uv`.
- PostgreSQL 17 for the connectivity and Alembic smoke checks.

Python 3.11 or later is supported. A PostgreSQL database and role matching `DATABASE_URL` must exist before running the database checks.

## Environment Configuration

Use the backend section of [`.env.example`](.env.example) to create an ignored `backend/.env`, and the frontend section to create an ignored `frontend/.env.local`. Replace `JWT_SECRET` with a strong local value; the application has no fallback secret.

`CORS_ORIGINS` is a comma-separated list of explicit origins, for example:

```dotenv
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Wildcard origins are not supported because the browser authentication design uses credentials. The documented JWT strategy remains: access tokens live only in frontend memory, while refresh tokens use an HttpOnly cookie with `SameSite=Lax`, `Path=/auth/refresh`, and `Secure` enabled under HTTPS. M0 defines only the configuration contract; it does not issue or validate tokens.

## Backend Setup

Run from `backend/`:

```bash
uv sync --all-groups
uv run python -m app.db.check
uv run alembic current
uv run alembic heads
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The intentionally public health endpoint is available at `http://127.0.0.1:8000/health` and returns only `{"status":"ok"}`.

Backend validation commands:

```bash
uv run python -m compileall -q app alembic
uv run ruff check app alembic
uv run mypy app
```

## Frontend Setup

Run from `frontend/`:

```bash
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

The foundation page is available at `http://127.0.0.1:3000/`.

Frontend validation commands:

```bash
npm run lint
npm run typecheck
npm run build
```

The production build intentionally uses Next.js's webpack builder. In the M0 execution environment, the default Turbopack production worker could not bind its internal port; the webpack build completed successfully.

## Technical Decisions

- The application remains a modular monolith with a Next.js client, one FastAPI backend, and PostgreSQL as the source of truth.
- Backend settings are required and typed. PostgreSQL URLs are validated, and SQLite is not used as a fallback.
- Credentialed CORS accepts only explicitly configured development origins.
- Alembic is connected to the shared SQLAlchemy metadata, but M0 deliberately contains no domain models or migration revisions.
- Mandatory security and functional flows take priority over optional infrastructure and UI polish.

## Known Limitations

- Authentication, RBAC, tenant isolation enforcement, ticket workflows, WebSocket chat, and product pages belong to later milestones.
- The Alembic heads list is empty because M0 does not create a domain migration.
- `npm audit --omit=dev` reports no runtime vulnerabilities. The full audit reports a high-severity `braces` advisory through the Next.js ESLint development-tooling chain; npm's proposed automatic fix is a breaking downgrade of `eslint-config-next`, so it was not applied.
- Database startup requires a locally provisioned PostgreSQL role and database matching `backend/.env`.

## Milestone Roadmap

| Milestone | Scope |
|---|---|
| M0 | Runnable frontend/backend foundation, PostgreSQL, Alembic, and verified setup |
| M1 | Database models and migrations |
| M2 | JWT authentication and securely scoped business user management |
| M3 | Comprehensive tenant-authorization audit and isolation tests |
| M4 | Ticket management |
| M5 | WebSocket chat |
| M6 | Required frontend flows |
| M7 | Final tests, seed data, documentation, and demo preparation |
