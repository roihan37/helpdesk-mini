# M0 - Project Foundation

## Objective

Prepare the initial runnable development foundation for Next.js, FastAPI, PostgreSQL, and Alembic without implementing domain features.

## Prerequisites

- Harness documentation is internally consistent and reviewed.
- Node.js/package-manager and Python 3.11+ versions are selected during implementation.
- A local PostgreSQL instance and non-production credentials are available.

## Scope

- Frontend project scaffolding.
- Backend project scaffolding.
- Environment configuration.
- PostgreSQL connection configuration.
- Initial Alembic configuration.
- Basic application startup.
- Initial README setup instructions.
- Relevant smoke checks.

## Out of Scope

Do not implement business registration, JWT authentication, user management, database domain models, ticket CRUD, WebSocket chat, advanced frontend pages, or bonus features. These belong to later milestones.

## Security Considerations

- Load configuration from ignored local environment files; commit examples only.
- Do not add fallback JWT secrets or real database credentials.
- Configure CORS only for explicit development origins.
- M0 health/startup routes must not expose configuration or secrets.
- Do not create protected endpoints before their authentication and authorization controls exist.

## Implementation Tasks

### M0-01 - Scaffold the frontend

- **Objective:** Create the minimal Next.js App Router TypeScript application with Tailwind CSS.
- **Files involved:** `frontend/package.json`, lockfile, Next.js/TypeScript/Tailwind configuration, minimal `frontend/src/app/` files.
- **Dependencies:** Supported Node.js runtime and chosen package manager.
- **Acceptance criteria:** Development server starts; the root page renders; generated files remain minimal; no product pages or auth flows are added.
- **Verification commands:** Package-manager install, lint, type-check (if separate), build, and development startup command recorded from the generated project.

### M0-02 - Scaffold the backend

- **Objective:** Create a minimal importable FastAPI application and Python project configuration.
- **Files involved:** `backend/pyproject.toml`, dependency lock or requirements artifact, `backend/app/__init__.py`, `backend/app/main.py`.
- **Dependencies:** Python 3.11+ and an isolated virtual environment.
- **Acceptance criteria:** Application imports cleanly; an intentionally public health endpoint returns a non-sensitive success response; no domain endpoints exist.
- **Verification commands:** Dependency installation, `python -m compileall backend/app`, configured lint/type checks, and `uvicorn app.main:app --reload` from `backend/`.

### M0-03 - Add typed environment configuration

- **Objective:** Load and validate the documented backend settings and expose frontend public URLs through framework conventions.
- **Files involved:** `.env.example`, ignored `backend/.env`, ignored `frontend/.env.local`, backend settings module, relevant framework configuration.
- **Dependencies:** M0-01 and M0-02.
- **Acceptance criteria:** Required values fail clearly when absent; no insecure secret defaults exist; variable names match the documentation; local environment files are untracked.
- **Verification commands:** Start each application with valid local values; run `git check-ignore backend/.env frontend/.env.local`; inspect tracked files for secrets.

### M0-04 - Configure PostgreSQL connectivity

- **Objective:** Configure SQLAlchemy engine and session infrastructure against PostgreSQL without adding domain models.
- **Files involved:** backend settings and database modules; backend dependency manifest.
- **Dependencies:** M0-02 and M0-03; reachable PostgreSQL instance.
- **Acceptance criteria:** A smoke check establishes and closes a database connection; failures do not expose credentials; no SQLite fallback is silently used.
- **Verification commands:** Run the documented database connectivity smoke check with the local `DATABASE_URL`.

### M0-05 - Initialize Alembic

- **Objective:** Add Alembic configuration wired to application metadata and environment settings.
- **Files involved:** `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/`.
- **Dependencies:** M0-03 and M0-04.
- **Acceptance criteria:** Alembic loads configuration and connects to PostgreSQL; no domain migration is created; migrations directory is preserved.
- **Verification commands:** Run `alembic current` and `alembic heads` from `backend/`.

### M0-06 - Verify startup and document setup

- **Objective:** Exercise both applications and replace provisional README guidance with verified setup instructions.
- **Files involved:** `README.md` and only files needed to correct startup issues.
- **Dependencies:** M0-01 through M0-05.
- **Acceptance criteria:** Frontend and backend start together against configured PostgreSQL; backend health and frontend root respond; commands are recorded exactly as executed.
- **Verification commands:** Run frontend lint/type/build checks, backend syntax/import checks, Alembic checks, database smoke check, and manual HTTP startup smoke checks.

## Acceptance Criteria

- [x] Frontend starts successfully.
- [x] Backend starts successfully.
- [x] PostgreSQL configuration is valid.
- [x] Alembic is configured correctly.
- [x] Environment configuration is documented.
- [x] No real secrets are exposed.
- [x] Basic validation commands succeed.
- [x] README contains verified setup instructions.

## Validation Record

Executed on 2026-10-09.

### Dependency and configuration checks

- `cd backend && uv sync --all-groups` - PASS; Python 3.12.12 environment and lockfile created.
- `cd frontend && npm install` - PASS; package lock is current.
- Backend settings checks with valid values, missing required values, and comma-separated `CORS_ORIGINS` - PASS. Missing values fail validation, and comma-separated origins produce the expected URL list.
- `git check-ignore backend/.env frontend/.env.local` - PASS; both local configuration files are ignored.
- Repository scan excluding ignored local environment files and generated dependency/build directories - PASS; no real private key or local JWT secret was found in project files.

### Frontend checks

- `cd frontend && npm run lint` - PASS.
- `cd frontend && npm run typecheck` - PASS.
- `cd frontend && npm run build` - PASS; Next.js 16.4.0 produced a static `/` route using webpack.
- `cd frontend && npm run dev -- --hostname 127.0.0.1 --port 3000` - PASS; started while the backend was running.
- `curl --fail --silent --show-error --output /private/tmp/helpdesk-mini-frontend-smoke.html --write-out 'frontend_status=%{http_code}\n' http://127.0.0.1:3000/` - PASS; returned HTTP 200.
- `cd frontend && npm audit --omit=dev` - PASS; zero runtime vulnerabilities reported.
- `cd frontend && npm audit` - FAIL; five high-severity findings are one transitive `braces` advisory in the Next.js ESLint development-tooling chain. The suggested forced fix would install the incompatible `eslint-config-next@14.2.35`, so it was not applied.

The first default `next build` attempt used Turbopack and failed when its internal worker could not bind a port in the execution environment. The checked-in build command uses Next.js's supported webpack builder; the final production build passed.

### Backend checks

- `cd backend && uv run python -m compileall -q app alembic` - PASS.
- `cd backend && uv run ruff check app alembic` - PASS.
- `cd backend && uv run mypy app` - PASS; eight source files checked.
- `cd backend && uv run python -c 'from app.main import app; assert app.title == "HelpDesk Mini API"'` - PASS.
- `cd backend && DATABASE_URL=postgresql+psycopg://helpdesk:helpdesk@127.0.0.1:55432/helpdesk_mini uv run python -m app.db.check` - PASS against a disposable PostgreSQL 17 instance; the connection was opened and closed without exposing credentials.
- `cd backend && DATABASE_URL=postgresql+psycopg://helpdesk:helpdesk@127.0.0.1:55432/helpdesk_mini uv run alembic current` - PASS; PostgreSQL configuration loaded and connected.
- `cd backend && DATABASE_URL=postgresql+psycopg://helpdesk:helpdesk@127.0.0.1:55432/helpdesk_mini uv run alembic heads` - PASS with no output, as expected before the M1 domain migration.
- `cd backend && DATABASE_URL=postgresql+psycopg://helpdesk:helpdesk@127.0.0.1:55432/helpdesk_mini uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` - PASS; started while the frontend was running.
- `curl --fail --silent --show-error --include --header 'Origin: http://localhost:3000' http://127.0.0.1:8000/health` - PASS; returned HTTP 200, `{"status":"ok"}`, the configured origin, and credential support.

The machine's existing service on PostgreSQL's default port did not accept the documented local development credentials. M0 database behavior was therefore verified against an isolated PostgreSQL 17 container on port 55432. Developers must provision the role and database named by their own `backend/.env`.

### Known limitations

- M0 intentionally contains no authentication, domain models, tickets, messages, WebSocket endpoint, or product pages.
- There is no Alembic revision until the M1 schema is implemented.
- The full npm audit retains the development-only transitive advisory described above; the runtime dependency audit is clean.
- M0 remains in `exec-plans/active/` pending review. No M1 work has started.

## Definition of Done

- [x] All acceptance criteria are checked with evidence.
- [x] Relevant validation results are recorded.
- [x] Known limitations are documented.
- [x] No critical security issue is introduced.
- [ ] M0 is reviewed before moving this plan to `exec-plans/completed/` or beginning M1.
