# HelpDesk Mini

HelpDesk Mini is a multi-tenant support-ticket application being built for the SVO Connect Junior Developer technical assessment.

## Implementation Status

M0 provides the project foundation, M1 provides the PostgreSQL domain models and initial Alembic migration, and M2 provides verified JWT authentication plus tenant-scoped Admin user management. Ticket APIs, WebSocket chat, and the product frontend are not implemented yet.

See [ARCHITECTURE.md](ARCHITECTURE.md), [requirements](docs/REQUIREMENTS.md), [security](docs/SECURITY.md), and the [API contract](docs/API_CONTRACT.md) for the planned application behavior.

## Prerequisites

The M0 checks were run with:

- Node.js 24.18.0 and npm 11.16.0.
- Python 3.12.12 managed by `uv`.
- PostgreSQL 17 for the connectivity and Alembic smoke checks.

Python 3.11 or later is supported. A PostgreSQL database and role matching `DATABASE_URL` must exist before running the database checks.

## Environment Configuration

Use the backend section of [`.env.example`](.env.example) to create an ignored `backend/.env`, and the frontend section to create an ignored `frontend/.env.local`. Replace `JWT_SECRET` with a strong local value; the application has no fallback secret. Set `REFRESH_COOKIE_SECURE=false` only for local HTTP development and `true` when serving over HTTPS.

`CORS_ORIGINS` is a comma-separated list of explicit origins, for example:

```dotenv
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Wildcard origins are not supported because the browser authentication design uses credentials. Access tokens are returned for in-memory frontend use. Login also places the refresh token in an HttpOnly cookie with `SameSite=Lax`, `Path=/auth/refresh`, and environment-controlled `Secure`. Browser refresh requests with an `Origin` header are checked against `CORS_ORIGINS`.

## Backend Setup

Run from `backend/`:

```bash
uv sync --all-groups
uv run python -m app.db.check
uv run alembic upgrade head
uv run alembic heads
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The intentionally public health endpoint is available at `http://127.0.0.1:8000/health` and returns only `{"status":"ok"}`. Swagger UI is available at `http://127.0.0.1:8000/docs`.

M2 endpoints are:

- `POST /auth/register-business`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`
- `GET /users`
- `POST /users`

For Postman refresh testing, use the cookie jar populated by `/auth/login`; `/auth/refresh` does not accept a refresh token in the JSON body.

Backend validation commands:

```bash
uv run python -m compileall -q app alembic tests
uv run ruff check app alembic tests
uv run ruff format --check app alembic tests
uv run mypy app tests
```

The full test suite includes destructive migration checks and therefore requires
`DATABASE_URL`, `TEST_DATABASE_URL`, and `M1_TEST_DATABASE_URL` to point to an explicitly
disposable PostgreSQL database whose name ends in `_test`. The verified local command below derives
that URL without printing credentials. Never run these tests against a development or production
database.

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m2_test'); test_url=url.render_as_string(hide_password=False); os.environ['DATABASE_URL']=test_url; os.environ['TEST_DATABASE_URL']=test_url; os.environ['M1_TEST_DATABASE_URL']=test_url; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','--tb=short']))"
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
- Alembic is connected to the shared SQLAlchemy metadata and M1 provides the initial domain migration.
- Protected M2 requests validate token type and resolve current role and business membership from PostgreSQL instead of authorizing from JWT claims alone.
- Mandatory security and functional flows take priority over optional infrastructure and UI polish.

## Known Limitations

- Refresh tokens are stateless and are not rotated or immediately revocable in M2.
- Refresh-cookie headers and CORS behavior are covered by TestClient, but persistence and
  SameSite/Secure behavior have not been manually verified in a real browser deployment.
- Ticket workflows, ticket-level tenant isolation, WebSocket chat, and product pages belong to later milestones.
- `npm audit --omit=dev` reports no runtime vulnerabilities. The full audit reports a high-severity `braces` advisory through the Next.js ESLint development-tooling chain; npm's proposed automatic fix is a breaking downgrade of `eslint-config-next`, so it was not applied.
- Database startup requires a locally provisioned PostgreSQL role and database matching `backend/.env`.

## Milestone Roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 | Runnable frontend/backend foundation, PostgreSQL, Alembic, and verified setup | Complete |
| M1 | Database models and migrations | Complete |
| M2 | JWT authentication and securely scoped business user management | Complete |
| M3 | Comprehensive tenant-authorization audit and isolation tests | Not started |
| M4 | Ticket management | Not started |
| M5 | WebSocket chat | Not started |
| M6 | Required frontend flows | Not started |
| M7 | Final tests, seed data, documentation, and demo preparation | Not started |
