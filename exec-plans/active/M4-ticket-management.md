# M4 - Ticket Management

## Status

**READY FOR PHASE 4 REVIEW — Phase 3 verified on 2026-10-10.** The plan remains active and M4 is
not marked complete. Final milestone review has not been performed.

## 1. Objective

Implement the required Ticket REST workflows on top of the completed M1 models, M2 authentication,
and M3 authorization policies:

- list tickets with role-appropriate tenant and ownership scope;
- create a Customer ticket and its first Message atomically;
- retrieve an authorized ticket without existence disclosure;
- update assignment and status using the documented rules; and
- verify endpoint contracts, isolation, transactions, and concurrent assignment behavior against a
  disposable PostgreSQL database.

The implementation will remain a small synchronous FastAPI/SQLAlchemy modular-monolith feature.

## 2. Scope

- `GET /tickets` with optional validated `status` filtering, role-based visibility, descending
  latest-activity ordering, and an empty list when no record matches.
- `POST /tickets`, Customer-only, deriving tenant and owner from the authenticated database User.
- Atomic Ticket and required first-Message persistence.
- `GET /tickets/{id}` using the M3 tenant/ownership resolver and non-disclosing 404 behavior.
- `PATCH /tickets/{id}` for documented status transitions and Agent assignment.
- Admin same-business Agent assignment, Agent self-assignment, and race-safe conflicting-claim
  handling.
- Combined assignment and status update in one database transaction after all requested operations
  pass authorization and business-rule validation.
- Explicit Pydantic request/response schemas and standard error envelopes.
- PostgreSQL-backed endpoint, transaction, authorization, and concurrency tests.
- Necessary CORS support for the new `PATCH` method.

## 3. Out of Scope

- Message-history REST endpoints and additional REST message creation.
- WebSocket connection management, chat messages, broadcasts, status events, or any other M5 work.
- Frontend pages or clients.
- Authentication, refresh-token, or user-management redesign.
- Pagination, search, attachments, notifications, unread counts, or other bonus features.
- Unassignment unless a later approved contract explicitly adds it; the current API contract only
  defines assignment to an Agent.
- Database schema changes or a new Alembic revision unless implementation uncovers a demonstrated
  schema defect. None is currently expected.
- README or unrelated documentation changes.

## 4. Existing Dependencies

### Verified prerequisites

- M1 provides `Business`, `User`, `Ticket`, and `Message`, UUID foreign keys, allowed-value check
  constraints, nullable `assigned_agent_id`, timestamps, relationships, and the
  `(business_id, status)` Ticket index.
- M2 provides Bearer access-token authentication, database-backed current User resolution,
  `require_roles`, standard error handling, and Admin-only tenant-scoped user management.
- M3 is marked **COMPLETE — 2026-10-10**. Its final review found no critical current-scope defect.
  Database-backed Phase 3 evidence records 76 passing tests, including M2 regressions, M3 policy
  tests, and M1 model tests. The single Alembic head was `a3930ac451be` and no model drift was found.
- M3 Phase 4 could not repeat PostgreSQL tests because that sandbox denied local connections, but
  reviewed the same committed implementation for which Phase 3 had passing database evidence.
  This is a recorded environment limitation, not a functional M4 blocker.

### Reusable code

- `app.api.dependencies.get_current_user` is the trusted authenticated database identity.
- `app.api.dependencies.require_roles` supplies consistent 403 role enforcement.
- `app.services.authorization.get_authorized_ticket` scopes a single Ticket by trusted business
  and, for Customers, ownership, returning the same 404 for missing and inaccessible resources.
- `get_authorized_assignment_agent` verifies actor permissions and resolves only a same-business
  Agent target without leaking foreign users.
- `authorize_ticket_status_update` enforces tenant/ownership, role, Customer reopen authority, and
  closed-ticket rejection; M4 must add the complete normal transition map.
- Existing router, schema, service, `AppError`, TestClient override, and disposable PostgreSQL
  patterns will be followed.

No new runtime or development dependency is planned.

## 5. Architecture Decisions

- Add a dedicated `tickets` router, Ticket request/response schemas, and Ticket service. Routers
  will parse HTTP input and shape responses; services will own SQL, transactions, and business
  rules.
- Use the existing `TicketPriority` and `TicketStatus` string enums in Pydantic and service logic.
  Strict request schemas will reject unknown/client-controlled identity fields.
- Response models will map ORM rows explicitly through Pydantic `from_attributes`. Core responses
  retain the documented fields. List responses include optional assignee identity; detail/update
  responses include Customer and optional assignee identity.
- Extend the M3 ticket resolver minimally with an optional row-lock mode, or an equivalently small
  centralized locked resolver, so `PATCH` preserves exactly the same query-time tenant/ownership
  predicates while issuing PostgreSQL `SELECT ... FOR UPDATE`. Read-only detail requests remain
  unlocked.
- Ticket lists use an explicit predicate on the authenticated User's database `business_id`; a
  Customer query also includes `customer_id == current_user.id`. Lists cannot use an unscoped base
  query.
- Creation constructs Ticket and Message in one Session transaction, derives
  `business_id/customer_id/sender_id` from the current Customer, commits once, rolls back on every
  exception, and returns only committed/refreshed state.
- Updates lock the Ticket row, validate every supplied operation before mutation, then commit once.
  This serializes competing Agent claims and gives later M5 code a compatible row-lock strategy for
  close-versus-message races.
- Treat a requested status equal to current status as a no-op, including `closed -> closed`, per the
  API contract. Closed remains terminal for every actual status change.
- Reject an empty PATCH body with 422. Distinguish omitted fields from provided values using
  Pydantic field presence. `assigned_agent_id: null` is rejected because unassignment is not in the
  approved contract.
- A pure no-op does not issue an UPDATE or advance `updated_at`; a successful material assignment
  or status change advances activity time. A combined request is all-or-nothing.
- Use `updated_at DESC, id DESC` for deterministic list ordering while satisfying the documented
  primary order.
- Expand the existing CORS method allow-list only to include `PATCH`; no wildcard policy change.
- No migration is planned because the existing schema supports M4.

## 6. Existing Implementation Gap Analysis

| Requirement | Classification | M4 action |
|---|---|---|
| Authenticated current User | IMPLEMENTED AND VERIFIED | Reuse without JWT changes |
| Business, User, Ticket, and Message models | IMPLEMENTED AND VERIFIED | Reuse without a migration unless a defect is demonstrated |
| Ticket tenant/Customer resolver | IMPLEMENTED AND VERIFIED | Reuse for detail; minimally add locked resolution for update |
| Assignment target authorization | IMPLEMENTED AND VERIFIED at policy level | Integrate and add current-assignee conflict rule |
| Status actor authorization | IMPLEMENTED AND VERIFIED at policy level | Integrate and add complete transition map/no-op handling |
| Standard application error handling | IMPLEMENTED AND VERIFIED | Reuse the existing error envelope and exception mapping |
| PostgreSQL test fixtures/patterns | IMPLEMENTED AND VERIFIED | Reuse guarded disposable-database patterns |
| Ticket schemas | MISSING | Add strict create/update and explicit read schemas |
| Ticket router | MISSING | Add the four approved REST operations and register it |
| Ticket list service | MISSING | Add explicit tenant/ownership predicates, filter, and ordering |
| Atomic Ticket + first Message workflow | MISSING | Add one-commit transaction with rollback |
| Ticket detail endpoint | MISSING | Call centralized M3 resolver and return nested public identities |
| Update transaction | MISSING | Add locked, all-or-nothing assignment/status workflow |
| Concurrent Agent claim handling | MISSING | Serialize on Ticket row and return 409 to the losing claimant |
| Cross-row tenant/role integrity | IMPLEMENTED BUT NOT VERIFIED at an M4 endpoint | Enforce in services; test adversarial cases |
| CORS `PATCH` support | MISSING | Add `PATCH` to the existing allow-list |
| Ticket endpoint integration tests | MISSING | Add guarded PostgreSQL tests |
| Message history and WebSocket/status broadcasts | DEFERRED TO M5 | M4 only persists the first Message and committed Ticket state |
| Pagination, search, and bonus infrastructure | OUT OF SCOPE | Do not implement during M4 |

## 7. Ordered Implementation Tasks

### M4-01 — Define strict Ticket API schemas and register the route boundary

**Objective:** Establish typed request/response contracts and the four documented HTTP operations
without placing business logic in route handlers.

**Files:** Create `backend/app/schemas/ticket.py` and `backend/app/api/routes/tickets.py`; modify
`backend/app/api/router.py` and `backend/app/main.py`. Modify package `__init__.py` files only if the
existing import style requires it.

**Dependencies:** Completed M1 models/enums, M2 authentication dependency, existing error schemas,
and the API contract.

**Approach:** Define strict create and update schemas; constrain subject to 1-150 characters,
category to a stripped non-empty value no longer than the database's 100 characters, initial
message to 1-5000 characters, and priority/status to supported enums. Define explicit core/list and
detail response models with small public identity objects. Add thin authenticated route handlers,
register the router, document 401/403/404/409/422 responses, and allow CORS `PATCH`.

**Security:** Do not accept `business_id`, `customer_id`, `sender_id`, initial status, or arbitrary
assignee fields during creation. Use database-backed `get_current_user`; schemas must never expose
password hashes.

**Acceptance:** OpenAPI contains exactly the four M4 routes with Bearer security and explicit
response models; malformed enums, lengths, UUIDs, unknown fields, empty PATCH, and null assignment
produce the standard 422 envelope; existing routes remain unchanged.

**Verification commands:** Run compile, Ruff, mypy, the focused schema/OpenAPI cases in
`tests/test_tickets.py`, and existing authentication/user route tests from Section 15.

### M4-02 — Implement tenant-scoped listing and atomic Customer creation

**Objective:** Implement `GET /tickets` and `POST /tickets` with trusted ownership and transaction
boundaries.

**Files:** Create `backend/app/services/tickets.py`; complete list/create handlers in
`backend/app/api/routes/tickets.py`; add cases to `backend/tests/test_tickets.py`.

**Dependencies:** M4-01 and existing Ticket/Message/User relationships.

**Approach:** Build list predicates from the authenticated User, apply the optional status enum,
order by `updated_at DESC, id DESC`, and eager-load only response relationships. For creation,
require Customer role, derive all identity/default fields server-side, add the Ticket and first
Message to one Session, commit exactly once, roll back on error, refresh/load response state, and
return 201.

**Security:** Admin/Agent can list only their trusted business; Customer can list only their own
records. A payload cannot select another tenant, Customer, sender, assignee, or status. The first
Message sender is always the authenticated Customer.

**Acceptance:** Role visibility, status filter, empty result, ordering, server-derived fields,
default `open`/unassigned state, first Message persistence, and forced-failure rollback all pass
against PostgreSQL. Admin/Agent creation returns 403; bad input returns 422.

**Verification commands:** Run the focused list/create and atomic rollback tests in
`tests/test_tickets.py`, followed by the guarded database suite from Section 15.

### M4-03 — Implement authorized Ticket detail

**Objective:** Implement `GET /tickets/{id}` without duplicating or weakening M3 isolation.

**Files:** Complete `backend/app/api/routes/tickets.py` and `backend/app/services/tickets.py`; add
detail cases to `backend/tests/test_tickets.py`. Modify `authorization.py` only if a narrowly needed
loading option is justified and preserves its predicates/errors.

**Dependencies:** M4-01 and the M3 `get_authorized_ticket` policy.

**Approach:** Resolve the resource through the M3 helper, load Customer and optional assigned-Agent
public data without a new unscoped Ticket lookup, and return the documented detail envelope.

**Security:** Cross-business, same-business other-Customer, and nonexistent IDs must be
indistinguishable `TICKET_NOT_FOUND` 404 responses. Same-business Admin/Agent retain business-wide
visibility.

**Acceptance:** Authorized roles receive the expected core and nested fields; inaccessible and
missing resources have identical status/code/message/details; password hashes and internal errors
are absent.

**Verification commands:** Run focused Ticket detail/isolation tests, M3 authorization regression
tests, and the guarded full suite.

### M4-04 — Implement locked assignment and status updates

**Objective:** Implement `PATCH /tickets/{id}` with complete authorization, transition, conflict,
and atomicity rules.

**Files:** Modify `backend/app/services/authorization.py` only for centralized lock-compatible
resolution; complete `backend/app/services/tickets.py` and `backend/app/api/routes/tickets.py`; add
update cases to `backend/tests/test_tickets.py`.

**Dependencies:** M4-01, M4-03, M3 assignment/status policies, and PostgreSQL row locking.

**Approach:** Resolve and lock the tenant/ownership-scoped Ticket. Validate all supplied fields
before applying either. Enforce normal transitions `open -> in_progress -> resolved -> closed` for
Admin/Agent and only `resolved -> open` for the owning Customer. Treat same status as a no-op.
Resolve assignment targets through the M3 policy; Admin can assign/reassign a same-business Agent;
Agent can select only self when unassigned or already self and receives 409 when another Agent owns
the Ticket. Commit a material update once, roll back every failure, refresh relationships, and
return detail shape.

**Security:** Never lock or mutate a Ticket outside the current User's authorized query scope.
Customer cannot assign; Agent cannot assign another user or take another Agent's Ticket; foreign or
non-Agent targets remain hidden behind the generic 404. A combined request cannot partially commit
if either operation fails.

**Acceptance:** All allowed transitions and assignments succeed; forbidden roles return 403;
foreign/inaccessible records return 404; conflicts and invalid transitions return documented 409
codes; invalid data returns 422; same-status is a no-op; closed is terminal; combined updates are
atomic; competing Agent claims yield one owner and one conflict without last-write-wins takeover.

**Verification commands:** Run focused PATCH transition/assignment/atomicity/concurrency tests,
M3 policy regressions, and the guarded full suite.

### M4-05 — Complete adversarial integration and regression coverage

**Objective:** Prove that the four real HTTP endpoints enforce the approved contracts and preserve
M1-M3 behavior.

**Files:** Complete `backend/tests/test_tickets.py`; modify existing tests only for a demonstrated,
nonduplicative regression gap.

**Dependencies:** M4-01 through M4-04 and a migrated disposable PostgreSQL database ending in
`_test`.

**Approach:** Use TestClient with the established dependency override and real PostgreSQL rows.
Build deterministic two-business, multi-role fixtures. Include failure injection for first-Message
persistence and two independent database transactions for the Agent-claim race. Assert database
state in addition to HTTP responses.

**Security:** Exercise forged payload identity fields, refresh/missing/invalid authentication,
cross-tenant and cross-Customer access, target-user probing, unauthorized role operations, and
response secret omission. Do not weaken existing assertions or mock away database scoping.

**Acceptance:** Every case in Section 13 passes; existing M1-M3 tests remain green; test cleanup
cannot operate on a database whose name lacks the `_test` suffix; no test claims M5 behavior.

**Verification commands:** Run focused `tests/test_tickets.py`, M2/M3 security regressions, M1 model
tests, and the guarded full suite from Section 15.

### M4-06 — Final verification and execution-record update

**Objective:** Review the completed M4 diff, record only executed results, and stop before M5.

**Files:** Update this execution plan with implementation files, exact command outcomes, security
findings, failures, and remaining limitations. No unrelated documentation is expected.

**Dependencies:** M4-01 through M4-05.

**Approach:** Run all applicable Section 15 commands, inspect route/OpenAPI output and Git scope,
scan changed files for credentials, and compare behavior with requirements/security/API docs. Do
not move this plan to `completed/` until the milestone acceptance review authorizes it.

**Security:** Confirm no endpoint omits authentication, tenant scope, ownership, role checks, or
transaction rollback. Confirm logs/responses expose neither tokens, password hashes, SQL errors,
nor cross-tenant existence.

**Acceptance:** Actual PASS/FAIL/NOT RUN results are recorded; failures are not hidden; no critical
M4 security defect remains; no M5, frontend, dependency, migration, or unrelated change appears.

**Verification commands:** Run the complete command list in Section 15 plus `git diff --check`,
`git status --short`, and a changed-scope credential scan.

## 8. REST API Contracts

| Method and path | Access | Success | Contract |
|---|---|---:|---|
| `GET /tickets` | Authenticated Admin, Agent, Customer | 200 | Optional `status`; Admin/Agent see own business, Customer owns only; `updated_at` descending; `{\"data\": []}` when empty |
| `POST /tickets` | Customer only | 201 | Strict `subject`, `category`, `priority`, `message`; server derives tenant/owner/sender, starts `open` and unassigned, persists Ticket + Message atomically |
| `GET /tickets/{id}` | Authorized viewer | 200 | Core Ticket plus Customer and optional assignee public identity; inaccessible and missing return identical 404 |
| `PATCH /tickets/{id}` | Operation-specific | 200 | One or both of `status` and non-null `assigned_agent_id`; assignment and status are validated and committed atomically; returns detail shape |

Common errors remain the project envelope: 401 missing/invalid access authentication, 403 valid
identity without operation permission, 404 missing/inaccessible Ticket or hidden invalid assignment
target, 409 assignment conflict/invalid state transition/terminal Ticket, and 422 request or query
validation failure.

M4 persists status changes but does not broadcast them. The API contract's post-commit real-time
status event is deferred to M5 and must only broadcast committed state.

## 9. Authorization Matrix

| Operation | Admin | Agent | Customer |
|---|---|---|---|
| List tickets | All in own business | All in own business | Own tickets only |
| Create ticket | 403 | 403 | Yes, as self in own business |
| View detail | Own-business Ticket | Own-business Ticket | Own Ticket only |
| Normal status transition | Yes | Yes | No |
| `resolved -> open` | No | No | Own Ticket only |
| Assign/reassign Agent | Same-business Agent | Self only if unassigned/already self | No |
| Take Ticket owned by another Agent | Admin may reassign | 409 conflict | No |

Every single-resource action first applies the tenant/ownership resource scope. Therefore an
otherwise privileged action against a foreign Ticket returns 404 before action-specific behavior
can reveal information.

## 10. Database Transaction Strategy

### Creation

1. Validate the strict request and Customer role.
2. Construct Ticket with server-derived business/customer/default state.
3. Construct the initial Message with the authenticated Customer as sender and the new Ticket as
   parent.
4. Add both to the same Session and commit once.
5. On any flush/commit failure, roll back the Session and re-raise/map safely.
6. Refresh/load only after successful commit and return committed state.

A targeted test will force Message persistence failure and assert from a separate transaction that
neither row exists.

### Update and concurrency

1. Select the authorized Ticket using tenant/ownership predicates and PostgreSQL row locking.
2. Validate every requested assignment and transition against the locked current state.
3. Apply no changes until all requested operations pass.
4. Commit once; roll back on any exception.
5. Refresh and return committed detail state.

The Ticket row lock serializes simultaneous Agent claims. After the first transaction commits, the
second evaluates the now-assigned state and returns 409 if the owner is another Agent. This avoids
an unnecessary distributed lock and is compatible with the required M5 close/message locking
strategy. Tests will use separate sessions/connections; a single transactional fixture cannot
prove concurrency behavior.

## 11. Security Invariants

- Identity, role, and `business_id` come from the authenticated database User, never from payload or
  mutable JWT role/tenant claims.
- Every Ticket query is scoped to `current_user.business_id`; Customer reads/writes additionally
  require ownership.
- Missing, cross-tenant, and cross-Customer Ticket identities share one non-disclosing 404.
- List queries apply tenant/ownership predicates themselves and cannot rely on frontend filtering.
- Creation is Customer-only and derives Ticket owner, tenant, Message sender, initial status, and
  null assignment on the server.
- Ticket and first Message either both commit or neither commits.
- Assignment targets exist in the Ticket business and have the Agent role. Cross-tenant/non-Agent
  targets are not disclosed.
- Agents can claim only for themselves and cannot overwrite another Agent's claim.
- Status transitions are backend-enforced; closed is terminal; only an owning Customer may reopen a
  resolved Ticket.
- Combined PATCH operations are all-or-nothing and validated against locked current state.
- Responses expose explicit public fields only and never password hashes, credentials, SQL text, or
  internal exceptions.
- M4 does not read message history, accept chat messages, or broadcast events.

## 12. Testing Strategy

Use a new guarded PostgreSQL-backed `backend/tests/test_tickets.py`. Prefer endpoint integration
tests through TestClient and assert persisted rows with SQLAlchemy. Reuse existing M2 test helpers
where appropriate without creating a broad shared-fixture refactor.

Coverage groups:

- Schema/OpenAPI: route presence, security scheme, strict fields, supported enums, UUID parsing,
  length constraints, empty/null PATCH behavior, and standard 422 envelopes.
- Authentication/RBAC: missing/invalid/refresh tokens; Customer-only creation; operation-specific
  PATCH permissions.
- Listing: two-business isolation, Customer ownership, optional status filter, invalid filter,
  deterministic latest-activity order, and empty array.
- Creation: server-derived identity/defaults, first Message sender/body, one-transaction success,
  and rollback when Message insertion fails.
- Detail: Admin/Agent own-business access, Customer ownership, and identical missing/cross-tenant/
  cross-Customer 404 responses.
- Status: every allowed normal transition, Customer reopen, role denials, skipped/invalid
  transitions, same-status no-op, closed terminal behavior, and response/database timestamps.
- Assignment: Admin assign/reassign, Agent self-claim/already-self no-op, Agent-other 403,
  already-owned 409, Customer 403, and hidden foreign/non-Agent targets.
- Atomic update: combined valid update succeeds together; invalid status or assignment leaves both
  persisted values unchanged.
- Concurrency: two Agents claim one unassigned Ticket using separate sessions; exactly one succeeds,
  one receives conflict, and the persisted winner is not overwritten.
- Regression: M1 constraints/models, M2 auth/users, M3 policies, error envelopes, and password-hash
  omission remain green.

No test in M4 will claim message-history, WebSocket authorization, broadcast, or closed-ticket chat
behavior; those belong to M5.

## 13. Acceptance Criteria

- Exactly the four approved Ticket REST operations are implemented and documented in OpenAPI.
- All endpoints require a valid access token; refresh tokens are rejected.
- Ticket list/detail/update queries enforce tenant isolation and Customer ownership as applicable.
- Cross-tenant and cross-Customer single-resource requests return the documented hidden 404.
- Customers alone can create Tickets, with server-derived tenant/owner/sender/default fields.
- Ticket and first Message persistence is atomic, including verified rollback on failure.
- Status filtering validates allowed values; lists are latest-activity ordered and may be empty.
- Status transitions exactly follow the approved lifecycle and same-status no-op rule.
- Admin assignment and Agent self-assignment follow target tenant/role and conflict rules.
- Concurrent self-assignment cannot silently overwrite the first successful Agent.
- Combined status/assignment PATCH requests commit entirely or not at all.
- Standard 401/403/404/409/422 envelopes are preserved; explicit responses expose no secrets.
- Existing M1-M3 tests pass without weakened assertions.
- No new dependency, migration, frontend feature, M5 behavior, or unrelated refactor is introduced.
- Actual validation outcomes are recorded before M4 is declared complete.

## 14. Verification Commands

Run from `backend/` unless stated otherwise. Database commands must resolve to PostgreSQL and a
database name ending in `_test`. Use `helpdesk_m4_test`; never downgrade, truncate, or reset a
valuable database.

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m compileall -q app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff check app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff format --check app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run mypy app tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run alembic heads
```

Use this guarded wrapper for database-backed pytest and Alembic drift checks:

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m4_test'); assert url.get_backend_name() == 'postgresql' and (url.database or '').endswith('_test'); test_url=url.render_as_string(hide_password=False); os.environ['DATABASE_URL']=test_url; os.environ['TEST_DATABASE_URL']=test_url; os.environ['M1_TEST_DATABASE_URL']=test_url; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','tests/test_tickets.py','--tb=short']))"
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m4_test'); assert url.get_backend_name() == 'postgresql' and (url.database or '').endswith('_test'); test_url=url.render_as_string(hide_password=False); os.environ['DATABASE_URL']=test_url; os.environ['TEST_DATABASE_URL']=test_url; os.environ['M1_TEST_DATABASE_URL']=test_url; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','tests/test_auth.py','tests/test_users.py','tests/test_m2_integration.py','tests/test_authorization.py','tests/test_models.py','--tb=short']))"
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m4_test'); assert url.get_backend_name() == 'postgresql' and (url.database or '').endswith('_test'); test_url=url.render_as_string(hide_password=False); os.environ['DATABASE_URL']=test_url; os.environ['TEST_DATABASE_URL']=test_url; os.environ['M1_TEST_DATABASE_URL']=test_url; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','--tb=short']))"
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m4_test'); assert url.get_backend_name() == 'postgresql' and (url.database or '').endswith('_test'); os.environ['DATABASE_URL']=url.render_as_string(hide_password=False); get_settings.cache_clear(); from alembic.config import main; main(argv=['check'])"
```

Run from the repository root after implementation:

```bash
git diff --check
git status --short
```

The disposable database must be created and upgraded to the single Alembic head before tests if it
does not already exist. The M4 implementation does not plan a downgrade or schema mutation.

## 15. Risks and Trade-offs

- Shared-schema tenancy makes one omitted predicate dangerous. Central single-resource resolution,
  explicit list predicates, and adversarial two-business endpoint tests mitigate this risk.
- Foreign keys cannot enforce that Ticket Customer/assignee belongs to the same business or that an
  assignee has Agent role. These remain explicit service checks; M4 tests must prove them.
- Pessimistic row locking is PostgreSQL-specific and may reduce throughput for simultaneous writes
  to one Ticket, but it is simple, local, and correct for this MVP. Lock scope must remain short.
- A TestClient request race may be timing-sensitive. The concurrency test should coordinate
  separate transactions with a barrier and assert final database state, not rely only on response
  order.
- `updated_at` is an activity timestamp. Avoiding updates for pure no-ops preserves meaningful list
  order; material state changes must advance it. M5 must later update it for committed messages.
- Nested relationship loading can introduce N+1 queries. Select-in/joined eager loading will be
  limited to fields required by list/detail responses rather than adding repository abstractions.
- The contract does not define unassignment, so rejecting null avoids inventing behavior. A future
  requirement would need an explicit contract and authorization decision.
- The API contract mentions status-event broadcast after commit, but implementing it in M4 would
  cross the M5 boundary. M4 will persist status only and explicitly document this deferred behavior.
- Existing stateless, non-rotating refresh tokens and pending real-browser cookie verification are
  inherited limitations and are not changed by M4.
- Local PostgreSQL access may again be denied by the execution sandbox. Any blocked database check
  will be recorded as NOT RUN with the exact error; it will not be claimed as passing.

## 16. Definition of Done

M4 is done only when M4-01 through M4-06 are implemented after explicit approval, all acceptance
criteria have evidence from executed checks, the complete backend suite passes against a guarded
disposable PostgreSQL database (or exact environmental blockers are reported), and no critical
Ticket authorization, isolation, transaction, or concurrency defect remains.

The execution record must list changed files, results, failures, security findings, and remaining
limitations. M4 must not be moved to `completed/`, committed, pushed, or followed by M5 without
separate user review and authorization.

## 17. Phase 2 Implementation Record — 2026-10-10

### Implemented scope

- M4-01: Added strict Ticket create/update and explicit response schemas, registered exactly the
  four planned Ticket operations, and enabled `PATCH` in the existing CORS method allow-list.
- M4-02: Added tenant/ownership-scoped listing and Customer-only creation of a Ticket plus its
  initial Message in one Session transaction.
- M4-03: Added Ticket detail using the centralized M3 tenant/ownership resolver and explicit public
  Customer/assignee identities.
- M4-04: Added row-locked, all-or-nothing assignment and status updates, including normal lifecycle
  transitions, owning-Customer reopen, same-status no-op, Agent self-claim rules, and 409 conflict
  handling.
- M4-05: Added the preliminary Phase 2 endpoint, isolation, transaction, and concurrency coverage
  in `tests/test_tickets.py`. Comprehensive Phase 3 adversarial verification remains pending.
- M4-06: Recorded the Phase 2 implementation and executed checks here. Final milestone verification
  is intentionally deferred to the separately approved Phase 3.

### Files created

- `backend/app/api/routes/tickets.py`
- `backend/app/schemas/ticket.py`
- `backend/app/services/tickets.py`
- `backend/tests/test_tickets.py`

### Files modified

- `backend/app/api/router.py`
- `backend/app/main.py`
- `backend/app/services/authorization.py`
- `exec-plans/active/M4-ticket-management.md`

No dependency, model, Alembic revision, frontend, README, M5, or unrelated documentation change was
required.

### Database and security behavior

- Ticket list predicates always include the authenticated database User's `business_id`; Customer
  lists additionally include their `customer_id`.
- Single-Ticket reads and writes reuse the non-disclosing M3 resolver. Update adds optional
  PostgreSQL row locking without weakening the existing predicates.
- Creation accepts no client-controlled tenant, owner, sender, assignee, or initial status and
  commits the Ticket and initial Message together. Forced post-flush commit failure was verified to
  leave neither row persisted.
- Assignment targets remain limited to same-business Agents. Admin may assign/reassign, while an
  Agent may claim only as self and cannot overwrite another Agent's claim.
- All requested PATCH operations are validated before mutation and committed once. Two independent
  concurrent Agent sessions produced exactly one winner and one `ASSIGNMENT_CONFLICT` response.
- Explicit response schemas contain no password hash or token field.

### Executed validation

- Disposable PostgreSQL database `helpdesk_m4_test` was created only after verifying the target and
  upgraded to Alembic head `a3930ac451be`: **PASS**.
- Focused M4 suite (`tests/test_tickets.py`): **PASS — 14 passed, 1 warning**.
- Complete backend pytest suite with both `TEST_DATABASE_URL` and the legacy
  `M1_TEST_DATABASE_URL` targeting the disposable database: **PASS — 90 passed, 1 warning**.
- `git diff --check`: **PASS**.
- `ruff check app alembic tests`: **PASS**.
- `ruff format --check app alembic tests`: **PASS — 42 files already formatted**.
- `mypy app tests`: **PASS — no issues in 40 source files**.
- `python -m compileall -q app alembic tests`: **PASS**.
- `alembic heads`: **PASS — one head, `a3930ac451be`**.
- Guarded `alembic check` against `helpdesk_m4_test`: **PASS — no new upgrade operations
  detected**.

The first complete-suite invocation supplied only `TEST_DATABASE_URL`; it produced 60 passing tests
and 26 setup errors because the existing M1 model tests separately require `M1_TEST_DATABASE_URL`.
This was a test-runner environment configuration error, not an application assertion failure. The
corrected guarded invocation supplied both variables and produced the 90-test passing result above.

The single warning in both successful pytest runs is an existing `StarletteDeprecationWarning` from
FastAPI's TestClient compatibility layer. No dependency was changed during M4.

### Remaining limitations and risks

- Comprehensive Phase 3 Ticket security/integration verification and Phase 4 final review remain
  pending; M4 is not marked complete.
- Message history, additional message creation, WebSocket authorization/chat, status broadcasts,
  and closed-ticket message rejection remain correctly deferred to M5.
- Same-business Customer/assignee integrity cannot be represented completely by the existing
  foreign keys and therefore remains enforced in application services.
- Row locking is intentionally PostgreSQL-specific and assumes all future competing Ticket writers
  follow the same locking discipline.
- The inherited stateless refresh-token behavior and pending real-browser cookie verification were
  not changed by this milestone.

## 18. Phase 3 Verification Record — 2026-10-10

### Scope and changes

Phase 3 audited the four M4 Ticket operations against the approved plan and expanded
`backend/tests/test_tickets.py` from 14 to 36 collected cases. No application defect requiring a
production-code change was found. The added evidence covers:

- missing, invalid, and refresh-token rejection on every Ticket operation;
- rejection of every client-controlled creation identity/state field;
- a targeted Message-insert failure proving Ticket/Message rollback and Session recovery;
- cross-tenant Admin, Agent, and Customer detail/update denial plus same-tenant Customer ownership;
- malformed Ticket UUID validation;
- missing, blank, and oversized Ticket creation fields;
- all four status filters plus deterministic ordering when activity timestamps tie;
- skipped, backward, and staff-only reopen transition rejection;
- successful combined assignment/status persistence and database activity timestamp behavior; and
- live PostgreSQL inspection of required Ticket foreign keys, check constraints, and the
  `(business_id, status)` index.

Existing tests continue to cover list tenant/owner/filter/order rules, all documented status and
assignment paths, invalid combined-update atomicity, response secret omission, and a two-session
simultaneous Agent claim with exactly one winner.

Files changed during Phase 3:

- `backend/tests/test_tickets.py`
- `exec-plans/active/M4-ticket-management.md`

No runtime source, dependency, migration, frontend, README, or M5 file was changed.

### Executed validation

All database commands used the explicitly guarded disposable PostgreSQL database
`helpdesk_m4_test`.

- Baseline focused M4 suite before coverage expansion: **PASS — 14 passed, 1 warning**.
- First expanded focused run: **FAIL — 1 failed, 22 passed, 1 warning**. The new test expected the
  undocumented code `AUTH_REQUIRED` for missing credentials; established M2 behavior correctly
  returned `AUTH_TOKEN_INVALID`. The test expectation was corrected without changing application
  behavior.
- Corrected initial expanded focused M4 suite: **PASS — 23 passed, 1 warning**.
- Final focused M4 suite after completing the input, ordering, and transition matrices:
  **PASS — 36 passed, 1 warning**.
- M1-M3 regression selection (`test_auth.py`, `test_users.py`, `test_m2_integration.py`,
  `test_authorization.py`, and `test_models.py`): **PASS — 76 passed, 1 warning**.
- Initial complete backend suite after the first coverage expansion:
  **PASS — 99 passed, 1 warning**.
- Final complete backend suite after completing all Phase 3 cases:
  **PASS — 112 passed, 1 warning**.
- `python -m compileall -q app alembic tests`: **PASS**.
- `ruff check app alembic tests`: **PASS**.
- `ruff format --check app alembic tests`: **PASS — 42 files already formatted**.
- `mypy app tests`: **PASS — no issues in 40 source files**.
- `alembic heads`: **PASS — one head, `a3930ac451be`**.
- Guarded `alembic check`: **PASS — no new upgrade operations detected**.
- `git diff --check`: **PASS**.

The one warning is the pre-existing `StarletteDeprecationWarning` emitted through FastAPI's
TestClient compatibility layer. Phase 3 did not change dependencies.

### Security findings and remaining limitations

- No critical Ticket authorization, tenant-isolation, transaction, concurrency, schema, or secret
  exposure defect was found in the approved M4 scope.
- Cross-tenant and cross-Customer single-resource access remains a non-disclosing
  `TICKET_NOT_FOUND` 404; list scoping and server-derived creation identity were verified through
  real endpoint/database integration.
- Refresh tokens cannot authenticate Ticket endpoints, and explicit response schemas expose no
  password hash or token.
- Same-business Customer/assignee integrity remains an application-service invariant because the
  current foreign keys cannot express it fully; regression and endpoint tests cover the service
  enforcement.
- Message history, message sending, WebSocket authorization/chat, closed-ticket message rejection,
  and status broadcasts remain intentionally deferred to M5.
- Stateless refresh-token behavior and real-browser cookie verification remain inherited
  limitations outside M4.

**Phase 3 result: READY FOR PHASE 4 REVIEW.** Do not move this plan to `completed/`, begin Phase 4,
or proceed to M5 without separate approval.
