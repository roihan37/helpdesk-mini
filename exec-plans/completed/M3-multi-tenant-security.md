# M3 - Multi-Tenant Authorization & Security

## Status

**COMPLETE — 2026-10-10.** M3 implementation, security testing, final code review, and
documentation review are complete. No critical current-scope security defect remains. M4 has not
started.

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

### Remaining risks and Phase 3 work recorded at the end of Phase 2

- Future endpoints can still become unsafe if they fail to invoke these policies; M4/M5 integration
  and endpoint-level tests remain mandatory.
- Cross-row Customer/business, assignee/business/role, and Message-sender authorization invariants
  are service-level checks because the current foreign keys do not encode them all.
- The existing stateless, non-rotating refresh-token limitation and outstanding real-browser cookie
  verification are unchanged.
- At the end of Phase 2, Phase 3 still needed to review the final diff, repeat/extend adversarial
  authorization verification, confirm error-envelope consistency, and decide readiness for final
  review. Section 15 records the completed Phase 3 validation, and Section 16 records the completed
  Phase 4 review and final milestone decision.

## 15. Phase 3 Security Testing and Validation Record — 2026-10-10

### Validation outcome

M3 Phase 3 is **READY FOR PHASE 4 REVIEW**. The final guarded backend suite passed 76 tests with
zero failures, including 40 focused M2 authentication/user-management regressions, 10 M3
authorization policy tests, and 26 focused M1 model/constraint tests. No current-scope production
security defect was found, and no production source file, dependency, model, or migration required
a change.

Two nonduplicative coverage gaps were identified and closed:

- Added an endpoint regression proving an already-issued access token is rejected with the standard
  401 response after its User is deleted from PostgreSQL.
- Added policy regressions proving cross-tenant staff cannot use either assignment-target or status
  authorization against a foreign ticket, and receive the same non-disclosing
  `TICKET_NOT_FOUND` 404 response.

These were missing assertions, not observed authorization bypasses. Both new tests passed against
the disposable PostgreSQL database.

### Tests modified

- `backend/tests/test_m2_integration.py`: added
  `test_me_rejects_access_token_after_user_is_deleted`.
- `backend/tests/test_authorization.py`: added
  `test_assignment_and_status_policies_hide_ticket_from_cross_tenant_staff`.

No test assertion was weakened and no authorization check was removed.

### Exact commands and results

All commands ran from `backend/` except the Git commands, which ran from the repository root.
Database commands derived the configured local PostgreSQL URL, replaced only the database name
with `helpdesk_m3_test`, asserted the PostgreSQL driver and `_test` suffix, and set `DATABASE_URL`,
`TEST_DATABASE_URL`, and `M1_TEST_DATABASE_URL` only inside the test process.

The exact guarded pytest command body was executed with each argument list shown in the table:

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; url=make_url(get_settings().database_url).set(database='helpdesk_m3_test'); assert url.get_backend_name() == 'postgresql' and (url.database or '').endswith('_test'); test_url=url.render_as_string(hide_password=False); os.environ['DATABASE_URL']=test_url; os.environ['TEST_DATABASE_URL']=test_url; os.environ['M1_TEST_DATABASE_URL']=test_url; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(PYTEST_ARGUMENT_LIST))"
```

| Command | Result |
|---|---|
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m compileall -q app alembic tests` | PASS |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff check app tests alembic` | PASS |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff format --check app tests alembic` | PASS — 38 files already formatted |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run mypy app tests` | PASS — no issues in 36 source files |
| Guarded pytest with `PYTEST_ARGUMENT_LIST=['-q','tests/test_auth.py','tests/test_users.py','tests/test_authorization.py','tests/test_m2_integration.py','--tb=short']` | PASS — 50 passed, 0 failed, 1 external warning |
| Guarded pytest with `PYTEST_ARGUMENT_LIST=['-q','tests/test_auth.py','tests/test_users.py','tests/test_m2_integration.py','--tb=short']` | PASS — 40 passed, 0 failed, 1 external warning |
| Guarded pytest with `PYTEST_ARGUMENT_LIST=['-q','tests/test_models.py','--tb=short']` | PASS — 26 passed, 0 failed |
| Guarded pytest with `PYTEST_ARGUMENT_LIST=['-q','--tb=short']` | PASS — 76 passed, 0 failed, 1 external warning |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run alembic heads` | PASS — `a3930ac451be` is the single head |
| Guarded Python invocation ending in `from alembic.config import main; main(argv=['check'])` against `helpdesk_m3_test` | PASS — no new upgrade operations detected |
| `git diff --check` | PASS |
| Changed-test diff scan for password, secret, token, API-key, and credential terms | PASS — only expected test names/error assertions matched; no hardcoded credential value found |

The warning in HTTP test runs is the existing external `StarletteDeprecationWarning` about its
TestClient `httpx` compatibility layer. It is not a test failure.

Two command-attempt issues were encountered and resolved without code changes:

- The first guarded database pytest attempt inside the restricted sandbox produced 15 passes and
  35 setup errors because localhost TCP access was denied with `Operation not permitted`. The same
  guarded command was rerun with approved localhost access and passed 50/50 tests. No assertion
  failed in the blocked attempt.
- The first read-only database-target diagnostic had a shell/Python quoting error. The corrected
  diagnostic reported that `TEST_DATABASE_URL` was unset in the shell; all database test commands
  therefore derived the target from application settings and explicitly forced
  `helpdesk_m3_test` before connecting.

No database was dropped, truncated, downgraded, or reset.

### Authentication and RBAC evidence

- Invalid-signature, expired, and wrong-token-type credentials return 401; refresh tokens cannot
  authorize `/auth/me`.
- `/auth/me` reloads the User from PostgreSQL. Forged JWT role/business claims do not change the
  response identity, and a deleted or nonexistent User is rejected.
- Admin user management remains constrained to the Admin's database-backed business. Agent and
  Customer list/create attempts return 403 even when token claims falsely assert Admin.
- Request payloads cannot override `business_id` or create an Admin through the managed-user
  endpoint. Password hashes remain absent from responses.
- Same-business Admin and Agent ticket access is allowed. An Agent can select only themselves as
  assignment target; Customers cannot perform staff-only assignment actions.

### Tenant and resource-isolation evidence

- Ticket lookup SQL contains `Ticket.id` and `Ticket.business_id == current_user.business_id`;
  Customer lookup additionally contains `Ticket.customer_id == current_user.id` before execution.
- Cross-business staff, same-business non-owning Customers, and nonexistent ticket IDs receive the
  same `TICKET_NOT_FOUND` 404 shape.
- Cross-business and non-Agent assignment targets receive the same generic resource-not-found
  response. Cross-tenant actors are rejected before assignment or status policy evaluation can
  disclose or operate on the ticket.
- Current `/users` queries remain scoped by the authenticated database User's business rather than
  request input or mutable JWT claims.

### Database security review

The focused 26-test model suite and the no-drift Alembic check verified the existing M1 foreign
keys, unique/check constraints, nullable assignment, enum values, relationships, and ticket
`(business_id, status)` index. The database guarantees that referenced Business, User, Ticket, and
Message rows exist.

The current schema intentionally does not encode all cross-row authorization invariants. M4 must
enforce that a ticket Customer and assigned Agent belong to the ticket business and that the
assignee has the Agent role. M5 must authorize the Message sender through the parent ticket and
authenticated context. These remain service-level requirements, not migration defects.

### Defects, fixes, and limitations

- **Critical M3 security defects:** none found.
- **Production fixes:** none required.
- **Test coverage fixes:** the two regressions listed above.
- Refresh tokens remain stateless and non-rotating, so immediate revocation is unavailable.
- Refresh-cookie behavior has automated HTTP coverage but still lacks the documented real-browser
  verification.
- Policy helpers are verified, but future endpoints remain unsafe unless M4/M5 consistently invoke
  them and apply their additional write/message invariants.

### Deferred integration tests — not passed in M3

- **DEFERRED TO M4:** Ticket CRUD endpoint isolation, assignment endpoint protection, status
  endpoint protection, Customer reopen authorization, complete transition rules, atomic initial
  message creation, and race-safe self-assignment.
- **DEFERRED TO M5:** WebSocket handshake authorization, ticket ownership checks, message-send
  authorization, Admin read-only behavior, closed-ticket message rejection, persistence before
  broadcast, revalidation, and ticket-room broadcast isolation.

These endpoints and WebSocket behaviors do not exist in M3 and are explicitly not reported as
passing. Phase 4 reviewed these boundaries without treating them as current-scope test evidence.

## 16. Phase 4 Final Security Review and Milestone Decision — 2026-10-10

### Final decision

M3 is **COMPLETE**. The final review inspected the implementation, authentication dependencies,
RBAC policies, tenant-scoped SQLAlchemy queries, M2/M3 tests, API contract, security guidance, and
Git scope. All mandatory current-scope acceptance criteria have passing evidence, and no critical
M3 security defect remains.

The Phase 4 review began from a clean worktree at commit `31f59ba`. That commit contains the Phase
3 test additions and recorded PostgreSQL results. Phase 4 did not change application source or
tests, so the Phase 3 database evidence applies to the exact reviewed implementation. The Phase 4
attempt to repeat PostgreSQL validation was recorded as `NOT RUN`, rather than PASS, because the
execution sandbox denied both localhost TCP and Unix-socket connections with `Operation not
permitted`. The sandbox was not bypassed.

### Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| Verified JWT signature, expiry, and access-token type | PASS | Code review plus Phase 4 auth tests and Phase 3 integration suite |
| Current User, role, and business resolved from backend state | PASS | `get_current_user` review; forged/deleted-user Phase 3 regressions |
| Admin, Agent, and Customer policy behavior | PASS | Phase 3 PostgreSQL authorization tests |
| M2 Admin-only own-business user management preserved | PASS | Phase 3 M2 regression suite; Phase 4 focused unit tests |
| Ticket query enforces trusted `business_id` | PASS | Resolver query review and Phase 3 policy tests |
| Customer ticket query enforces ownership | PASS | Resolver query review and Phase 3 policy tests |
| Missing, cross-tenant, and cross-customer tickets share 404 behavior | PASS | Phase 3 policy tests |
| Cross-business/non-Agent assignment targets are hidden | PASS | Assignment-policy review and Phase 3 tests |
| Passwords are hashed and hashes are omitted from responses | PASS | Source/schema review and authentication regressions |
| No committed real environment secret or token logging | PASS | Only `.env.example` is tracked; application logging/token-output review found no token logging |
| Approved API contracts remain unchanged | PASS | No M3 route/schema change; Phase 4 OpenAPI/auth suite passed |
| M4 and M5 boundaries are documented without claiming integration coverage | PASS | Sections 11, 13, 15, and this record |

### Phase 4 commands and outcomes

Commands ran from `backend/` unless noted.

| Command | Result |
|---|---|
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m compileall -q app alembic tests` | PASS |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff check app tests alembic` | PASS |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff format --check app tests alembic` | PASS — 38 files already formatted |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run mypy app tests` | PASS — no issues in 36 source files |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run pytest -q tests/test_auth.py tests/test_users.py` | PASS — 14 passed, 0 failed, 0 skipped, 1 external warning |
| `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run alembic heads` | PASS — `a3930ac451be` is the single head |
| Guarded PostgreSQL target check over localhost TCP to `helpdesk_m3_test` | NOT RUN — sandbox denied the connection before database access |
| Guarded PostgreSQL target check over `/tmp/.s.PGSQL.5432` to `helpdesk_m3_test` | NOT RUN — sandbox denied the connection before database access |
| Phase 4 M3 authorization, M2 database integration, model, full-suite, and `alembic check` reruns | NOT RUN — require the denied PostgreSQL connection |
| `git diff --check` before and after documentation edits | PASS |
| `git ls-files '*env*'` | PASS — only `.env.example` and Alembic's `env.py` are tracked |

The Phase 4 focused HTTP/unit run emitted the existing external Starlette TestClient `httpx`
deprecation warning. It caused no failure. No tests were skipped. Phase 3 remains the latest
database-backed evidence: 10 M3 authorization policy tests, 40 focused M2 regressions, 26 model
tests, and the complete 76-test backend suite all passed with zero failures against the disposable
`helpdesk_m3_test` database; `alembic check` also reported no model drift.

### Final security findings

- Authentication decisions use verified access tokens and a current database User. Mutable JWT
  role/business claims and client payload fields are not trusted as authorization context.
- Existing `/users` endpoints remain Admin-only and tenant-scoped. Public schemas do not contain a
  password hash.
- Ticket policies constrain resource lookup by tenant in SQL and add Customer ownership in the
  same query. Inaccessible and nonexistent resources use the same non-disclosing 404 response.
- Assignment target lookup constrains business and Agent role. Staff action checks first authorize
  the ticket, preventing a cross-tenant actor from probing assignment or status behavior.
- No unexpected endpoint, schema, migration, dependency, frontend, or infrastructure change was
  introduced in M3.
- No current-scope defect required a Phase 4 source fix. The two Phase 3 coverage gaps and their
  passing regressions remain documented in Section 15.

### Remaining risks and deferred integration

- **DEFERRED TO M4:** actual Ticket REST routes must call these policies for create, list, detail,
  assignment, and status operations; validate same-business Customer/Agent relationships; enforce
  the complete transition map and Customer reopen rule; atomically persist the first message; and
  test endpoint-level isolation and assignment concurrency.
- **DEFERRED TO M5:** WebSocket and message flows must validate an access token, authorize the
  parent ticket before acceptance/history/send, enforce ownership and Admin read-only behavior,
  reject closed-ticket messages, persist before broadcast, revalidate sensitive operations, and
  isolate each broadcast room.
- Refresh tokens remain stateless/non-rotating, and real-browser cookie behavior remains manually
  unverified. These are documented limitations inherited from M2, not M3 blockers.
- Policy-level tests are not evidence that future Ticket endpoints or WebSocket connections are
  secure. Their milestone-specific integration tests remain mandatory.

M3 is ready for review and subsequent M4 planning only after explicit user confirmation.
