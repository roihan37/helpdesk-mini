# M1 - Database Models & Migrations

## Status

Completed on 2026-10-09 after implementation and independent Phase 3/4 verification.
No critical M1 blocker remains.

## Objectives and Scope

Implement the minimum PostgreSQL persistence model required by the assessment:

- `Business`, `User`, `Ticket`, and `Message` SQLAlchemy 2.x models.
- UUID primary keys and timezone-aware UTC timestamps.
- Explicit ORM relationships between the four entities.
- Required foreign keys, uniqueness rules, enum-like value constraints, and indexes.
- One reviewed Alembic revision that creates and can remove the M1 schema.

M1 does not include authentication, password hashing services, registration, REST APIs,
authorization services, ticket workflows, WebSocket behavior, frontend changes, seed data,
or optional infrastructure.

## M0 Prerequisite Review

Verified on 2026-10-09:

- Python 3.12.12 satisfies the Python 3.11+ requirement.
- FastAPI, SQLAlchemy, Psycopg, Alembic, and typed settings are installed through `uv`.
- Backend source and Alembic configuration compile and import successfully.
- Ruff and strict mypy checks pass for the existing backend.
- `backend/.env` is ignored and is loaded by the settings layer.
- The configured PostgreSQL database accepts the application connection.
- `alembic current` connects successfully and `alembic heads` is empty, as expected before M1.
- `Base.metadata` currently has no domain tables.

Historical prerequisite note: M0 was still awaiting administrative closure when M1 began.
It has since been reviewed and is stored at `exec-plans/completed/M0-foundation.md`.

## Files to Create or Modify

Planned model files:

- `backend/app/models/__init__.py`
- `backend/app/models/enums.py`
- `backend/app/models/business.py`
- `backend/app/models/user.py`
- `backend/app/models/ticket.py`
- `backend/app/models/message.py`

Planned integration and migration files:

- `backend/alembic/env.py` - import the model registry so Alembic sees all metadata.
- `backend/alembic/versions/<revision>_create_core_tables.py` - create and drop the M1 schema.

Phase 3 verification files:

- `backend/tests/test_models.py` - focused PostgreSQL model and constraint tests.
- `backend/pyproject.toml` - pytest development dependency and test discovery configuration.
- `backend/uv.lock` - locked pytest dependency graph.

No frontend or API files are in scope. `backend/app/db/base.py` will remain the single
declarative base unless implementation reveals a concrete import-cycle problem.

## Database Schema

### `businesses`

- `id`: UUID primary key.
- `name`: required string.
- `slug`: required string with a named global unique constraint.
- `created_at`: required timezone-aware timestamp with a database-side current-time default.
- Relationships: one-to-many `users` and `tickets`.

### `users`

- `id`: UUID primary key.
- `business_id`: required foreign key to `businesses.id`.
- `name`: required string.
- `email`: required string with a named global unique constraint.
- `password_hash`: required string; the model stores hashes only, although hashing logic is M2.
- `role`: required value restricted to `admin`, `agent`, or `customer`.
- `created_at`: required timezone-aware timestamp with a database-side current-time default.
- Relationships: parent `business`, customer tickets, assigned tickets, and sent messages.
- Add an index on `business_id` to support tenant-scoped user access.

### `tickets`

- `id`: UUID primary key.
- `business_id`: required foreign key to `businesses.id`.
- `customer_id`: required foreign key to `users.id`.
- `assigned_agent_id`: nullable foreign key to `users.id`.
- `subject`: required string, limited to 150 characters to match the API contract.
- `category`: required string.
- `priority`: required value restricted to `low`, `medium`, or `high`.
- `status`: required value restricted to `open`, `in_progress`, `resolved`, or `closed`;
  model default and database default are `open`.
- `created_at`: required timezone-aware timestamp with a database-side current-time default.
- `updated_at`: required timezone-aware timestamp initialized from database time and configured
  for application-issued updates; later services remain responsible for touching it when ticket
  activity changes.
- Relationships: parent `business`, `customer`, optional `assigned_agent`, and `messages`.
- Required named composite index on `(business_id, status)`.

### `messages`

- `id`: UUID primary key.
- `ticket_id`: required foreign key to `tickets.id`.
- `sender_id`: required foreign key to `users.id`.
- `body`: required text.
- `created_at`: required timezone-aware timestamp with a database-side current-time default.
- Relationships: parent `ticket` and `sender`.
- Add the recommended deterministic-history index on `(ticket_id, created_at, id)`.

### Constraint and Deletion Policy

- Use named foreign-key, unique, check, and index objects so migrations and failures are
  reviewable and deterministic.
- Use database check constraints for role, priority, and status values instead of PostgreSQL
  native enum types. This keeps the allowed values explicit and avoids a separate enum-type
  migration lifecycle.
- Use restrictive foreign-key behavior (no cascading deletes). No deletion feature is required,
  and retaining users, tickets, and messages is safer than implicit history deletion.
- UUID values are generated by the application through SQLAlchemy. The schema does not require
  a PostgreSQL extension solely for UUID generation.

## Implementation Steps

1. Add shared Python enum definitions for user roles, ticket priorities, and ticket statuses.
2. Define the four SQLAlchemy models with typed `Mapped` columns and explicit relationships.
3. Export the declarative base and all models from `app.models` as the model registry.
4. Update Alembic's environment to load that registry into `target_metadata`.
5. Generate one Alembic revision from model metadata against a disposable PostgreSQL database.
6. Review and normalize the generated migration: table order, names, UUID/timestamp types,
   foreign keys, check constraints, unique constraints, indexes, and reverse-safe downgrade order.
7. Run static validation, migration lifecycle checks, schema inspection, and focused integrity
   probes on the disposable database.
8. Record only actually executed verification results in this plan and report M1 without
   proceeding to M2.

## Security Considerations

- `tickets.business_id` is stored directly to support mandatory tenant-filtered queries.
- Foreign keys guarantee referenced rows exist, but ordinary foreign keys do not prove that a
  ticket's customer/assignee belongs to the same business or has the required role.
- Same-business customer validation, Agent-role assignment validation, and sender authorization
  require trusted service-layer checks in later milestones. These limitations must not be mistaken
  for authorization provided by ORM relationships.
- Messages inherit tenant scope through their ticket; later message queries must authorize the
  parent ticket before returning or creating messages.
- UUID identifiers reduce predictability but never replace tenant and ownership authorization.
- `password_hash` is persistence-only. M1 will not add plaintext password fields, credentials,
  hashing behavior, response schemas, or logging of sensitive values.
- No client-provided tenant identifier becomes trusted merely because the schema contains it.

## Acceptance Criteria

- [x] All four models import successfully and share the existing declarative base.
- [x] Model metadata contains exactly the required four domain tables.
- [x] Alembic detects one M1 head and can upgrade an empty disposable PostgreSQL database.
- [x] The database contains `businesses`, `users`, `tickets`, and `messages` after upgrade.
- [x] All documented columns are present with the required nullability.
- [x] Business slug and user email uniqueness are enforced by PostgreSQL.
- [x] User role, ticket priority, and ticket status allowed values are enforced by PostgreSQL.
- [x] Required foreign keys exist for all documented relationships.
- [x] `assigned_agent_id` accepts `NULL`.
- [x] The `(business_id, status)` ticket index exists.
- [x] The `(ticket_id, created_at, id)` message-history index exists.
- [x] ORM relationships expose the documented parent/child associations without ambiguity.
- [x] Downgrade to base and re-upgrade to head both succeed on the disposable database.
- [x] Existing backend compile, Ruff, and strict mypy checks continue to pass.
- [x] Focused PostgreSQL model tests pass against the disposable database.
- [x] No authentication, API, WebSocket, frontend, seed, or M2 feature is introduced.

## Verification Commands

Run static checks from `backend/`:

```bash
uv run python -m compileall -q app alembic tests
uv run ruff check app alembic tests
uv run ruff format --check app alembic tests
uv run mypy app tests
uv run python -c "from app.models import Base; assert set(Base.metadata.tables) == {'businesses', 'users', 'tickets', 'messages'}"
uv run alembic heads
```

Use a dedicated disposable PostgreSQL container/database, not the developer's normal database:

```bash
docker run --rm --name helpdesk-mini-m1-postgres \
  -e POSTGRES_USER=helpdesk_test \
  -e POSTGRES_PASSWORD=helpdesk_test \
  -e POSTGRES_DB=helpdesk_m1_test \
  -p 127.0.0.1:55433:5432 \
  -d postgres:17
docker exec helpdesk-mini-m1-postgres pg_isready -U helpdesk_test -d helpdesk_m1_test
DATABASE_URL=postgresql+psycopg://helpdesk_test:helpdesk_test@127.0.0.1:55433/helpdesk_m1_test uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://helpdesk_test:helpdesk_test@127.0.0.1:55433/helpdesk_m1_test uv run alembic current
M1_TEST_DATABASE_URL=postgresql+psycopg://helpdesk_test:helpdesk_test@127.0.0.1:55433/helpdesk_m1_test uv run pytest -q
```

Run focused SQLAlchemy inspection/integrity probes to verify tables, column nullability,
foreign keys, named indexes, check constraints, duplicate-slug rejection, duplicate-email
rejection, invalid enum-like values, and a ticket with `assigned_agent_id = NULL`. Record the
exact command used during implementation rather than claiming the probes in advance.

Test the reversible migration only on that disposable database:

```bash
DATABASE_URL=postgresql+psycopg://helpdesk_test:helpdesk_test@127.0.0.1:55433/helpdesk_m1_test uv run alembic downgrade base
DATABASE_URL=postgresql+psycopg://helpdesk_test:helpdesk_test@127.0.0.1:55433/helpdesk_m1_test uv run alembic upgrade head
docker stop helpdesk-mini-m1-postgres
```

## Known Risks

- M0 has technical validation evidence but has not been administratively reviewed/moved to
  `completed/`. The user explicitly approved M1 implementation despite that administrative state;
  M0 was not moved or otherwise altered as part of this milestone.
- The original assessment PDF is not present in the repository. This plan uses the repository's
  stated source-of-truth requirements, which identify themselves as derived from that PDF.
- Cross-business user relationships and role correctness cannot be fully enforced by the chosen
  minimal foreign-key layout; later service code must validate them transactionally.
- PostgreSQL's current email uniqueness is case-sensitive. M2 must normalize email addresses to
  one canonical form before querying and persistence so case variants cannot represent separate
  identities.
- `updated_at` does not update merely because a related message is inserted. Ticket/message
  services must explicitly update ticket activity time in the same transaction.
- Local PostgreSQL data is not disposable. All destructive downgrade/re-upgrade checks must use
  the isolated test database described above.
- Relationship-heavy models can introduce circular imports or ambiguous user-to-ticket joins;
  explicit foreign key lists and a single model registry will be used and verified.

## Validation Record

Executed on 2026-10-09.

Static validation from `backend/` with
`UV_CACHE_DIR=/private/tmp/helpdesk-mini-uv-cache`:

- `uv run python -m compileall -q app alembic` - PASS.
- `uv run ruff check app alembic` - PASS (`All checks passed!`).
- `uv run ruff format --check app alembic` - PASS (`16 files already formatted`).
- `uv run mypy app` - PASS (`Success: no issues found in 14 source files`).
- Model import, metadata-table assertion, and `configure_mappers()` probe - PASS
  (`models_and_relationships=ok`).
- `uv run alembic heads` - PASS; one head: `a3930ac451be`.

Migration validation used a temporary `postgres:17` container named
`helpdesk-mini-m1-postgres` with database `helpdesk_m1_test` exposed only on
`127.0.0.1:55433`. It was started with `--rm` and stopped after validation.

- `alembic upgrade head` on the empty database - PASS.
- `alembic current` - PASS: `a3930ac451be (head)`.
- `alembic check` - PASS: `No new upgrade operations detected.`
- `alembic downgrade base` - PASS.
- Re-running `alembic upgrade head` after downgrade - PASS.
- Final `alembic current` - PASS: `a3930ac451be (head)`.

A temporary SQLAlchemy verification script was executed before and after the migration
downgrade/re-upgrade cycle. It inspected the live PostgreSQL catalog and performed focused
inserts. Results:

- Required tables, columns, and nullability - PASS.
- Named foreign keys and ORM relationship configuration - PASS.
- Required ticket index and deterministic message-history index - PASS.
- `assigned_agent_id = NULL` insertion - PASS.
- Duplicate business slug rejection - PASS.
- Duplicate user email rejection - PASS.
- Invalid role, priority, and status rejection - PASS.
- Ticket default status `open` and relationship traversal - PASS.

The first temporary-script invocation omitted `PYTHONPATH=.` and failed before importing the
application (`ModuleNotFoundError: app`). The corrected command was
`PYTHONPATH=. UV_CACHE_DIR=/private/tmp/helpdesk-mini-uv-cache uv run python /private/tmp/m1_verify.py`;
both complete probe runs then passed. This was a command-environment issue, not an application
or migration failure.

## Phase 3 and 4 Review Record

Re-verified on 2026-10-09 against a fresh disposable `postgres:17` database named
`helpdesk_m1_review_test`. The container was bound only to `127.0.0.1:55433`, used test-only
credentials, and removed after verification.

### Implementation Review

- Inspected all four models, the model registry, Alembic environment, and revision
  `a3930ac451be` against the documented requirements.
- Corrected the Python typing for the `role`, `priority`, and `status` attributes to `str`, which
  matches the values actually returned by their SQLAlchemy `String` columns. The shared enums
  remain the source for defaults and allowed-value definitions.
- Added a persistent focused PostgreSQL test suite and the existing-project-compatible pytest
  development dependency. No production dependency was added.
- No migration correction was required. The revision matches current SQLAlchemy metadata.

### Final Command Results

Static and metadata validation from `backend/`:

- `uv run python -m compileall -q app alembic tests` - PASS.
- `uv run ruff check app alembic tests` - PASS.
- `uv run ruff format --check app alembic tests` - PASS (`17 files already formatted`).
- `uv run mypy app tests` - PASS (`15 source files`).
- Model import, exact metadata-table assertion, and `configure_mappers()` probe - PASS.
- `uv run alembic heads` - PASS; exactly one head: `a3930ac451be`.

Fresh migration lifecycle on the disposable PostgreSQL database:

- `uv run alembic upgrade head` - PASS.
- `uv run alembic current` - PASS: `a3930ac451be (head)`.
- `uv run alembic check` - PASS: `No new upgrade operations detected.`
- `uv run alembic downgrade base` - PASS.
- Re-upgrade with `uv run alembic upgrade head` - PASS.
- Final `uv run alembic current` - PASS: `a3930ac451be (head)`.
- Final `uv run alembic check` - PASS: no schema drift.

Focused database test suite:

- `M1_TEST_DATABASE_URL=<disposable-test-url> uv run pytest -q` - PASS.
- Result: **26 passed, 0 failed, 0 skipped** in 0.53 seconds.
- Coverage includes table/column shape, nullability, database defaults, timestamps, named foreign
  keys, actual foreign-key enforcement, unique slug/email constraints, all allowed role/priority/
  status values, rejection of invalid values, nullable assignment, indexes, and ORM traversal.

### Failures Encountered and Resolved

- The initial dependency installation could not reach the package index inside the restricted
  sandbox. Re-running the same `uv add --dev 'pytest>=8,<9'` command with approved network access
  succeeded.
- The first localhost migration attempt was denied by sandbox networking. Re-running it with
  approved access to the disposable local container succeeded.
- The first pytest collection attempt failed with `ModuleNotFoundError: app`. Adding the project
  root to pytest's configured `pythonpath` fixed test discovery; the final suite passed.
- Initial Ruff validation reported only import ordering, line length, and formatting issues in the
  new verification code. Ruff's formatter/fixer corrected them; final lint and format checks pass.

### Security and Scope Review

- No production credentials or environment file were added. Test connection details were limited
  to the disposable local database.
- Database foreign keys ensure referenced records exist, but same-business membership, customer
  ownership, assigned-agent role, and message sender authorization remain mandatory service-layer
  checks for later milestones.
- No authentication, API endpoint, frontend, WebSocket, seed, or M2 behavior was implemented or
  tested in this milestone.
- Full application authorization tests are **NOT RUN** because those services are outside M1.

### Milestone Review Status

**COMPLETE.** All M1 acceptance criteria have executable evidence. The plan was confirmed in
`completed/` during the M2 prerequisite review on 2026-10-09. No later milestone implementation
has been started.
