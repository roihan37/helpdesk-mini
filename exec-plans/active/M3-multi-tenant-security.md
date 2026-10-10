# M3 - Multi-Tenant Authorization & Security

## Status

**IMPLEMENTED, PENDING PHASE 3 VERIFICATION — 2026-10-10.** M3 Phase 2 implementation and
preliminary validation are complete. The plan remains active; M3 has not been marked complete and
M4 has not started.

## 1. Objective

Establish and verify the smallest reusable backend authorization foundation needed by the future
ticket and WebSocket milestones while preserving the completed M2 authentication and
business-user-management behavior.

M3 will:

- keep `get_current_user` as the trusted authentication context;
- add minimal reusable role checks without replacing the existing JWT implementation;
- centralize ticket tenant and Customer-ownership resolution so M4 and M5 do not duplicate it;
- add policy-level PostgreSQL tests for cross-tenant and ownership behavior;
- rerun the M2 security regression suite; and
- document the security checks that M4 and M5 must integrate and test at their real endpoints.

## 2. Scope

- Verify JWT signature, expiry, access-token type, and database-backed current-user behavior through
  existing M2 tests.
- Preserve Admin-only, own-business user management.
- Add a small reusable role-authorization primitive for `admin`, `agent`, and `customer`.
- Add one centralized ticket resolver/policy that applies tenant scope and Customer ownership in
  the database query and returns the documented non-disclosing 404 response.
- Test the authorization policy against migrated PostgreSQL tables using disposable test data.
- Verify current endpoints have no M2 authentication, role, tenant, or response-contract
  regressions.
- Record explicit integration requirements for later ticket, message, and WebSocket code.

## 3. Out of Scope

- Ticket list, create, detail, update, assignment, or status endpoints and services (M4).
- Ticket transition, assignment concurrency, or first-message transaction implementation (M4).
- Message history, message creation, WebSocket connection management, and broadcasting (M5).
- Frontend authorization or pages (M6).
- Seed/demo data and final-delivery work (M7).
- New authentication schemes, JWT utilities, password behavior, middleware, authorization
  frameworks, dependencies, infrastructure, or database migrations.
- Claiming endpoint integration coverage for endpoints that do not yet exist.

## 4. Existing Security Implementation

### M2 completion evidence

`exec-plans/completed/M2-authentication.md` is marked **COMPLETE — 2026-10-10**. Its Phase 4
record reports 65 passing tests, no failures, a single Alembic head with no model drift, and passing
OpenAPI and security-contract checks. The current Git history contains the M2 implementation,
integration-test, and milestone-finalization commits, and the worktree was clean when M3 planning
began.

No unresolved critical current-scope M2 vulnerability was found. The documented stateless,
non-rotating refresh-token design and unperformed real-browser cookie check are known MVP/testing
limitations, not blockers for the M3 authorization foundation.

Current planning-review validation (2026-10-10) also passed: compile/import validation, Ruff lint,
Ruff format check, strict mypy, `alembic heads`, and the focused non-database M2 authentication/user
suite (14 passed, 0 failed, with one external Starlette `httpx` deprecation warning). The guarded
PostgreSQL full suite was not rerun during this planning-only phase; its latest recorded Phase 4
result remains 65 passed, 0 failed.

### Reusable implementation already present

- `app.core.security.decode_token` verifies the configured signature algorithm, required claims,
  expiration, UUID subject, and expected token type.
- `app.api.dependencies.get_current_user` accepts only Bearer access tokens, resolves the User and
  Business from PostgreSQL, and rejects a missing/deleted user. Authorization therefore does not
  trust JWT `role` or `business_id` claims.
- `app.api.dependencies.require_admin` returns 403 for a current non-Admin user.
- `app.services.users.list_business_users` explicitly filters by the trusted Admin
  `business_id`; user creation receives that server-derived tenant ID.
- Request schemas reject client-controlled `business_id` and Admin-role injection for managed user
  creation.
- M2 tests cover missing/invalid/wrong-type authentication, forged role/tenant claims, Admin-only
  user management, own-business list/create behavior, and global email uniqueness.
- M1 database constraints enforce required foreign-key existence, allowed role/priority/status
  values, unique business slug/email, nullable assignment, and the ticket tenant/status index.

### Gap classification

| Requirement | Classification | Evidence or required work |
|---|---|---|
| JWT signature, expiry, and access/refresh type separation | IMPLEMENTED AND VERIFIED | `core/security.py`; M2 unit/integration tests |
| Current User resolved from PostgreSQL | IMPLEMENTED AND VERIFIED | `get_current_user`; forged/deleted identity tests |
| Trusted role and business membership from current User | IMPLEMENTED AND VERIFIED | JWT role/tenant manipulation tests |
| Missing/invalid authentication returns 401 | IMPLEMENTED AND VERIFIED | dependency and integration tests |
| Admin-only user management | IMPLEMENTED AND VERIFIED | `require_admin`; role tests |
| User list/create constrained to Admin business | IMPLEMENTED AND VERIFIED | service predicates and PostgreSQL tests |
| Generic reusable role dependency/check | MISSING | Only the Admin-specific dependency exists |
| Central ticket tenant/Customer-ownership resolver | MISSING | No ticket authorization service exists |
| Ticket endpoint tenant and action enforcement | DEFERRED TO M4 | No ticket endpoints exist |
| Customer/assignee same-business and assignee Agent-role validation | DEFERRED TO M4 | Foreign keys do not enforce cross-row tenant/role integrity |
| Message sender authorization and closed-ticket rejection | DEFERRED TO M5 | No message service exists |
| Message-history parent-ticket authorization | DEFERRED TO M5 | No message endpoint exists |
| WebSocket pre-accept and per-message authorization | DEFERRED TO M5 | No WebSocket endpoint exists |
| Browser refresh-cookie behavior in a real browser | IMPLEMENTED BUT NOT VERIFIED | HTTP integration behavior passed; manual browser check remains |

## 5. Authorization Architecture

Keep authorization explicit within the modular monolith:

1. `get_current_user` authenticates an access token and returns the current database User.
2. A minimal role check rejects a valid user whose role cannot perform an operation with 403.
3. A service-level ticket resolver queries by both ticket ID and the current User's trusted
   `business_id`; for Customers it adds `customer_id == current_user.id` to the same query.
4. A missing, cross-business, or other-Customer ticket produces the same 404
   `TICKET_NOT_FOUND` error.
5. M4 services call the resolver before details, updates, assignment, or status work and apply
   action-specific business rules after resource access is established.
6. M5 message history and WebSocket authorization reuse the same resource policy before reading,
   joining a room, or processing an event.

The resolver must not first fetch a ticket by ID and then disclose why access failed. It must not
accept `business_id`, `customer_id`, role, or sender identity from request data as trusted context.
Route-level role checks complement rather than replace service/resource authorization.

## 6. Security Invariants

- Authentication uses a valid, unexpired JWT access token; refresh tokens cannot authenticate
  protected REST or future WebSocket operations.
- The current User, role, and business are loaded from PostgreSQL after token validation.
- Every protected ticket query includes `Ticket.business_id == current_user.business_id`.
- Customer ticket queries additionally include `Ticket.customer_id == current_user.id`.
- Admin and Agent ticket visibility is business-wide; Agent assignment is not required for view or
  reply access.
- Missing or invalid authentication returns 401; a disallowed role/action returns 403; missing or
  inaccessible ticket identity returns 404 without confirming existence.
- Messages inherit tenant scope only through an already-authorized parent ticket.
- M4 must verify a ticket Customer and assigned Agent belong to the ticket business, and that the
  assignee has the Agent role. Existing foreign keys alone do not enforce these invariants.
- M5 must derive the sender from authenticated context, recheck ticket access before sensitive
  operations, reject closed-ticket messages, commit before broadcast, and isolate broadcasts by
  authorized ticket room.
- Admin can inspect same-business chat but cannot send messages, per the documented API/security
  decision.

## 7. Ordered Implementation Tasks

### M3-01 — Preserve and verify the trusted M2 authentication context

**Objective:** Confirm the M3 foundation reuses the database-backed M2 identity and does not
duplicate or weaken JWT authentication.

**Existing files to inspect:**

- `backend/app/core/security.py`
- `backend/app/api/dependencies.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/users.py`
- `backend/app/services/users.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_users.py`
- `backend/tests/test_m2_integration.py`

**Expected files to modify:** None unless verification reveals a concrete current-scope defect. Any
such defect must be narrowly fixed and documented before later tasks proceed.

**Dependencies:** Completed M2 and a configured disposable PostgreSQL test database.

**Implementation approach:** Run the focused M2 unit and integration regressions first. Confirm
that current authorization decisions use the database User and that access-only dependencies reject
refresh tokens. Do not recreate token parsing or current-user resolution.

**Security implications:** This establishes that all later policy inputs are trusted and prevents
forged/stale JWT role or tenant claims from becoming authorization inputs.

**Acceptance criteria:** The M2 authentication and user-management tests pass; no current endpoint
trusts client/JWT tenant or role data over the database User; no critical M2 regression remains.

**Verification:** Focused `test_auth.py`, `test_users.py`, and guarded `test_m2_integration.py`
commands from Section 10.

### M3-02 — Add minimal reusable role authorization

**Objective:** Provide one explicit, typed role-checking mechanism usable by future routes while
preserving the existing `require_admin` contract.

**Existing files to inspect:**

- `backend/app/api/dependencies.py`
- `backend/app/models/enums.py`
- `backend/app/api/routes/users.py`
- `backend/tests/test_users.py`

**Expected files to modify:**

- `backend/app/api/dependencies.py`
- `backend/tests/test_authorization.py` (new)

**Dependencies:** M3-01.

**Implementation approach:** Extract a small reusable allowed-role dependency/check around the
already-resolved `User`. Keep `require_admin` available to existing routes and backed by the same
logic. Use `UserRole`; do not add middleware, a permission library, or token-claim authorization.

**Security implications:** Consistent role failures return 403 only after authentication; route
role checks remain separate from tenant/ownership checks.

**Acceptance criteria:** Allowed roles receive the same current database User; disallowed roles
receive the standard 403 `FORBIDDEN`; existing Admin endpoints and OpenAPI security remain intact.

**Verification:** Focused role-policy tests plus existing user and OpenAPI tests.

### M3-03 — Centralize ticket resource authorization

**Objective:** Implement a policy-level ticket resolver that M4 REST services and M5 WebSocket
authorization can reuse without duplicating tenant or Customer-ownership logic.

**Existing files to inspect:**

- `backend/app/models/ticket.py`
- `backend/app/models/user.py`
- `backend/app/models/enums.py`
- `backend/app/core/errors.py`
- `backend/app/services/users.py`
- `docs/SECURITY.md`
- `docs/API_CONTRACT.md`

**Expected files to modify:**

- `backend/app/services/authorization.py` (new)
- `backend/app/services/__init__.py` only if an explicit export is useful
- `backend/tests/test_authorization.py`

**Dependencies:** M3-01 and M3-02; migrated disposable PostgreSQL schema.

**Implementation approach:** Query a ticket with both its ID and the trusted current User's
`business_id`. Add the Customer ownership predicate for the Customer role before executing the
query. Return the same standard `TICKET_NOT_FOUND` 404 for absent, cross-business, and
same-business cross-Customer records. Permit same-business Admin and Agent visibility. Keep the
policy independent of an M4 route or request schema.

**Security implications:** Query-time isolation prevents existence disclosure and creates one
reviewable boundary for REST, message-history, and WebSocket access. The helper must never accept a
client-supplied tenant identity.

**Acceptance criteria:** Same-business Admin/Agent and owning Customer resolve the ticket;
cross-business users, non-owning Customers, and nonexistent IDs receive indistinguishable 404
errors; unsupported roles are rejected; tests exercise actual PostgreSQL rows rather than only
mocked query construction.

**Verification:** Guarded `test_authorization.py` PostgreSQL run plus lint, types, and full suite.

### M3-04 — Verify current endpoint security regressions

**Objective:** Prove that the authorization foundation does not regress existing authentication or
business-user-management behavior.

**Existing files to inspect:**

- `backend/tests/test_m2_integration.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_users.py`
- files modified by M3-02 and M3-03

**Expected files to modify:** `backend/tests/test_authorization.py`; existing M2 tests only when a
missing current-endpoint assertion is demonstrated, not to duplicate coverage.

**Dependencies:** M3-02 and M3-03.

**Implementation approach:** Run existing tests for 401 handling, wrong token type, Agent/Customer
denial, tenant-scoped Admin list/create, request tenant injection, forged JWT claims, global email
uniqueness, password non-exposure, and standard errors. Add only nonduplicative regression cases.

**Security implications:** Prevents reusable abstractions from weakening already-verified M2
boundaries.

**Acceptance criteria:** All M2 security scenarios continue to pass, no password hash or internal
exception is exposed, and current 401/403/404/422 semantics remain consistent.

**Verification:** Focused M2 tests, OpenAPI assertion, and the guarded full test suite.

### M3-05 — Record M4/M5 integration contracts and complete verification

**Objective:** Make the future enforcement points explicit, record actual command results, and
finish M3 without claiming unimplemented endpoint coverage.

**Existing files to inspect:**

- `ARCHITECTURE.md`
- `docs/REQUIREMENTS.md`
- `docs/SECURITY.md`
- `docs/API_CONTRACT.md`
- this execution plan

**Expected files to modify:**

- `exec-plans/active/M3-multi-tenant-security.md`

No other documentation change is expected unless implementation exposes a real conflict.

**Dependencies:** M3-01 through M3-04.

**Implementation approach:** Record exact validation results and remaining limitations. Confirm the
M4 handoff requires the centralized resolver for ticket list/detail/update/assignment and
same-business/role integrity checks. Confirm the M5 handoff requires pre-accept and per-message
authorization, access-token-only authentication, closed-ticket rejection, commit-before-broadcast,
and authorized-room isolation.

**Security implications:** Prevents policy-only tests from being mistaken for enforcement at future
HTTP or WebSocket boundaries.

**Acceptance criteria:** Actual checks and failures are recorded; M4/M5 items remain explicitly
deferred; no migration or unrelated documentation change exists; M3 is not advanced to M4
automatically.

**Verification:** Review Git diff/status, scan for secrets, and run every applicable command in
Section 10.

## 8. Required Tests

### Current functionality in M3

- Missing Bearer authentication returns 401.
- Invalid, expired, or tampered access tokens return 401.
- Refresh tokens cannot authorize access-only operations.
- Current User role and tenant come from PostgreSQL despite forged JWT role/tenant claims.
- Agent and Customer cannot list or create business users.
- Admin lists only own-business users and creates users only in the server-derived business.
- Client `business_id` and Admin-role injection are rejected.
- Globally duplicate email remains rejected without leaking database details.
- Generic role policy permits configured roles and returns standard 403 for other roles.
- Same-business Admin and Agent can resolve a ticket.
- Owning Customer can resolve their ticket.
- Cross-business ticket access returns `TICKET_NOT_FOUND` 404.
- Same-business cross-Customer access returns the identical 404.
- Nonexistent ticket access returns the identical 404.

### Deferred endpoint integration coverage

- **M4:** ticket list/detail/create/update/assignment/status authorization; Customer creation and
  ownership; Customer/Agent same-business validation; Agent role validation; transition rules;
  atomic first message; race-safe self-assignment.
- **M5:** message history and creation authorization; Admin read-only enforcement; WebSocket token,
  Origin, tenant, ownership, pre-accept, revalidation, closed-ticket, persistence, and room-broadcast
  behavior.

These deferred scenarios must not be marked passing during M3.

## 9. Acceptance Criteria

- Existing JWT authentication and database-backed current-user resolution remain unchanged or are
  narrowly corrected only if a verified defect exists.
- Existing M2 RBAC and tenant-scoped user management pass their regression tests.
- Reusable role authorization is minimal, typed, and returns the documented 403 response.
- One reusable ticket resolver enforces tenant and Customer ownership at query time.
- Same-business Agent access and owning-Customer access pass against PostgreSQL.
- Cross-business, cross-Customer, and nonexistent ticket access produce the same documented 404.
- No code trusts a client-provided `business_id`, `customer_id`, assignee role, or sender identity.
- No new migration or runtime dependency is introduced.
- Syntax, lint, format, strict typing, focused tests, and the guarded full suite pass, or exact
  blockers are recorded.
- Ticket endpoint integration remains assigned to M4 and WebSocket/message integration to M5.
- No critical current-scope security issue remains and no automatic-failure condition is
  introduced.

## 10. Verification Commands

Run from `backend/`. Commands that touch the database must target a disposable PostgreSQL database
whose name ends in `_test`; never downgrade or clear a valuable database.

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m compileall -q app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff check app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff format --check app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run mypy app tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run pytest -q tests/test_auth.py tests/test_users.py tests/test_authorization.py --tb=short
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m3_test'); test_url=url.render_as_string(hide_password=False); os.environ['DATABASE_URL']=test_url; os.environ['TEST_DATABASE_URL']=test_url; os.environ['M1_TEST_DATABASE_URL']=test_url; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','--tb=short']))"
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run alembic heads
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run alembic check
git diff --check
git status --short
```

The focused test command will become available when M3-02 creates
`tests/test_authorization.py`. The guarded full-suite command is the database integration check;
it must fail safely if the resolved database name does not end in `_test`. No downgrade is required
because M3 does not change schema. M4 and M5 endpoint/WebSocket tests cannot run in M3.

## 11. Dependencies

- Completed M0 project foundation and M1 database schema.
- Completed M2 JWT authentication and business-user-management implementation.
- Python 3.11+, `uv`, and the already-locked backend dependencies.
- Reachable PostgreSQL with an Alembic-upgraded disposable `helpdesk_m3_test` database.
- Existing models and enums for Business, User, Ticket, Message, and roles.
- Existing standard `AppError` envelope and error-code contract.

No new package or Alembic revision is planned.

## 12. Known Risks

- Database foreign keys prove referenced rows exist but cannot prove the ticket Customer/assignee
  shares its business, that an assignee is an Agent, or that a Message sender is authorized. These
  remain mandatory service checks at M4/M5 write boundaries.
- A reusable resolver is only a policy foundation until every future ticket/message/WebSocket
  entry point actually calls it; policy tests are not endpoint integration proof.
- Fetching by ticket ID before tenant/ownership filtering could create an existence side channel;
  the planned query-time predicates and identical 404 prevent this.
- Shared-schema tenancy remains sensitive to omitted filters in future queries. M4 list queries need
  separate explicit tenant and Customer predicates, not only the single-resource resolver.
- The refresh-token strategy remains stateless and non-rotating; compromise cannot be revoked
  immediately. This documented M2 limitation is unchanged by M3.
- Browser cookie behavior has HTTP-level automated coverage but not a completed real-browser
  verification.
- WebSocket query-string tokens may appear in infrastructure logs; M5 must avoid application
  logging and document redaction/HTTPS handling.
- M2 completion evidence records a prior disposable-development migration incident that was
  restored; M3 must use the guarded `_test` database command and perform no schema downgrade.
- Documentation is consistent on 401/403/404 behavior, Customer ownership, Admin read-only chat,
  and milestone boundaries. No conflict requiring a documentation change was found.

## 13. Definition of Done

M3 is complete only after Phase 2 is separately approved and implemented, all M3-01 through M3-05
acceptance criteria are satisfied, applicable validation commands have actually run with results
recorded here, the M2 regression suite remains green, and no critical current-scope authorization
defect remains.

The completed implementation must contain no ticket or WebSocket endpoint, no unrelated refactor,
no unnecessary dependency or migration, and no claim that deferred M4/M5 integration security has
passed. After review, the plan may be moved to `exec-plans/completed/`; M4 must not begin
automatically.

## 14. Phase 2 Implementation Record — 2026-10-10

### Scope adjustment

The approved plan originally deferred all assignment and status validation to M4. The Phase 2
implementation instruction explicitly required reusable assignment and status authorization
policies while keeping mutations and the full transition engine in M4. The smallest compliant
adjustment was applied: M3 now contains policy-only validators for actor, tenant, ownership, and
assignment-target integrity. No ticket mutation, endpoint, request schema, or state-transition
workflow was added.

### Task progress

- **M3-01 complete:** Existing access-token validation and database-backed current-user resolution
  were preserved. The full M2 regression coverage passed, including refresh-token rejection,
  forged JWT role/tenant claims, deleted users, own-business user management, request-field
  injection rejection, and password-hash omission.
- **M3-02 complete:** Added `require_roles` as a minimal reusable check. `require_admin` delegates
  to it while preserving its existing error message and route contract.
- **M3-03 complete:** Added a ticket resolver whose SQL query includes the ticket ID and trusted
  current User business ID, plus Customer ownership for Customer callers. Missing,
  cross-business, and cross-Customer records return the identical `TICKET_NOT_FOUND` response.
- **M3-04 complete:** Added PostgreSQL-backed policy tests and reran all current backend tests.
  Existing `/users` role and tenant behavior remains green; no M2 vulnerability requiring a code
  change was found.
- **M3-05 complete for Phase 2:** Actual preliminary results and the M4/M5 integration boundaries
  are recorded below. Comprehensive Phase 3 review remains pending.

### Files changed

- `backend/app/api/dependencies.py`: reusable role check; existing Admin dependency preserved.
- `backend/app/services/authorization.py`: ticket access, assignment-target, and status-actor
  authorization policies.
- `backend/tests/test_authorization.py`: guarded PostgreSQL policy coverage.
- `exec-plans/active/M3-multi-tenant-security.md`: this Phase 2 record.

No dependency, model, migration, API route, schema, frontend, Message service, or WebSocket file was
changed.

### Policies implemented

- Ticket lookup is query-scoped to `current_user.business_id`; Customer lookup also requires
  `customer_id == current_user.id`.
- Admin and Agent may resolve any ticket in their business; Customers may resolve only owned
  tickets.
- Admin assignment targets must be same-business Agents. Agents may target only themselves.
  Customers cannot assign. Target lookup returns a non-disclosing generic 404 for a foreign-tenant
  or non-Agent user.
- Admin and Agent pass the reusable status actor check. A Customer passes only for reopening their
  own resolved ticket to `open`. Closed tickets are rejected as terminal.
- Normal status-transition validation, persistence, and concurrency behavior remain in M4.

### Preliminary validation results

All commands ran from `backend/` unless noted.

| Check | Result |
|---|---|
| `python -m compileall -q app alembic tests` | PASS |
| `ruff check app alembic tests` | PASS |
| `ruff format --check app alembic tests` | PASS — 38 files already formatted |
| `mypy app tests` | PASS — no issues in 36 source files |
| Focused auth/user/authorization suite against `helpdesk_m3_test` | PASS — 23 passed, 0 failed |
| Full backend suite against `helpdesk_m3_test` | PASS — 74 passed, 0 failed |
| `alembic heads` | PASS — `a3930ac451be` is the single head |
| `alembic check` against `helpdesk_m3_test` | PASS — no new upgrade operations |
| `git diff --check` | PASS |
| Changed-scope hardcoded credential scan | PASS — no match; `.env` was excluded |

Both pytest runs emitted one external `StarletteDeprecationWarning` concerning the TestClient
`httpx` compatibility layer. It does not represent a test failure. The disposable
`helpdesk_m3_test` database was created and upgraded to head; no downgrade or destructive database
operation was performed.

### Security and deferred integration handoff

- Trusted identity, role, and business continue to come from the database User resolved by the M2
  access-token dependency. The new policies accept that trusted User and never accept tenant,
  customer, role, or sender identity from request data.
- M4 must call the resolver/policies from every applicable ticket route/service, add explicit
  tenant/ownership predicates to list queries, validate the ticket Customer on creation, implement
  the complete transition map, make first-message creation atomic, and make self-assignment
  race-safe. Policy tests here are not endpoint-integration proof.
- M5 must authorize through the parent ticket before message history, sending, and WebSocket
  acceptance; enforce Admin read-only chat; revalidate sensitive operations; reject closed-ticket
  messages; commit before broadcast; and isolate connections/broadcasts by ticket. No M5 behavior
  is claimed as tested.

### Remaining risks and Phase 3 work

- Future endpoints can still become unsafe if they fail to invoke these policies; M4/M5 integration
  and endpoint-level tests remain mandatory.
- Cross-row Customer/business, assignee/business/role, and Message-sender authorization invariants
  are service-level checks because the current foreign keys do not encode them all.
- The existing stateless, non-rotating refresh-token limitation and outstanding real-browser cookie
  verification are unchanged.
- Phase 3 must review the final diff, repeat/extend adversarial authorization verification, confirm
  error-envelope consistency, and decide milestone completion. M3 remains active until that review.
