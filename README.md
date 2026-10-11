# HelpDesk Mini

HelpDesk Mini is a multi-tenant support-ticket application being built for the SVO Connect Junior Developer technical assessment.

## Implementation Status

M0 provides the project foundation, M1 provides the PostgreSQL domain models and initial Alembic
migration, M2 provides verified JWT authentication plus tenant-scoped Admin user management, and
M3 provides verified reusable role and ticket-resource authorization policies. M4 provides
verified Ticket REST workflows for creation, scoped listing/detail, assignment, and status
lifecycle management. M5 provides verified persistent message history and authenticated,
ticket-scoped WebSocket chat with post-commit message and status events. M6 provides the verified
responsive Next.js authentication, Ticket, real-time chat, and Admin Team interfaces, including
real-browser role, tenant-isolation, reconnect, and two-client WebSocket workflows.
M7 adds a safe, repeatable demo seed and reviewer-facing setup/demo documentation. The final M7
audit reran the backend, PostgreSQL, frontend, migration, seed, browser, security, and repository
quality gates. The milestone remains active pending final-revision setup verification, formal
assistive-technology/contrast evidence, and the 3-5 minute demo recording.

See [ARCHITECTURE.md](ARCHITECTURE.md), [requirements](docs/REQUIREMENTS.md), [security](docs/SECURITY.md), and the [API contract](docs/API_CONTRACT.md) for the planned application behavior.

## One-command Docker demo (recommended for reviewers)

Prerequisites: Docker Engine with the Docker Compose plugin, or Docker Desktop, running with
ports 3000, 8000, and 5433 free. From the repository root:

```bash
docker compose up --build -d
docker compose ps
```

No `.env` files, local Python/Node/PostgreSQL installation, or password prompts are required.
The first build downloads dependencies and can take several minutes. PostgreSQL becomes healthy,
the backend runs Alembic migrations and the existing demo seed, then the production Next.js
frontend starts. Tests do **not** run during normal startup.

- Login: **http://localhost:3000/login**
- Backend: http://localhost:8000/health; Swagger: http://localhost:8000/docs
- Shared password for all eight accounts below: **`HelpdeskDemo2026!`**
- Fresh demo: 2 businesses, 8 users, 5 tickets, and 7 messages.

Use `localhost` consistently in the browser. The frontend uses `http://localhost:8000` for REST
and `ws://localhost:8000` for WebSocket connections; these are browser URLs, not Docker service
names. Explicit credentialed CORS and the HttpOnly, SameSite=Lax refresh cookie remain enabled.
The backend runs one worker because ticket-room broadcasts use an in-memory connection manager.

Run the existing backend suite, migrations, and schema-drift check explicitly:

```bash
docker compose --profile test run --build --rm tests
```

The test profile uses a separate `test-db` service and a disposable `helpdesk_compose_test`
database in tmpfs, with all test database URLs pointing there. It does not connect to or seed
the demo database. Migration downgrade tests operate only on that disposable database.

```bash
docker compose logs backend
docker compose stop
docker compose up -d
docker compose restart
docker compose down
```

`stop`, `restart`, and `down` without `--volumes` preserve demo data. Named volumes
`demo_postgres_data` and `demo_backend_state` retain PostgreSQL data and an automatically generated
private JWT signing secret. On restart, the complete demo identity manifest is detected and seed
is skipped: edited users, passwords, tickets, and messages are not reset or duplicated. An
incomplete/nonempty database without the manifest is rejected rather than modified automatically.
Do not use `down --volumes` if you want to keep data. The previous Compose `postgres_data` volume
is not reused or deleted; this demo uses its own database and volumes.

**Local demo only:** these public account/database credentials and HTTP cookie settings must
never be used in production. All published ports are bound to loopback. Automatic initialization
accepts only the fixed Compose `db:5432/helpdesk_mini_demo` target and demo database role; external
or production targets are rejected. `.env.compose` is no longer required or consumed. For other
environments, use the manual setup below with private credentials and an appropriate secure
configuration; do not use the demo entrypoint.

## Manual setup prerequisites

The M0 checks were run with:

- Node.js 24.18.0 and npm 11.16.0.
- Python 3.12.12 managed by `uv`.
- PostgreSQL 17 for the connectivity and Alembic smoke checks.

Python 3.11 or later is supported. A PostgreSQL database and role matching `DATABASE_URL` must exist before running the database checks.

From a fresh local PostgreSQL installation, create separate development and disposable test
databases. The commands prompt for the role password and do not put it in shell history:

```bash
createuser --pwprompt helpdesk_user
createdb --owner=helpdesk_user helpdesk_mini
createdb --owner=helpdesk_user helpdesk_m7_test
```

If the role or databases already exist, reuse them only after confirming their purpose. Commands
that downgrade migrations or run integration tests must target the disposable `*_test` database,
never development or valuable data.

## Environment Configuration

From the repository root, copy the tracked template into the two ignored local files:

```bash
cp .env.example backend/.env
cp .env.example frontend/.env.local
```

Replace `USER`, `PASSWORD`, and `JWT_SECRET` in `backend/.env`. The application has no fallback
JWT secret. Set `REFRESH_COOKIE_SECURE=false` only for local HTTP development and `true` when
serving over HTTPS. The backend ignores the frontend-only variables and Next.js exposes only the
two `NEXT_PUBLIC_*` values from `frontend/.env.local`.

`CORS_ORIGINS` is a comma-separated list of explicit origins, for example:

```dotenv
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Wildcard origins are not supported because the browser authentication design uses credentials. Access tokens are returned for in-memory frontend use. Login also places the refresh token in an HttpOnly cookie with `SameSite=Lax`, `Path=/auth/refresh`, and environment-controlled `Secure`. Browser refresh and logout requests with an `Origin` header are checked against `CORS_ORIGINS`. Logout expires that cookie and the frontend clears its in-memory access token; stateless JWT copies are not revoked server-side.

## Backend Setup

Run from `backend/`:

```bash
uv sync --all-groups
uv run python -m app.db.check
uv run alembic upgrade head
uv run alembic heads
DEMO_SEED_PASSWORD='<local-demo-only-password>' uv run python -m app.scripts.seed_demo --confirm-demo-data
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

The seed requires explicit acknowledgement, a password of at least 12 characters, and a named
PostgreSQL target. It refuses obvious production/system database names, never truncates tables,
and aborts on incompatible existing demo keys. Rerunning it with the same password is idempotent;
it preserves unrelated rows. Inspect `DATABASE_URL` before confirming. Never save real or
production credentials in Git, environment templates, screenshots, or recordings. The public
Docker demo password above is deliberately demo-only.

The intentionally public health endpoint is available at `http://127.0.0.1:8000/health` and returns only `{"status":"ok"}`. Swagger UI is available at `http://127.0.0.1:8000/docs`.

M2 endpoints are:

- `POST /auth/register-business`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /users`
- `POST /users`

M4 Ticket endpoints are:

- `GET /tickets` with optional `status` filtering
- `POST /tickets`
- `GET /tickets/{id}`
- `PATCH /tickets/{id}`
- `GET /tickets/{id}/messages`

M5 WebSocket chat is available at
`WS /ws/tickets/{id}?token=<access-token>`. Browser connections must send an `Origin` that exactly
matches `CORS_ORIGINS`. Agent and owning Customer connections may send `message.send`; Admin
connections are read-only. The server emits `message.created`, `ticket.status_changed`, and
sanitized `error` events.

These endpoints require access-token authentication. Ticket queries are tenant-scoped, Customer
access is ownership-scoped, and inaccessible cross-tenant or cross-Customer ticket IDs return 404.

### Live ticket-list activity (B4)

The frontend maintains one authenticated `WS /ws/tickets?token=<access-token>` subscription per
session, separate from ticket-detail chat. Committed creation, messages, status, and assignment
changes emit minimal activity events. Admin/Agent receive only own-business activity; Customers
receive only their own tickets. JWT expiration and current database membership/role are checked
before delivery. Existing Origin restrictions apply.

Events invalidate the existing ticket-list queries with 250 ms coalescing, preserving page,
search, status filters, and database sorting. A short generic inline notice avoids exposing
message content. Reconnect refetches missed activity; token replacement and logout clean up the
subscription. No unread badges or notification center are added.

For Postman refresh testing, use the cookie jar populated by `/auth/login`; `/auth/refresh` does not accept a refresh token in the JSON body.

### Login rate limiting

`POST /auth/login` permits five failed attempts per sliding 15-minute window for each
normalized (trimmed, lowercase) email + client IP. The first five invalid attempts return the
same generic 401 for registered and unknown emails; subsequent attempts return the standard
`AUTH_RATE_LIMITED` 429 error with a positive `Retry-After` in seconds. Successful logins do not
erase recent failures. An additional per-IP limit counts body-parsed login requests, including
successful logins and schema-invalid payloads. Malformed JSON is rejected before the limiter;
this is not a general HTTP denial-of-service control. Allowed browser origins can read
`Retry-After` through CORS.

| Environment variable | Default |
|---|---|
| `LOGIN_MAX_FAILED_ATTEMPTS` | `5` |
| `LOGIN_FAILED_WINDOW_SECONDS` | `900` |
| `LOGIN_IP_MAX_REQUESTS` | `30` |
| `LOGIN_IP_WINDOW_SECONDS` | `60` |

All values must be positive integers. Docker Compose accepts the same overrides. Limits use
the ASGI peer IP, not client-supplied `X-Forwarded-For`, `X-Real-IP`, or `Forwarded` headers.
Docker and the startup command above disable proxy-header processing. If deploying behind a
proxy, enable it only with an explicit, narrowly scoped trusted-proxy allowlist; never trust `*`.
Without this, users behind the proxy share its IP limit.

The limiter is thread-safe but process-local: run one backend worker, as already required by
WebSocket rooms. Restarting clears limits; workers/instances do not share them. Shared NAT IPs
share the request cap, and rotating source IPs are not fully mitigated. State is bounded to
10,000 live keys; at capacity, new keys fail closed with 429 rather than evicting active limits.

## Demo Data and Accounts

In the Docker demo, all eight accounts use **`HelpdeskDemo2026!`**, supplied only through the demo
seed configuration and stored as Argon2 hashes. For manual setup, they use the local-only password
you supply as `DEMO_SEED_PASSWORD`; authentication has no demo password bypass.

| Business | Slug | Role | Email |
|---|---|---|---|
| Northstar Support | `demo-northstar` | Admin | `admin@northstar.helpdeskmini.dev` |
| Northstar Support | `demo-northstar` | Agent | `agent@northstar.helpdeskmini.dev` |
| Northstar Support | `demo-northstar` | Customer | `customer1@northstar.helpdeskmini.dev` |
| Northstar Support | `demo-northstar` | Customer | `customer2@northstar.helpdeskmini.dev` |
| Orbit Services | `demo-orbit` | Admin | `admin@orbit.helpdeskmini.dev` |
| Orbit Services | `demo-orbit` | Agent | `agent@orbit.helpdeskmini.dev` |
| Orbit Services | `demo-orbit` | Customer | `customer1@orbit.helpdeskmini.dev` |
| Orbit Services | `demo-orbit` | Customer | `customer2@orbit.helpdeskmini.dev` |

The manifest also creates five tickets and seven messages: a Northstar open/unassigned chat
ticket (`30000000-0000-4000-8000-000000000001`), an assigned ticket with history, resolved and
closed restriction examples, and an Orbit isolation ticket
(`30000000-0000-4000-8000-000000000005`). These stable IDs are demo data, not credentials.

Backend validation commands:

```bash
uv run python -m compileall -q app alembic tests
uv run ruff check app alembic tests
uv run ruff format --check app alembic tests
uv run mypy app tests
uv run pytest -q tests/test_login_rate_limit.py tests/test_auth.py --tb=short
```

The full test suite includes destructive migration checks and therefore requires
`DATABASE_URL`, `TEST_DATABASE_URL`, and `M1_TEST_DATABASE_URL` to point to an explicitly
disposable PostgreSQL database whose name ends in `_test`. The verified local command below derives
that URL without printing credentials. Change its database name to the disposable database you
created if necessary. Never run these tests against a development or production
database.

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m7_test'); assert url.get_backend_name() == 'postgresql' and (url.database or '').endswith('_test'); test_url=url.render_as_string(hide_password=False); os.environ['DATABASE_URL']=test_url; os.environ['TEST_DATABASE_URL']=test_url; os.environ['M1_TEST_DATABASE_URL']=test_url; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','--tb=short']))"
```

M5 Phase 4 ran the equivalent guarded setup against the disposable `helpdesk_m5_test` database.
The focused M5 suite passed 25 tests, the M2-M4 regression selection passed 112 tests, and the full
backend suite passed 137 tests. Compile/import, Ruff lint/format, strict mypy, single-head Alembic,
and schema-drift checks also passed. One upstream TestClient deprecation warning remains. Exact
commands and results are recorded in the completed M5 execution plan.

M6 frontend integration must load REST history before opening one Ticket socket per mounted detail
view, reconcile `message.created` events by Message ID, and reload history after reconnect. It must
handle `message.created`, `ticket.status_changed`, and `error`, render message bodies as text, clean
up sockets during navigation, and disable Admin/closed-Ticket message input without treating UI
restrictions as authorization controls.

## Frontend Setup

Run from `frontend/`:

```bash
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

The frontend is available at `http://127.0.0.1:3000/`. It requires the FastAPI backend at the
`NEXT_PUBLIC_API_URL` configured in `frontend/.env.local`. Required routes are `/login`, `/register`,
`/tickets`, `/tickets/new`, `/tickets/[id]`, and `/admin/users`.

Frontend validation commands:

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm audit --omit=dev
```

M6 Phase 4 verified ESLint, strict typecheck, three focused domain tests, and the production webpack
build. It also exercised the six required routes, role and tenant isolation, Customer Ticket
creation, Admin assignment, Agent status workflows, exact 320/375/768/1440px layouts, WebSocket
disconnect/retry, and two-browser Customer/Agent chat against FastAPI and PostgreSQL. The full
backend regression suite passed 139 tests on a migrated disposable database. No checked-in browser
E2E framework exists; the mandatory matrix was run through actual browser sessions rather than
inferred from unit tests or build success. Exact evidence is in the completed M6 execution plan.
The production build intentionally uses Next.js's webpack builder.

### B4 verification evidence

Executed against a newly created, disposable `helpdesk_b4_test` PostgreSQL database, not demo
data. The Compose test runner applies Alembic migrations, runs pytest, and checks schema drift:

```bash
docker compose --profile test exec -T test-db createdb -U helpdesk_test helpdesk_b4_test
docker compose --profile test run --build --rm \
  -e DATABASE_URL=postgresql+psycopg://helpdesk_test:local-test-only@test-db:5432/helpdesk_b4_test \
  -e TEST_DATABASE_URL=postgresql+psycopg://helpdesk_test:local-test-only@test-db:5432/helpdesk_b4_test \
  -e M1_TEST_DATABASE_URL=postgresql+psycopg://helpdesk_test:local-test-only@test-db:5432/helpdesk_b4_test tests
```

Result: **214 backend tests PASS**, migrations/schema-drift check PASS. `local-test-only` is the
public disposable Compose test password, not a production credential. The first run against an
existing test database had 212 PASS / 2 FAIL because seed tests require an empty database; prior
browser fixtures were preserved, and the fresh database rerun passed. For another full run,
create a new explicitly disposable `*_test` database rather than clearing existing data.

From `backend/`, `.venv/bin/ruff check app tests` and `.venv/bin/mypy app` passed. From
`frontend/`, `npm test` passed 17 tests, and `npm run typecheck`, `npm run lint`, and
`npm run build` passed. Tests cover committed activity, minimal payloads, tenant/Customer
isolation, invalid/expired/refresh-token rejection, failed-commit suppression, concurrent list
delivery, cleanup, reconnect, token replacement, deduplication, and B3 search/pagination.
Final review reproduced a stale-response race when activity arrived during an existing list
request (16 PASS / 1 FAIL). Invalidation now supersedes that pre-event request; the added
regression and the full frontend rerun passed (17 PASS / 0 FAIL).

A real Chrome session against FastAPI/PostgreSQL verified that an external committed status
and assignment change updates `/tickets` without refresh while preserving active search/status
filters. A new automated two-independent-browser B4 scenario was **NOT RUN**; real two-client
FastAPI WebSocket integration is covered by pytest, not claimed as browser E2E. To verify this
manually, open separate Customer/Agent browser profiles, keep the Agent on `/tickets`, create a
Customer ticket and send a message, then verify list activity/order and status/assignment changes
without reload. Repeat with Orbit and another Customer to confirm no unauthorized notices.

## Demo Checklist

Use two isolated browser profiles and keep the backend at one worker. The target recording is 3-5
minutes:

1. Show Northstar and Orbit as separate businesses; open Northstar Customer 1 and Agent sessions.
2. Customer 1 creates a ticket with its first message.
3. The Agent sees and self-assigns the ticket.
4. Customer and Agent exchange messages without refreshing; reload once to prove persistence.
5. The Agent changes status and the Customer sees the committed update in real time.
6. Close a ticket and show that further messages are disabled/rejected.
7. While authenticated to Northstar, request the seeded Orbit ticket ID and show the non-disclosing 404.

Demo video: **pending final recording and reviewer-access verification**. Do not replace this
text with a URL until the recording exists and access has been tested.

## Catatan

### Technical decisions

- The application remains a modular monolith with a Next.js client, one FastAPI backend, and PostgreSQL as the source of truth.
- Backend settings are required and typed. PostgreSQL URLs are validated, and SQLite is not used as a fallback.
- Credentialed CORS accepts only explicitly configured development origins.
- Alembic is connected to the shared SQLAlchemy metadata and M1 provides the initial domain migration.
- Protected M2 requests validate token type and resolve current role and business membership from PostgreSQL instead of authorizing from JWT claims alone.
- Reusable M3 policies scope ticket lookup by the trusted current User's business and additionally
  enforce Customer ownership. Assignment and status actor policies preserve non-disclosing 404
  behavior for inaccessible tickets and related resources.
- M4 keeps Ticket routers thin and applies creation, list, detail, assignment, lifecycle, rollback,
  and PostgreSQL row-lock rules in the service layer. Ticket creation persists the first Message
  in the same transaction, while competing Agent claims are serialized on the Ticket row.
- M5 keeps WebSocket authentication and Ticket authorization database-backed, uses short-lived
  sessions for handshake and send operations, persists each Message with the Ticket activity
  timestamp before broadcasting, and isolates connections by Ticket room.
- M6 keeps bearer access tokens in memory, restores sessions through the credentialed HttpOnly
  refresh cookie, centralizes typed REST errors, and loads persisted Ticket history before opening
  one native WebSocket per mounted Ticket detail view.
- Mandatory security and functional flows take priority over optional infrastructure and UI polish.

### Known limitations and unfinished work

- Refresh tokens are stateless and are not rotated or immediately revocable in M2.
- Login limits are in memory, reset on restart, and do not span backend workers or instances;
  see the login rate-limiting section for proxy, shared-IP, and capacity limitations.
- Refresh-cookie headers and CORS behavior are covered by TestClient, but persistence and
  SameSite/Secure behavior have not been manually verified in a real browser deployment.
- M5 chat and B4 list activity use an in-memory connection manager and require one backend worker.
  Live delivery does not span processes/instances and has no durable outbox. A crash between
  commit and broadcast can delay visibility until history is reloaded or the list reconnects/refetches.
- Idle WebSocket connections are not continuously reauthenticated. Authentication, current User,
  role, tenant/ownership access, and Ticket status are revalidated on each message send. B4 also
  revalidates token expiration and current User role/business/ownership before each list delivery.
- Same-business Customer/assignee integrity cannot be fully expressed by the existing foreign keys
  and remains an application-service invariant. Future Ticket writers must follow the same row-lock
  discipline used by M4 for competing state changes.
- `npm audit --omit=dev` reports no runtime vulnerabilities. The full audit reports a high-severity `braces` advisory through the Next.js ESLint development-tooling chain; npm's proposed automatic fix is a breaking downgrade of `eslint-config-next`, so it was not applied.
- The mandatory M6 browser matrix was verified manually through browser automation, but the
  repository does not yet include a dedicated browser-E2E suite. A dedicated VoiceOver or other
  assistive-technology pass was not run; keyboard, focus, semantics, and responsive checks passed.
- Manual startup requires a locally provisioned PostgreSQL role and database matching
  `backend/.env`; the Docker demo provisions its own isolated database automatically.
- M7 final audit passed the complete backend/frontend gates, disposable PostgreSQL migration and
  seed checks, real-browser E2E/security flows, and a measured working-candidate setup rehearsal.
  A dedicated assistive-technology/contrast pass, a 3-5 minute demo recording, and verification
  from the immutable final revision remain outstanding, so M7 is not complete.

## Milestone Roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 | Runnable frontend/backend foundation, PostgreSQL, Alembic, and verified setup | Complete |
| M1 | Database models and migrations | Complete |
| M2 | JWT authentication and securely scoped business user management | Complete |
| M3 | Comprehensive tenant-authorization audit and isolation tests | Complete |
| M4 | Ticket management | Complete |
| M5 | WebSocket chat | Complete |
| M6 | Required frontend flows | Complete |
| M7 | Final tests, seed data, documentation, and demo preparation | Final audit complete; pending final evidence |
