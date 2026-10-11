# M7 - Final Verification & Submission

Status: **PHASE 2 IMPLEMENTED — pending Phase 3 verification**
Milestone owner: Engineering / QA / Security review  
Scope: Final verification, safe demo data, reproducible setup, demo preparation, and submission readiness.

## 1. Objective

Produce a reviewer-ready HelpDesk Mini submission whose mandatory behavior, security boundaries, setup process, and demo can be reproduced from a clean checkout. M7 is a verification and delivery milestone; it must not expand the product beyond the assessment requirements.

## 2. Phase 1 evidence and baseline

Phase 1 performed a read-only inspection of:

- `AGENTS.md`, `ARCHITECTURE.md`, and all required files under `docs/`.
- Completed M0-M6 execution plans, with detailed review of `exec-plans/completed/M6-frontend.md`.
- Backend models, migrations, routes, services, WebSocket implementation, and tests.
- Frontend routes, authentication handling, API/WebSocket integration, UI components, and tests.
- `README.md`, `.env.example`, dependency manifests, ignored environment files, Git status, remote, and commit history.

Baseline findings:

- M6 is recorded as **COMPLETE**, with all 16 mandatory M6 acceptance criteria marked PASS.
- M6 evidence records 139 passing backend tests against disposable PostgreSQL, plus passing frontend lint, typecheck, three domain tests, and production build.
- M6 browser verification records real backend/PostgreSQL flows at 320, 375, 768, and 1440 px, including two-session chat, status synchronization, tenant isolation, reconnect, and cleanup.
- All six required frontend routes exist: `/login`, `/register`, `/tickets`, `/tickets/new`, `/tickets/[id]`, and `/admin/users`.
- The current repository contains both `frontend/` and `backend/`, Alembic migration history, and a focused M0-M6 commit history.
- The working tree was clean at Phase 1 inspection time. Local `backend/.env`, `frontend/.env.local`, dependency, build, and cache directories are ignored and not tracked.
- `.env.example` contains placeholders rather than observed real credentials. The current backend CORS parser accepts the documented comma-separated `CORS_ORIGINS` value.
- No seed utility, demo-data manifest, or checked-in browser E2E framework was found.
- Phase 1 did not rerun application tests and does not claim fresh M7 validation. Prior milestone results are inherited evidence only and must be revalidated in Phases 2-4.

### Phase 2 implementation evidence — 2026-10-11

Phase 2 completed the approved submission-preparation work without changing application APIs or
starting Phase 3:

| Task | Result | Evidence |
| --- | --- | --- |
| M7-01 | COMPLETE | Reconfirmed clean Phase 1 baseline at commit `ad43617`, reviewed the focused M0-M6 history, and mapped mandatory requirements to final gates below. |
| M7-02 | COMPLETE | Added the transactional, idempotent `app.scripts.seed_demo` command with explicit confirmation, supplied-password validation, tenant relationship checks, conflict rollback, and protected-target refusal. |
| M7-03 | COMPLETE | Added PostgreSQL tests for the exact 2-business/8-user manifest, role distribution, password hashes, relationships, idempotence, unrelated-row preservation, rollback, and target guards. |
| M7-04 | COMPLETE for Phase 2 | Updated `.env.example` and README with consistent CORS origins, PostgreSQL setup, safe seed use, eight-account manifest, verified commands, demo checklist, decisions, and limitations. Clean-checkout timing remains a Phase 3 gate. |

Mandatory requirement traceability and final owners:

| Requirement area | Current evidence source | Final owner/gate |
| --- | --- | --- |
| JWT separation, password hashing, RBAC, tenant/customer isolation | M2-M5 implementation/tests and completed plans | M7-05 automated regressions and M7-08 security audit |
| Ticket creation, first message, listing, assignment, lifecycle, and closed restrictions | M4 tests and M6 browser evidence | M7-07 functional browser E2E |
| Persistent chat, room isolation, live messages/status, reconnect, cleanup | M5 tests and M6 two-session evidence | M7-07 functional E2E and M7-08 security audit |
| Six required responsive frontend routes and role UX | Frontend source/tests and M6 review | M7-07 and M7-09 browser/accessibility review |
| PostgreSQL schema and Alembic history | Backend migration and M1-M6 evidence | M7-05 migration/quality gate and M7-06 clean setup |
| Two-business/eight-user representative demo data | Phase 2 seed implementation and 34-test focused run | M7-05 regression, M7-06 fresh seed, and M7-10 demo |
| Reproducible setup and reviewer documentation | Phase 2 README and environment template | M7-06 timed clean-checkout rehearsal |
| Demo and repository submission readiness | Phase 2 checklist; video remains pending | M7-10 demo capture and M7-11 submission audit |

Phase 2 validation actually executed:

```text
PASS  cd backend && UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff format --check app/scripts tests/test_seed_demo.py
PASS  cd backend && UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff check app/scripts tests/test_seed_demo.py
PASS  cd backend && UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run mypy app/scripts tests/test_seed_demo.py
PASS  cd backend && UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m compileall -q app/scripts tests/test_seed_demo.py
PASS  cd backend && UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m app.scripts.seed_demo --help
PASS  focused PostgreSQL run on disposable `helpdesk_m5_test`: tests/test_seed_demo.py + tests/test_models.py — 34 passed
PASS  seed command executed twice on disposable `helpdesk_m5_test` — both reported 2 businesses, 8 users, 5 tickets, and 7 messages
PASS  `.env.example` comma-separated localhost/127.0.0.1 CORS value parsed into two explicit origins
PASS  git diff --check; local backend/frontend env files remain ignored; current-tree private-key/access-key marker scan returned no matches
FAIL  first sandboxed PostgreSQL attempt — local port access was denied by the execution sandbox; no application assertion ran
FAIL  first database-wrapper retry — inspection wrapper imported the wrong settings module; corrected before any database write
FAIL  safety assertion against the configured development database — correctly stopped before writes because the target did not end in `_test`
FIXED initial protected-target regex did not recognize hyphenated production names; corrected and covered by regression tests
```

The successful integration command derived the disposable target from configured connection
settings without printing its credentials and assigned it to `DATABASE_URL`, `TEST_DATABASE_URL`,
and `M1_TEST_DATABASE_URL` before invoking pytest. Full backend/frontend gates, migrations, clean
setup timing, browser E2E/security/responsive review, video capture, and final secret/repository
audit are intentionally **NOT RUN** until Phase 3.

Phase 2 files created or modified:

- `backend/app/scripts/__init__.py`
- `backend/app/scripts/seed_demo.py`
- `backend/tests/test_seed_demo.py`
- `.env.example`
- `README.md`
- `exec-plans/active/M7-final-verification.md`

## 3. Scope

### In scope

- A safe, deterministic, repeatable demo seed for two businesses and eight demo users.
- README and environment-template corrections necessary for a clean setup and submission.
- Full backend, frontend, PostgreSQL integration, browser E2E, security, responsive, and accessibility verification.
- A timed clean-checkout setup rehearsal.
- A 3-5 minute demo checklist and submission evidence.
- Minimal P0/P1 fixes confirmed by tests, with focused regression coverage.
- Final repository, secret, generated-file, and Git-history review.

### Out of scope

- M8 or any additional product milestone.
- Deployment infrastructure, Docker Compose, message brokers, or multi-process WebSocket infrastructure.
- Optional rate limiting, attachments, typing indicators, read receipts, search, pagination, or cosmetic redesign.
- Silent API-contract changes or unrelated refactoring.
- Automatic commit, push, or publication of a demo video.

## 4. Mandatory-requirement coverage at planning time

| Area | Repository evidence | Planning status |
| --- | --- | --- |
| JWT access/refresh separation and password hashing | Backend services and security tests; Argon2 and typed JWT validation | Implemented; final regression required |
| RBAC and tenant/customer isolation | Authorization services and M2-M5 tests | Implemented; final security audit required |
| Ticket creation, first message, listing, assignment, and lifecycle | M4 implementation/tests and M6 browser evidence | Implemented; final E2E required |
| Persistent real-time chat and status events | M5 implementation/tests and M6 two-session browser evidence | Implemented; final E2E required |
| Six responsive frontend routes | Frontend source and M6 Phase 4 evidence | Implemented; final responsive/accessibility review required |
| PostgreSQL/Alembic setup | Alembic configuration and migration exist | Implemented; clean migration/downgrade/re-upgrade proof required |
| Two-business, eight-user demo seed | No seed utility found | **Missing — P0** |
| Demo credentials in README | No complete demo account manifest found | **Missing — P0** |
| Fresh setup in approximately 15 minutes | README has install/start commands but no complete PostgreSQL provisioning/seed rehearsal | **Incomplete — P1** |
| 3-5 minute required demo evidence | No demo checklist/video reference found | **Missing — P0 submission gate** |
| Architecture, trade-offs, limitations | README has technical decisions and known limitations | Present; consolidate into explicit reviewer-facing notes |
| Safe environment template | Root `.env.example` has placeholders; actual local env files are ignored | Present; final tracked/history secret audit required |
| Reasonable commit history | 21 focused M0-M6 commits observed | PASS at planning time; final audit required |
| Reviewer-accessible GitHub repository | GitHub remote configured | Local evidence only; external reviewer access must be confirmed |

## 5. Gap analysis and priorities

### P0 — release blockers

1. There is no reproducible seed satisfying exactly two demo businesses, one Admin, one Agent, and two Customers per business (eight demo users), plus representative tickets and messages.
2. README does not list all demo accounts or an executable seed workflow.
3. The required 3-5 minute demonstration and its evidence have not been prepared. It must include two-business isolation, customer ticket creation, agent claim, two-session chat, status update, and customer live update.
4. Final M7 functional and security evidence has not yet been executed. Any tenant leak, plaintext password, real committed secret, invalid JWT separation, or mandatory-flow failure is a release blocker.

### P1 — submission/setup quality

1. README setup is not yet proven from a clean checkout within approximately 15 minutes and lacks complete PostgreSQL role/database provisioning guidance.
2. Setup instructions need the seed command, demo login workflow, WebSocket configuration check, verification commands, and explicit reviewer-facing “Catatan” covering decisions, trade-offs, limitations, and unfinished work.
3. GitHub reviewer access, tracked-file hygiene, and current plus historical secret exposure need final verification.
4. The test-database instructions must make destructive migration/test commands unambiguously target disposable databases.

### P2 — optional improvements

1. There is no checked-in Playwright/Cypress suite. Actual two-browser verification remains mandatory, but adding a new E2E dependency is optional and must be justified by a concrete verification gap.
2. A dedicated screen-reader session was not recorded in M6. Keyboard, semantics, focus, contrast, and announcements remain mandatory manual checks; formal assistive-technology coverage is optional for this assessment.
3. Deployment, Docker Compose, WebSocket horizontal scaling, token revocation, and other documented enhancements remain out of scope unless the assessment explicitly requires them.

Logout is already implemented and integrated; it is not an M7 gap and remains non-blocking relative to the original mandatory assessment.

## 6. Safety and test-data rules

- All migration downgrade/re-upgrade, seed, integration, and E2E setup must use explicitly named disposable development/test databases.
- Before a destructive database command, inspect the parsed target URL and fail unless the database name is explicitly allow-listed for the M7 run (for example, ending in `_test`). Never print credentials.
- The demo seed must never truncate tables or delete unrelated rows.
- Seed writes must use one transaction, roll back on conflict/error, hash every password with the application password helper, and never log plaintext passwords.
- The seed must require an explicit acknowledgement flag such as `--confirm-demo-data`; demo passwords must come from a supplied demo-only environment value rather than source code.
- Stable slugs/emails and deterministic identifiers or natural-key lookups must make repeated runs idempotent. An incompatible existing record must cause a clear rollback rather than reassignment across tenants.
- Tokens, passwords, cookie values, connection URLs, and local environment contents must be redacted from logs, screenshots, recordings, and the execution plan.
- Browser E2E must use disposable demo data, two isolated browser sessions, and one backend worker because the current connection manager is process-local.

## 7. Planned files

Expected Phase 2 changes, subject to actual inspection before editing:

- `backend/app/scripts/__init__.py` — seed module package if not already present.
- `backend/app/scripts/seed_demo.py` — safe, idempotent demo seed entry point.
- `backend/tests/test_seed_demo.py` — PostgreSQL seed behavior and security tests.
- `.env.example` — only if a demo-seed input variable is required; placeholder only.
- `README.md` — fresh setup, seed, demo accounts, verification, architecture/limitations notes, and demo link/checklist.
- `exec-plans/active/M7-final-verification.md` — actual Phase 2-4 evidence and status.

Application source files are not planned for modification. They may be changed only for a confirmed P0/P1 defect within M7 scope, with a focused regression test and written justification.

## 8. Ordered tasks

### M7-01 — Freeze baseline and trace requirements

Phase: 2  
Dependencies: none

Steps:

1. Reconfirm Git status and review changes made after this plan.
2. Build a concise traceability checklist from requirements to route/service/test/demo evidence.
3. Record each item as implemented, missing, or requiring fresh verification.
4. Do not carry prior PASS claims forward if their command or environment cannot be reproduced.

Acceptance criteria:

- Mandatory assessment requirements have an owner, evidence source, and final gate.
- Scope is limited to P0/P1 findings; P2 work is explicitly deferred.
- Unrelated user changes, if any, are preserved.

Verification commands:

```bash
git status --short
git diff --check
git log --oneline --decorate -25
rg --files backend frontend docs exec-plans | sort
```

### M7-02 — Implement the safe demo seed

Phase: 2  
Dependencies: M7-01

Steps:

1. Add a small module entry point that reuses the existing SQLAlchemy session, models, enums, and password hashing helper.
2. Seed two stable business slugs and exactly eight named demo accounts: one Admin, one Agent, and two Customers for each business.
3. Add representative data sufficient for the demo: an open customer ticket for claim/chat, an assigned ticket with message history, a resolved customer-owned ticket for reopen, a closed ticket for restriction checks, and a Business B ticket for tenant-isolation proof.
4. Ensure every ticket/message/user relationship is tenant-consistent and all messages identify valid senders.
5. Make reruns idempotent and transactional. Abort on incompatible natural-key conflicts.
6. Require `--confirm-demo-data` and a demo-only password input. Refuse obviously production-named targets and never echo secrets.

Acceptance criteria:

- The seed creates two businesses and eight demo users with the required role distribution.
- Password columns contain application hashes, never the supplied plaintext.
- Representative tickets/messages support every planned demo step.
- Running the seed twice produces no duplicates and preserves unrelated rows.
- Failure leaves no partial seed data.
- The seed is safe for a reviewer-owned development database and clearly refuses accidental production use.

Verification commands:

```bash
cd backend
uv run python -m app.scripts.seed_demo --help
DEMO_SEED_PASSWORD='<local-demo-only-password>' uv run python -m app.scripts.seed_demo --confirm-demo-data
DEMO_SEED_PASSWORD='<local-demo-only-password>' uv run python -m app.scripts.seed_demo --confirm-demo-data
uv run pytest -q tests/test_seed_demo.py --tb=short
```

The two seed commands above must run only after `DATABASE_URL` has been inspected and approved as a disposable development/test target.

### M7-03 — Verify seed integrity and demo manifest

Phase: 2  
Dependencies: M7-02

Steps:

1. Test initial creation, rerun behavior, conflict rollback, role counts, tenant relationships, and password hashing against PostgreSQL.
2. Verify representative tickets and messages match the documented demo checklist.
3. Create a non-secret manifest of demo emails, roles, business slugs, and intended demo purpose.
4. Ensure the same local-only password can be supplied for convenience without storing it in application source or Git history.

Acceptance criteria:

- Automated tests prove 2 businesses and 8 seeded users, with 1 Admin, 1 Agent, and 2 Customers per business.
- Tests prove idempotence and rollback on incompatible data.
- Tests prove no plaintext password is persisted or returned.
- Demo records provide stable lookup keys without exposing real credentials.

Verification commands:

```bash
cd backend
uv run pytest -q tests/test_seed_demo.py tests/test_models.py --tb=short
uv run ruff check app/scripts tests/test_seed_demo.py
uv run mypy app/scripts tests/test_seed_demo.py
```

### M7-04 — Make setup and submission documentation reproducible

Phase: 2  
Dependencies: M7-02, M7-03

Steps:

1. Update README prerequisites and explicit PostgreSQL role/database creation for local development and isolated tests.
2. Document exact environment-file creation without copying real local values.
3. Document backend install, database check, migration, safe seed, frontend install, startup, Swagger/OpenAPI, login, and WebSocket URLs.
4. List all eight demo accounts, their roles/businesses, and clearly label the shared supplied password as local demo data only.
5. Add exact quality-gate commands and explain which require disposable PostgreSQL.
6. Consolidate architecture choices, security boundaries, current limitations, unfinished items, and single-process WebSocket behavior in an explicit `Catatan` section.
7. Add the ordered demo checklist and a placeholder/location for the final demo video URL; do not fabricate a URL.
8. Update `.env.example` only for variables actually consumed by the final implementation, with safe placeholders.

Acceptance criteria:

- A reviewer can follow README from a clean checkout without undocumented commands.
- All commands exist and match current manifests/modules.
- Setup covers PostgreSQL, Alembic, seed, backend/frontend startup, login, and WebSocket runtime configuration.
- No real secret or credential is committed.
- Known limitations and submission artifacts are easy to find.

Verification commands:

```bash
rg -n "PostgreSQL|alembic upgrade|seed_demo|uvicorn|npm run dev|WebSocket|Demo|Catatan|Limitation" README.md
git diff --check
git diff -- README.md .env.example
```

### M7-05 — Run static and automated quality gates

Phase: 3  
Dependencies: M7-02, M7-03, M7-04

Steps:

1. Run backend compile, format, lint, typing, and the full pytest suite against disposable PostgreSQL.
2. Run Alembic head verification, upgrade, downgrade to base, and re-upgrade only on a newly created disposable database.
3. Run frontend clean install, lint, typecheck, unit tests, and production build.
4. Record commands, environment class, counts, warnings, failures, and NOT RUN items exactly.
5. Fix only confirmed M7-scoped P0/P1 defects and rerun affected plus regression checks.

Acceptance criteria:

- All mandatory backend and frontend quality gates pass.
- Alembic produces the required schema after both initial upgrade and downgrade/re-upgrade.
- Full tests use PostgreSQL, not an in-memory substitute.
- No failure or warning relevant to correctness/security is hidden.

Verification commands:

```bash
cd backend
uv sync --all-groups
uv run python -m compileall -q app alembic tests
uv run ruff format --check app alembic tests
uv run ruff check app alembic tests
uv run mypy app tests
uv run alembic heads
uv run alembic upgrade head
uv run pytest -q --tb=short
```

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm audit --omit=dev
```

Before Alembic or pytest, the executor must use the repository's disposable-database guard and record the redacted database name. Downgrade/re-upgrade uses a separate, empty M7 database and is not run against normal development data.

### M7-06 — Rehearse a clean setup within approximately 15 minutes

Phase: 3  
Dependencies: M7-04, M7-05

Steps:

1. Clone the local repository into a new temporary directory so ignored local dependencies and environment files cannot mask missing instructions.
2. Create a new disposable PostgreSQL role/database following README exactly.
3. Create environment files only from documented variables and fresh local-only secrets.
4. Install backend/frontend dependencies, migrate, seed, and start both applications using README commands.
5. Log in with documented demo accounts and open the REST docs plus a WebSocket-backed ticket.
6. Measure elapsed hands-on setup time and record every deviation from README.
7. Remove only the explicitly created temporary checkout/database after evidence is captured.

Acceptance criteria:

- A clean checkout reaches a usable seeded application in approximately 15 minutes under normal local conditions.
- No undocumented file, global package, database object, or local cache content is required for correctness.
- Database migrations and seed can be rerun safely.
- Backend health/OpenAPI, frontend route, login, and WebSocket connection all work.

Verification commands:

```bash
fresh_dir="$(mktemp -d)"
git clone --no-local . "$fresh_dir/helpdesk-mini"
cd "$fresh_dir/helpdesk-mini"
```

Then execute the README commands verbatim. Record start/end time and command results; do not substitute undocumented recovery steps without first recording a documentation defect.

### M7-07 — Execute mandatory functional browser E2E

Phase: 3  
Dependencies: M7-05, M7-06

Steps:

1. Use the seeded environment and two isolated browser sessions.
2. Register a new business and verify its initial Admin can log in.
3. As Admin, create an Agent and Customer, then verify role-scoped navigation and user-management restrictions.
4. As Customer, create a ticket with its first message; verify list/detail content and latest-activity ordering.
5. Verify Admin assignment and Agent self-assignment paths.
6. Exercise `open -> in_progress -> resolved -> closed` and Customer-owned `resolved -> open`; verify invalid transitions are rejected.
7. Exchange messages between Customer and Agent without refresh. Reload and compare rendered history with persisted backend history.
8. Change status and verify the other browser receives the committed update without refresh.
9. Close a ticket and prove both newly connected and already-connected clients cannot send further messages.
10. Verify logout/session restoration behavior without storing access tokens in localStorage.

Acceptance criteria:

- Every mandatory flow works through the real frontend, FastAPI backend, and PostgreSQL.
- Two clients see one copy of each message and consistent history/status after reload.
- Loading, empty, success, validation, conflict, unauthorized, forbidden, and not-found states behave intentionally.
- No mocked response or build result is counted as browser E2E proof.

Verification evidence:

- Browser/session matrix with account, business, role, ticket ID, expected result, actual result, and timestamp.
- Redacted screenshots or recording markers for the critical flows.
- Browser console and backend logs reviewed for unexpected errors without capturing tokens/cookies.

### M7-08 — Execute final security audit

Phase: 3  
Dependencies: M7-05, M7-07

Steps:

1. Verify Business A cannot retrieve, mutate, assign, reopen, or connect by WebSocket to a Business B ticket; REST access must return 404.
2. Verify one Customer cannot access another Customer's ticket in the same business; REST access must return 404.
3. Verify missing, invalid, expired, wrong-type, and refresh JWTs are rejected from access-only REST and WebSocket operations.
4. Verify Admin read-only chat, Agent/Customer messaging rules, user-management RBAC, assignment RBAC, and closed-ticket restrictions.
5. Connect clients to separate rooms and prove messages/status events do not leak across rooms or tenants.
6. Verify broadcasts occur only after successful commits and concurrent messages persist consistently.
7. Inspect API responses, OpenAPI, logs, browser storage, cookies, repository files, and Git history for sensitive data exposure.
8. Treat any tenant leak, plaintext password, committed real secret, or JWT type bypass as a release blocker.

Acceptance criteria:

- Cross-business and cross-customer protected ticket access returns 404.
- Unauthorized WebSocket handshakes are rejected before acceptance.
- Access/refresh separation, hashing, RBAC, room isolation, commit ordering, and closed-ticket rules pass.
- No password hash, token, secret, stack trace, or cross-user cache data is exposed.

Verification commands:

```bash
cd backend
uv run pytest -q tests/test_auth.py tests/test_authorization.py tests/test_integration.py --tb=short
uv run pytest -q tests/test_tickets.py tests/test_messages.py tests/test_websocket_chat.py tests/test_websocket_manager.py --tb=short
```

Actual REST/WebSocket/browser probes must supplement these tests; pytest alone is not sufficient final E2E evidence.

### M7-09 — Review responsive UI and accessibility

Phase: 3  
Dependencies: M7-07

Steps:

1. Review all six routes at 320, 375, 768, and 1440 px.
2. Verify no horizontal overflow, clipped actions, obscured composer, broken ticket table/list, or inaccessible mobile navigation.
3. Complete keyboard-only login, ticket creation, assignment/status controls, chat, navigation, dialogs, and logout.
4. Inspect labels, validation associations, semantic landmarks, headings, focus visibility/order, dialogs, contrast, and live loading/status announcements.
5. Confirm loading, empty, error, disconnected, reconnecting, forbidden, and unauthorized states remain usable.

Acceptance criteria:

- Required routes are usable at all target widths without critical layout defects.
- Core flows are keyboard operable with visible focus.
- Forms, dialogs, statuses, and connection state are meaningfully announced and meet the approved UI/UX specification.
- Any formal screen-reader test not performed is recorded as NOT RUN, not PASS.

Verification commands:

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

These commands support but do not replace the viewport and keyboard review.

### M7-10 — Rehearse and capture the 3-5 minute demo

Phase: 3  
Dependencies: M7-06, M7-07, M7-08, M7-09

Required test data:

- Business A Customer 1: owns the primary open ticket.
- Business A Agent: claims the ticket, chats, and changes status.
- Business A Admin: available for assignment/user-management context.
- Business B Customer 1: owns a distinct ticket used for 404 isolation proof.
- Two isolated browser sessions and the deterministic seeded ticket identifiers.

Ordered demo checklist:

1. Show the two separate seeded businesses and identify the active Customer and Agent sessions.
2. Customer A creates a ticket with the first message.
3. Agent A sees the ticket and self-assigns or claims it.
4. Customer A and Agent A exchange real-time messages in two browser sessions without refresh.
5. Reload one session and show the same persisted message history.
6. Agent A changes ticket status; Customer A sees the status update without refresh.
7. Attempt to open Business B's ticket while authenticated as Business A and show the 404 result without exposing sensitive data.
8. Briefly state the single-process in-memory WebSocket limitation and where verification commands are documented.

Acceptance criteria:

- A rehearsal fits 3-5 minutes without undocumented setup or manual data repair.
- The final recording visibly demonstrates every required assessment point.
- No token, secret, password entry, local `.env`, or private browser data is exposed.
- The final video URL/location is recorded in the submission/README only after it exists and reviewer access is confirmed.

### M7-11 — Audit submission and repository hygiene

Phase: 4  
Dependencies: M7-05 through M7-10

Steps:

1. Confirm one repository contains `frontend/` and `backend/`, the final README, safe environment template, migration, seed, tests, and completed plans.
2. Confirm no `.env`, credentials, tokens, database dumps, logs, dependency folders, build output, caches, or editor artifacts are tracked.
3. Scan current tracked content and Git history for secret-like material while redacting any finding.
4. Review commit history for understandable M0-M7 progression; do not rewrite history automatically.
5. Confirm the configured GitHub URL is accessible to the intended reviewer without relying on the developer's authenticated session.
6. Confirm README commands, demo accounts, video link, architecture decisions, trade-offs, limitations, and unfinished items are accurate.
7. Review `git diff` and ensure only intentional M7 files changed.

Acceptance criteria:

- Repository contains all mandatory submission artifacts and no sensitive/generated files.
- Reviewer access is confirmed externally.
- Git history is reasonable and no secret exposure is found in current or historical content.
- Diff is scoped, documentation is accurate, and all outstanding items are explicitly classified.

Verification commands:

```bash
git status --short
git diff --check
git diff --stat
git ls-files
git ls-files | rg '(^|/)(\.env($|\.)|node_modules|\.next|\.venv|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|.*\.log$|.*\.sql$)'
git grep -I -n -E '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|AKIA[0-9A-Z]{16}|Bearer [A-Za-z0-9._-]{20,}|postgresql[^[:space:]]*://[^[:space:]]+:[^[:space:]@]+@)' -- . ':!*.lock'
git log --oneline --decorate --all
git remote -v
```

Matches must be reviewed and redacted. `.env.example` placeholder matches are allowed only after manual confirmation. If an approved history scanner is available, run it in redacted mode; otherwise record historical secret scanning as NOT RUN and perform documented manual inspection.

### M7-12 — Conditional milestone closure

Phase: 4  
Dependencies: M7-11

Steps:

1. Reconcile every acceptance criterion and gap with executed evidence.
2. Record exact PASS / FAIL / NOT RUN counts and commands in this plan.
3. If any P0 security, mandatory functional, setup, seed, or demo gate fails, keep this plan active and mark M7 BLOCKED with the exact remediation.
4. If all mandatory gates pass, mark M7 COMPLETE, move this plan to `exec-plans/completed/`, and update README milestone status.
5. Do not commit or push; provide the final diff and suggested commit boundaries for human review.

Acceptance criteria:

- No mandatory criterion is inferred from code existence or mocked tests.
- All failures and NOT RUN items are visible and correctly affect release status.
- M7 closes only when setup, security, functionality, demo, and submission evidence all pass.

Verification commands:

```bash
git status --short
git diff --check
git diff --stat
```

## 9. Final verification matrix

The following evidence is required before M7 can be marked complete:

| Gate | Required evidence | Failure effect |
| --- | --- | --- |
| Backend quality | Compile, Ruff format/lint, mypy, full pytest on PostgreSQL | BLOCKED |
| Migration integrity | Fresh upgrade plus disposable downgrade/re-upgrade | BLOCKED |
| Frontend quality | `npm ci`, lint, typecheck, tests, production build | BLOCKED for mandatory defects |
| Seed | Two businesses, eight users, roles, idempotence, hashed passwords, representative data | BLOCKED |
| Clean setup | Clean checkout usable in approximately 15 minutes using README | BLOCKED if reviewer cannot start app |
| Functional E2E | Real frontend/backend/PostgreSQL flows, including two-session chat | BLOCKED |
| Security | Tenant/customer 404, JWT separation, RBAC, WebSocket/room isolation, no leaks | BLOCKED |
| Responsive/accessibility | Required routes usable at target sizes and by keyboard | BLOCKED for critical usability/access defects |
| Demo | 3-5 minute rehearsal/recording covers all seven requested moments | BLOCKED |
| Submission | Reviewer access, safe env template, README, clean tracked files/history | BLOCKED for secrets or missing mandatory artifacts |

## 10. Existing components to reuse

- Backend settings/database session, SQLAlchemy models/enums, and Alembic migration.
- Existing Argon2 password helper and authentication/token utilities.
- Existing tenant/role authorization services and ticket/message workflows.
- Existing M2-M5 PostgreSQL test fixtures and disposable-database guard patterns.
- Existing FastAPI OpenAPI documentation and native WebSocket connection manager.
- Frontend typed API client, auth provider/guards, TanStack Query cache scoping, and ticket socket hook.
- Existing responsive components, role-aware actions, loading/error/empty/connection states, and domain tests.
- Completed M0-M6 plans as traceability evidence, while rerunning final gates rather than copying their results.

## 11. Known risks

- The process-local WebSocket manager requires a single backend worker; multiple workers would split rooms without a shared pub/sub layer. This remains a documented limitation, not M7 scope.
- Fresh dependency installation and external GitHub/video access depend on network availability. Unavailable external checks must be recorded as NOT RUN and cannot be silently counted as PASS.
- Manual browser evidence is currently the practical E2E path. It is repeatable through the deterministic seed/checklist but less automated than a checked-in browser suite.
- Seed natural-key conflicts can otherwise corrupt demo assumptions; the seed must abort transactionally rather than mutate non-demo users or tenants.
- Repository-history secret scanning may require an already-approved local scanner. Current-tree review alone is insufficient proof of historical cleanliness.
- Existing stateless refresh tokens and in-memory WebSocket state are documented architecture trade-offs; neither may be represented as production hardening.

## 12. Phase boundaries and approval gate

- **Phase 1:** inspection, gap analysis, and implementation-ready planning; complete.
- **Phase 2:** approved seed, documentation, and submission preparation work; implemented and preliminarily validated.
- **Phase 3:** final automated tests, clean setup, actual browser E2E/security/responsive checks, and demo validation.
- **Phase 4:** final audit and conditional milestone closure.

M7 remains active and is **not complete**. Phase 3 must not begin without user review.

Phase 2 disposition: **IMPLEMENTED, PENDING PHASE 3 VERIFICATION**.
