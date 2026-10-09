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

- [ ] Frontend starts successfully.
- [ ] Backend starts successfully.
- [ ] PostgreSQL configuration is valid.
- [ ] Alembic is configured correctly.
- [ ] Environment configuration is documented.
- [ ] No real secrets are exposed.
- [ ] Basic validation commands succeed.
- [ ] README contains verified setup instructions.

## Validation Record

Record each executed command, date, result, and relevant failure detail here during M0. Do not mark a check successful without executing it.

## Definition of Done

- [ ] All acceptance criteria are checked with evidence.
- [ ] Relevant validation results are recorded.
- [ ] Known limitations are documented.
- [ ] No critical security issue is introduced.
- [ ] M0 is reviewed before moving this plan to `exec-plans/completed/` or beginning M1.
