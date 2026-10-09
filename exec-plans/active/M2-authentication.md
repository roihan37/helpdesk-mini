# M2 - JWT Authentication & User Management

## Status

Phase 2 implementation completed on 2026-10-09. **Implemented, pending Phase 3 comprehensive
verification and reviewer approval.** Preliminary static and focused tests pass. This plan remains
active; M2 is not yet complete.

## 1. Objective

Implement the smallest secure authentication and business-user-management backend that satisfies
the assessment contract:

- Public, atomic registration of one Business and its first Admin.
- Argon2 password hashing and generic credential failure handling.
- Distinct JWT access and refresh tokens with strict claim and token-type validation.
- Browser refresh through an HttpOnly cookie while still returning both tokens from login JSON.
- Authenticated current-user lookup through `GET /auth/me`.
- Admin-only, tenant-scoped user listing and creation.
- Consistent success and error envelopes, explicit OpenAPI schemas, and focused PostgreSQL tests.

M2 establishes the authentication context and the minimum role/tenant enforcement needed by its
own endpoints. M3 will audit and extend authorization across future ticket resources; it must not
be used to defer Admin authorization or tenant scoping required by M2.

## 2. Scope

In scope:

- `POST /auth/register-business`.
- `POST /auth/login`.
- `POST /auth/refresh` using the refresh cookie only.
- `GET /auth/me` using an access Bearer token.
- `GET /users`, restricted to an authenticated Admin and scoped to that Admin's `business_id`.
- `POST /users`, restricted to an authenticated Admin, inheriting that Admin's `business_id`, and
  accepting only `agent` or `customer` roles.
- Password hashing and verification, JWT creation and validation, current-user dependencies,
  Admin authorization, response/error schemas, and router wiring.
- Cookie, CORS, CSRF, environment, OpenAPI, and PostgreSQL integration tests relevant to M2.
- A small README update after implementation using only verified commands and documenting the
  stateless-refresh limitation.

## 3. Out of Scope

- Ticket APIs, ticket authorization, assignment, status transitions, and first-message creation.
- Message history and WebSocket authentication or chat.
- Frontend authentication pages, token lifecycle, or route guards.
- User update/delete, password reset/change, email verification, logout, account disablement, and
  Admin creation outside public business registration.
- Refresh-token rotation, revocation lists, sessions, Redis, rate limiting, MFA, OAuth providers,
  and other bonus features.
- Seed/demo data, Docker Compose, deployment, and M3 or later work.
- Database schema changes unless implementation reveals a documented M1 defect. None is currently
  expected, so M2 should not create an Alembic revision.

## 4. Existing Dependencies

### Verified M1 prerequisite

M1 is complete and stored at `exec-plans/completed/M1-database.md`.

- The `Business`, `User`, `Ticket`, and `Message` models import and their mappers configure.
- `users.password_hash` is required and sized for an Argon2 encoded hash.
- `businesses.slug` and `users.email` have named global unique constraints.
- Each User has a required Business relationship and a constrained role.
- Revision `a3930ac451be` is the single Alembic head and matches model metadata.
- The recorded disposable-PostgreSQL lifecycle passed upgrade, check, downgrade, re-upgrade, and
  check; the focused suite passed 26 tests with no failures or skips.
- During this planning review, compile, Ruff lint, Ruff format check, strict mypy, mapper
  configuration, model imports, and `alembic heads` were rerun and passed. The disposable
  downgrade lifecycle was not repeated because prior evidence is current and no valuable/local
  database should be destructively exercised for planning.

### Existing application foundation

- `app.core.config.Settings` already requires the PostgreSQL URL, JWT secret and expiry values,
  algorithm, and a comma-separated `CORS_ORIGINS` value parsed into `list[AnyHttpUrl]`.
- `app.db.session.get_db` provides SQLAlchemy Sessions; write services will explicitly own commit
  and rollback boundaries.
- `app.main` already enables credentialed CORS with explicit parsed origins.
- The application currently exposes only `/health`; no API router or error-handler framework
  exists yet.
- Existing production dependencies include FastAPI, SQLAlchemy, Psycopg, Pydantic Settings,
  Alembic, and Uvicorn. pytest, Ruff, and mypy are development dependencies.

### Added, justified dependencies

These dependencies were added during the approved Phase 2 implementation:

- `argon2-cffi`: maintained Argon2 hashing and verification implementation.
- `PyJWT`: HS256 JWT encode/decode with explicit algorithm and required-claim validation.
- `email-validator`: required by Pydantic `EmailStr` for contract-level email validation.
- `httpx` as a development dependency: required by FastAPI/Starlette `TestClient`.

No form parser is needed because login uses the documented JSON request, not OAuth form data.

### Implementation files

Create:

- `backend/app/api/__init__.py`
- `backend/app/api/dependencies.py`
- `backend/app/api/router.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/users.py`
- `backend/app/core/errors.py`
- `backend/app/core/security.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/common.py`
- `backend/app/schemas/user.py`
- `backend/app/services/__init__.py`
- `backend/app/services/auth.py`
- `backend/app/services/users.py`
- `backend/tests/conftest.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_users.py`

Modify:

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/tests/test_models.py` only as needed to share safe, milestone-neutral DB fixtures.
- `.env.example`
- `README.md` only after commands have actually been verified.

No M1 model or migration change is planned.

## 5. Architecture Decisions

### Layer boundaries

- Routers parse HTTP input, set status/cookies, and return documented schemas.
- Services own authentication workflows, SQLAlchemy queries, transaction boundaries, and conflict
  translation.
- Dependencies decode authentication, resolve the current User from PostgreSQL, and enforce the
  Admin role.
- Schemas are separate from ORM models and explicitly omit `password_hash`.
- Security helpers perform password and JWT primitives without owning HTTP or database behavior.

### Input and identity normalization

- Use strict Pydantic write schemas (`extra="forbid"`).
- Trim names and reject empty values; constrain them to the model's 255-character capacity.
- Require lowercase URL-safe slugs with `^[a-z0-9]+(?:-[a-z0-9]+)*$` and the model's
  255-character limit.
- Validate email with `EmailStr`, then trim and lowercase it before every lookup or write. This
  makes the existing globally unique database constraint deterministic for application-created
  accounts. Existing mixed-case legacy rows are not expected at M2.
- Require passwords of 8-128 characters. The documented minimum is preserved and the explicit
  upper bound limits attacker-controlled hashing work.
- Do not accept `business_id`, Admin role, IDs, timestamps, or other trusted fields from user
  creation requests.

### Password handling

- Hash new passwords with Argon2 through `argon2-cffi`; store only the encoded hash.
- Verify with the library function and support a future `check_needs_rehash` path without changing
  the API contract.
- Run one dummy-hash verification when a login email is unknown so unknown-user and bad-password
  paths are less distinguishable.
- Never put request models, passwords, hashes, or tokens in logs or error details.

### JWT contract

- Restrict configuration and decoder allowlisting to `HS256`.
- Access lifetime is configured as 15 minutes; refresh lifetime is 7 days.
- Both token types contain `sub`, `type`, `iat`, and `exp`. They may also carry `business_id` and
  `role` for client context, but authorization always uses the current database User.
- Require and validate all security-relevant claims, parse `sub` as a UUID, reject malformed,
  expired, incorrectly signed, or wrong-type tokens, and resolve an existing current User.
- Access dependencies accept only `type=access`; refresh accepts only `type=refresh`.
- Return `WWW-Authenticate: Bearer` on access-token 401 responses.
- No refresh rotation, `jti`, revocation store, or immediate logout invalidation is introduced in
  this milestone; this is an explicit MVP limitation.

### Refresh cookie, CORS, and CSRF

- Login returns access and refresh tokens in JSON exactly as required and also sets a cookie named
  `refresh_token`.
- Cookie attributes: `HttpOnly=true`, `SameSite=Lax`, `Path=/auth/refresh`, and a required
  environment-controlled `Secure` flag (`false` only for local HTTP, `true` under HTTPS). Set
  `Max-Age` to the configured refresh lifetime and omit `Domain` so the cookie remains host-only.
- `/auth/refresh` reads only that cookie. A JSON-body refresh token is rejected/not modeled.
- Postman testing relies on retaining the login cookie in its cookie jar.
- Continue parsing `CORS_ORIGINS` as the existing comma-separated explicit allowlist; never use a
  wildcard origin with credentials.
- Narrow credentialed CORS to `GET` and `POST` with `Authorization` and `Content-Type` request
  headers instead of the foundation's temporary wildcard method/header configuration.
- For browser refresh requests, combine `SameSite=Lax` with explicit `Origin` validation against
  the normalized configured allowlist. Reject a present disallowed origin. Originless clients are
  allowed so non-browser clients such as Postman can use the cookie jar; browsers provide the
  relevant cross-origin signal. A future truly cross-site `SameSite=None` deployment requires a
  stronger CSRF mechanism and is outside this milestone.

### Database and transaction behavior

- Registration creates Business and Admin in one transaction and performs one commit only after
  both rows are valid; any failure rolls back both.
- Admin user creation derives `business_id` exclusively from the database-resolved current Admin.
- User listing always includes `User.business_id == current_user.business_id` in the query.
- Friendly duplicate checks may be used, but named database uniqueness remains authoritative.
  Catch `IntegrityError`, roll back, and translate expected unique conflicts to a generic 409
  without returning SQL or disclosing another tenant's account details.
- Read queries do not commit. Write services explicitly roll back after failures.

### API envelopes and OpenAPI

- Successful payloads use `{"data": ...}`; collections use a data list without pagination.
- All planned errors use `{"error":{"code","message","details"}}`, including FastAPI request
  validation errors.
- A small application error type plus handlers will centralize safe 401/403/409/422 responses.
- Request/response models and Bearer security must appear accurately in `/docs` and OpenAPI.
- SQLAlchemy models are never returned directly as the public contract without response schemas.

## 6. Ordered Implementation Tasks

### M2-01 - Add authentication dependencies and configuration

**Objective:** Add only the libraries and settings required for M2 security, tests, and cookie
behavior.

**Files:** `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/core/config.py`, `.env.example`.

**Dependencies:** Completed M1 and existing typed settings.

**Approach:**

- Add `argon2-cffi`, `PyJWT`, and `email-validator`; add `httpx` to the dev group.
- Validate `JWT_ALGORITHM` as exactly `HS256` and retain the existing minimum-length JWT secret.
- Add a required `REFRESH_COOKIE_SECURE` boolean and local placeholder value.
- Keep the existing comma-separated `CORS_ORIGINS` parser unchanged and test multiple origins.

**Acceptance criteria:** Settings fail closed for missing/invalid secrets or algorithm; comma-
separated origins still parse; local cookie security is explicit; imports resolve from the lockfile.

**Verification:**

```bash
cd backend
uv sync --all-groups
uv run python -c "from app.core.config import get_settings; print(get_settings().jwt_algorithm)"
uv run pytest -q tests/test_auth.py -k "settings or cors or cookie"
```

### M2-02 - Define public schemas and standard error handling

**Objective:** Encode the documented API contract without exposing ORM-only fields.

**Files:** `backend/app/schemas/common.py`, `backend/app/schemas/auth.py`,
`backend/app/schemas/user.py`, `backend/app/schemas/__init__.py`,
`backend/app/core/errors.py`, `backend/app/main.py`.

**Dependencies:** M2-01.

**Approach:**

- Create strict register, login, and user-create request schemas.
- Create Business/User/current-user/token response schemas and generic data envelopes.
- Represent user creation roles so only `agent` and `customer` validate.
- Add handlers for application errors and `RequestValidationError`; sanitize details and preserve
  the documented codes/statuses.

**Acceptance criteria:** Unknown fields and unsupported roles return the standard 422 envelope;
responses never contain passwords or hashes; OpenAPI contains explicit schemas.

**Verification:**

```bash
cd backend
uv run pytest -q tests/test_auth.py tests/test_users.py -k "validation or schema or password_hash"
uv run python -c "from app.main import app; assert app.openapi()['paths'] is not None"
```

### M2-03 - Implement password and JWT primitives

**Objective:** Provide narrowly scoped, testable Argon2 and JWT helpers.

**Files:** `backend/app/core/security.py`, `backend/tests/test_auth.py`.

**Dependencies:** M2-01 and M2-02.

**Approach:**

- Implement hash/verify helpers with safe handling of invalid stored hashes.
- Implement access/refresh creation using timezone-aware UTC timestamps and configured lifetimes.
- Decode with `algorithms=["HS256"]`, required claims, UUID subject parsing, expiry validation,
  and expected-token-type enforcement.
- Map JWT failures to safe, differentiated contract codes where possible without leaking details.

**Acceptance criteria:** Stored values are Argon2 hashes; valid tokens decode; expired, tampered,
missing-claim, unexpected-algorithm, and wrong-type tokens are rejected; configured expiry values
are honored.

**Verification:**

```bash
cd backend
uv run pytest -q tests/test_auth.py -k "password or token or expired or signature or type"
```

### M2-04 - Implement authentication and Admin dependencies

**Objective:** Resolve every protected request to a current database User and apply role checks.

**Files:** `backend/app/api/dependencies.py`, `backend/tests/test_auth.py`,
`backend/tests/test_users.py`.

**Dependencies:** M2-03 and `app.db.session.get_db`.

**Approach:**

- Use FastAPI Bearer extraction for protected REST operations.
- Validate only access tokens, load the User and Business from PostgreSQL, and use their current
  role/business rather than trusting authorization claims.
- Add a reusable Admin dependency returning 403 for authenticated non-Admins.
- Return 401 for missing, invalid, expired, wrong-type, or deleted-user identities.

**Acceptance criteria:** Protected routes have one canonical authentication path; refresh tokens
cannot act as access tokens; role denial is 403; current tenant context comes from the database.

**Verification:**

```bash
cd backend
uv run pytest -q tests/test_auth.py tests/test_users.py -k "unauthenticated or bearer or wrong_type or forbidden"
```

### M2-05 - Implement atomic business registration

**Objective:** Create a Business and its Admin safely in one transaction.

**Files:** `backend/app/services/auth.py`, `backend/app/api/routes/auth.py`,
`backend/tests/test_auth.py`.

**Dependencies:** M2-02 through M2-04 and M1 models.

**Approach:**

- Validate and normalize input, hash the password, create both ORM records, flush, and commit once.
- Force role `admin`; never accept role or business identity from the client.
- Catch expected email/slug uniqueness races, roll back, and return a safe 409.
- Prove rollback by causing the second insert to fail and checking that no orphan Business remains.

**Acceptance criteria:** Success returns 201 and documented nested data; both rows share the same
business; password is hashed; duplicate email/slug returns 409; failure is atomic.

**Verification:**

```bash
cd backend
uv run pytest -q tests/test_auth.py -k "register"
```

### M2-06 - Implement login and refresh-cookie issuance

**Objective:** Authenticate JSON credentials and issue both token types using the documented
browser cookie strategy.

**Files:** `backend/app/services/auth.py`, `backend/app/api/routes/auth.py`,
`backend/tests/test_auth.py`.

**Dependencies:** M2-03 and M2-05.

**Approach:**

- Look up canonical email, verify Argon2, and use the same generic 401 for unknown email or wrong
  password, including dummy verification for the unknown-user path.
- Return access token, refresh token, `bearer`, and `expires_in=900` in the data envelope.
- Set the refresh cookie with the exact planned attributes and without logging token values.

**Acceptance criteria:** Valid login succeeds; both credential failures are indistinguishable;
both JSON tokens have correct types; cookie flags/path are correct; no sensitive data is returned.

**Verification:**

```bash
cd backend
uv run pytest -q tests/test_auth.py -k "login or cookie or credentials"
```

### M2-07 - Implement refresh and current-user endpoints

**Objective:** Restore access from a valid cookie and return the authenticated identity safely.

**Files:** `backend/app/services/auth.py`, `backend/app/api/routes/auth.py`,
`backend/tests/test_auth.py`.

**Dependencies:** M2-04 and M2-06.

**Approach:**

- Read refresh only from the `refresh_token` cookie, validate origin policy, signature, expiry,
  required claims, type, and current User existence, then return a new access token only.
- Implement `/auth/me` from the access dependency and serialize only that User and Business.
- Ensure an access token in the refresh cookie and a refresh token in Bearer auth are rejected.

**Acceptance criteria:** Refresh succeeds via cookie jar with no body; absent/invalid/expired/wrong-
type cookies return 401; disallowed browser origins are rejected; `/auth/me` returns current DB
identity and never hash data.

**Verification:**

```bash
cd backend
uv run pytest -q tests/test_auth.py -k "refresh or me or origin"
```

### M2-08 - Implement tenant-scoped Admin user management

**Objective:** Let only Admins list and create users inside their own business.

**Files:** `backend/app/services/users.py`, `backend/app/api/routes/users.py`,
`backend/tests/test_users.py`.

**Dependencies:** M2-04 and shared schemas/security helpers.

**Approach:**

- Query users with an explicit current-Admin `business_id` predicate and deterministic ordering.
- Create only `agent` or `customer`, derive tenant from the Admin, hash the password, commit, and
  translate global-email conflicts safely.
- Reject supplied trusted fields through strict schemas; never provide an Admin creation path.

**Acceptance criteria:** Admin sees only same-business users; Admin can create Agent/Customer in
their own business; Agent/Customer receive 403; `admin` or extra `business_id` receives 422;
duplicate email receives 409; password/hash never appears.

**Verification:**

```bash
cd backend
uv run pytest -q tests/test_users.py
```

### M2-09 - Wire routers, OpenAPI security, CORS, and test infrastructure

**Objective:** Integrate M2 endpoints into the application and make tests safe and repeatable.

**Files:** `backend/app/api/router.py`, `backend/app/api/routes/__init__.py`,
`backend/app/api/__init__.py`, `backend/app/main.py`, `backend/tests/conftest.py`,
`backend/tests/test_models.py` if fixture sharing is needed.

**Dependencies:** M2-02 through M2-08.

**Approach:**

- Include `/auth` and `/users` routers without introducing an undocumented `/api` prefix.
- Narrow CORS methods/headers to the M2 requirements while preserving the explicit comma-separated
  origin parser and credential support.
- Keep `/health` public and verify generated OpenAPI documents response models and Bearer auth.
- Use a guarded `TEST_DATABASE_URL` ending in `_test`, migrate it to head, override `get_db`, and
  isolate tests with an outer transaction/savepoint arrangement compatible with service commits.
- Preserve or migrate the M1 fixture safely; never point tests at a non-test database.
- Test CORS with explicit allowed/disallowed origins and credentials.

**Acceptance criteria:** All routes are reachable and accurately documented; tests cannot run on a
database whose name does not end in `_test`; committed service transactions remain isolated;
existing M1 tests continue to pass.

**Verification:**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test \
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test \
uv run pytest -q
```

### M2-10 - Full verification and documentation handoff

**Objective:** Produce reproducible evidence, document only verified behavior, and stop before M3.

**Files:** `README.md`, `exec-plans/active/M2-authentication.md`.

**Dependencies:** M2-01 through M2-09.

**Approach:**

- Run the complete static, unit/integration, migration-consistency, OpenAPI, and secret-diff checks.
- Update README with commands actually executed, cookie/Postman behavior, environment values, and
  the stateless refresh-token limitation.
- Record exact PASS/FAIL/NOT RUN results and unresolved risks in this plan.
- Keep this plan active until review; do not begin M3, commit, or push.

**Acceptance criteria:** Relevant checks have recorded evidence; no critical M2 security issue is
known; documentation matches implementation; failures are reported without being hidden.

**Verification:** Use the complete command set in section 11.

## 7. Security Requirements

- Store only Argon2 hashes; never log, return, or compare plaintext passwords directly.
- Use a strong environment-provided JWT secret and fail startup when required configuration is
  absent or invalid.
- Explicitly allow only HS256 during JWT verification and require signature, expiry, type, issued-
  at, and UUID subject claims.
- Resolve a current User from PostgreSQL after token validation; do not authorize from stale role
  or tenant claims.
- Enforce access/refresh token separation on every path.
- Use generic login errors and dummy verification to reduce email enumeration signals.
- Keep refresh in an HttpOnly, SameSite Lax, refresh-path-only cookie; require Secure under HTTPS.
- Apply explicit browser-origin checks to cookie-authenticated refresh requests and explicit
  credentialed CORS origins. Never configure wildcard credentialed CORS.
- Derive all trusted tenant IDs from the authenticated database User.
- Enforce Admin authorization for both user endpoints; return 403 to authenticated non-Admins.
- Filter lists by tenant in SQL, not after retrieval.
- Prevent mass assignment through strict, explicit schemas.
- Treat database uniqueness constraints as final authority, roll back on integrity errors, and do
  not expose database messages or cross-tenant account details.
- Preserve transaction atomicity for registration and user creation.
- Return no password, `password_hash`, JWT secret, raw exception, database URL, or stack trace in
  an API response.
- Keep real `.env` files and credentials untracked.

## 8. API Contracts

### `POST /auth/register-business` - public, 201

Request contains nested `business{name,slug}` and `admin{name,email,password}`. It returns the
documented nested Business/Admin data envelope. Public registration always creates exactly one
Admin. Duplicate canonical email or slug is 409; invalid input is 422.

### `POST /auth/login` - public, 200

Request is JSON `email` and `password`. Success returns `access_token`, `refresh_token`,
`token_type="bearer"`, and `expires_in=900`, and sets the refresh cookie. Invalid email and invalid
password both return `AUTH_INVALID_CREDENTIALS` with 401.

### `POST /auth/refresh` - valid refresh cookie, 200

No body is defined. The endpoint reads the refresh cookie only and returns a new access token,
`bearer`, and `expires_in=900`. Missing/invalid/expired/wrong-type token or missing User is 401.
Postman must retain the login cookie in its cookie jar.

### `GET /auth/me` - access Bearer token, 200

Returns the current User's `id`, `name`, `email`, and `role` plus their Business `id`, `name`, and
`slug`. Missing/invalid/refresh Bearer tokens are 401.

### `GET /users` - Admin access Bearer token, 200

Returns only users whose `business_id` equals the current database Admin's business. It never
returns hashes. Non-Admin is 403 and unauthenticated is 401.

### `POST /users` - Admin access Bearer token, 201

Request contains `name`, `email`, `password`, and role `agent` or `customer`. The server derives
`business_id`; `admin` and client-supplied tenant identity are invalid. Global duplicate email is
409, non-Admin is 403, unauthenticated is 401, and invalid input is 422.

All success and error bodies follow `docs/API_CONTRACT.md`; no contract change is planned.

## 9. Testing Strategy

Tests use pytest, FastAPI `TestClient`, and a disposable PostgreSQL database protected by a
database-name `_test` guard. Database-dependent tests use dependency overrides and rollback-safe
fixtures that tolerate service-level commits. No SQLite substitute is permitted.

Authentication coverage:

- Registration success, forced Admin role, shared business relationship, Argon2 storage, no
  plaintext/hash response, duplicate slug/email, and atomic rollback.
- Login success, canonical email behavior, incorrect password, unknown email with identical public
  error, and cookie/token response attributes.
- Access and refresh expiry; invalid signature; unexpected algorithm; malformed/missing claims;
  invalid UUID subject; wrong token type; nonexistent user.
- Refresh from cookie with no body, missing cookie, access token in cookie, allowed/disallowed
  Origin, and Postman-style originless request.
- `/auth/me` success, missing auth, wrong token type, and current database role/business behavior.

User-management coverage:

- Admin lists only users in their own business, including a fixture proving another business is
  excluded.
- Admin creates Agent and Customer in the Admin's business with Argon2 hashes.
- Admin role, `business_id`, IDs, timestamps, and unknown fields cannot be injected.
- Agent and Customer cannot list or create users.
- Duplicate canonical email is rejected globally with a safe 409.
- All responses exclude password fields and hashes.

Infrastructure/contract coverage:

- Standard 401/403/409/422 envelope and sanitized details.
- Explicit allowed CORS origin succeeds; disallowed origin receives no credentialed allowance.
- OpenAPI exposes all six endpoints, schemas, statuses, and Bearer security accurately.
- Existing 26 M1 model tests remain green.
- Alembic reports one head and no model/schema drift; no M2 revision is expected.

## 10. Acceptance Criteria

- [ ] Public registration persists Business and Admin atomically and returns 201.
- [ ] Duplicate slug or globally duplicate canonical email returns a safe 409.
- [ ] Every stored password created through M2 is an Argon2 hash; plaintext and hashes never appear
  in responses or logs.
- [ ] Login returns distinct 15-minute access and 7-day refresh JWTs in JSON.
- [ ] Login also sets the documented HttpOnly refresh cookie attributes.
- [ ] Incorrect password and unknown email share the same generic 401 response.
- [ ] Refresh reads only the cookie, validates origin/signature/expiry/type/current User, and returns
  a new access token.
- [ ] Access tokens cannot refresh; refresh tokens cannot access `/auth/me` or `/users`.
- [ ] `/auth/me` returns the current User and only their Business without sensitive fields.
- [ ] Only Admin can list/create users; Agent and Customer receive 403.
- [ ] `GET /users` is filtered in SQL by the current Admin's business.
- [ ] `POST /users` derives the Admin's business and accepts only Agent/Customer roles.
- [ ] Credentialed CORS uses the parsed explicit origin list; wildcard origin is absent.
- [ ] REST errors conform to the documented envelope and expose no internals.
- [ ] OpenAPI accurately documents M2 schemas and Bearer requirements.
- [ ] Static checks, focused tests, full tests, Alembic consistency, and secret/diff checks have
  actual recorded results.
- [ ] README and this execution plan contain only commands/results actually verified.
- [ ] No ticket, WebSocket, frontend, Redis, bonus, or M3 feature is implemented.

## 11. Verification Commands

Run from `backend/` unless stated otherwise. Substitute only a disposable PostgreSQL database whose
name ends with `_test`; never run downgrade verification on valuable data.

```bash
uv sync --all-groups
uv run python -m compileall -q app alembic tests
uv run ruff check app alembic tests
uv run ruff format --check app alembic tests
uv run mypy app tests
uv run python -c "from app.main import app; schema = app.openapi(); assert '/auth/login' in schema['paths']; print('OpenAPI OK')"
uv run alembic heads
```

With both URLs pointing to the same disposable test database:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test uv run alembic current
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test uv run alembic check
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test uv run pytest -q
```

Optional migration reversibility recheck only on a newly created disposable database:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test uv run alembic downgrade base
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_m2_test uv run alembic check
```

Repository checks from the repository root:

```bash
git diff --check
git status --short
git diff -- .env.example README.md backend exec-plans/active/M2-authentication.md
```

Manual review must also confirm that `.env` remains ignored, no real secret/token/password was
added, no response schema contains `password_hash`, and no endpoint outside M2 appeared.

## 12. Risks and Trade-offs

- Login must return the refresh token in JSON to satisfy the assessment even though browser code
  should use only the HttpOnly cookie. The frontend must not persist the response-body token.
- Stateless refresh tokens cannot be revoked immediately and are not rotated. Expiration limits
  exposure; session storage/revocation is deliberately deferred and must be documented.
- SameSite Lax plus Origin validation is selected for the documented same-site deployment. A truly
  cross-site frontend would need `SameSite=None`, HTTPS, Secure cookies, and a stronger CSRF design.
- Originless refresh is allowed for Postman/non-browser clients. Security relies on browsers'
  Origin/SameSite behavior for CSRF defense; this assumption must be reevaluated if deployment
  topology changes.
- Global email lowercasing is simple and predictable but treats theoretically case-sensitive local
  parts as case-insensitive. This is intentional for login identity consistency.
- Application duplicate prechecks cannot prevent races. Database constraints and `IntegrityError`
  handling remain required.
- JWT role/business claims can become stale, so each protected request incurs a database lookup.
  Correct current authorization is preferred over claim-only performance.
- Argon2 is intentionally CPU/memory intensive. Login rate limiting is a P2 bonus and remains out
  of scope; bounded password input and dummy verification reduce abuse/enumeration concerns but do
  not replace rate limiting.
- M1 foreign keys do not encode cross-business semantics. M2 user creation explicitly derives the
  tenant; M3 must audit tenant authorization for ticket-related resources.
- Test transactions must accommodate service commits correctly. An incorrect fixture could leak
  rows between tests, so the savepoint/outer-rollback behavior requires an explicit regression
  test and a guarded disposable database.

## 13. Definition of Done

M2 is done only when every in-scope endpoint and security behavior is implemented, all acceptance
criteria above have executable evidence, the full backend suite passes against disposable
PostgreSQL, Alembic reports no drift, OpenAPI matches the contract, and documentation records the
verified setup and known stateless-token limitation.

Any failing security-critical check, tenant leak, plaintext/hash exposure, token-type confusion,
non-atomic registration, unsafe test database configuration, or unresolved contract conflict keeps
M2 incomplete. The execution plan remains in `active/` until reviewer approval. Do not commit,
push, move to M3, or implement later-milestone functionality automatically.

## 14. Phase 2 Implementation Record

Recorded on 2026-10-09.

### Implemented tasks

- M2-01 through M2-09 are implemented. M2-10 is partially complete: preliminary checks and the
  README handoff are recorded, while comprehensive disposable-PostgreSQL verification remains for
  Phase 3.
- Added Argon2 password hashing, HS256 access/refresh JWT creation and strict token-type decoding,
  database-backed current-user resolution, and reusable Admin authorization.
- Added all six planned endpoints: `POST /auth/register-business`, `POST /auth/login`,
  `POST /auth/refresh`, `GET /auth/me`, `GET /users`, and `POST /users`.
- Registration performs one commit for the Business and forced-Admin records and rolls back on any
  commit failure. Admin user creation also rolls back on any commit failure.
- User listing applies an explicit `business_id` SQL predicate. User creation derives the tenant
  from the authenticated database Admin and accepts only Agent or Customer roles.
- Added strict request/response schemas, safe application/validation/unexpected-error envelopes,
  explicit credentialed CORS, refresh-cookie configuration, and refresh Origin validation.
- No model or Alembic revision was changed; no M3, ticket, messaging, WebSocket, or frontend feature
  was introduced.

### Files created

- `backend/app/api/__init__.py`
- `backend/app/api/dependencies.py`
- `backend/app/api/router.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/users.py`
- `backend/app/core/errors.py`
- `backend/app/core/security.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/common.py`
- `backend/app/schemas/user.py`
- `backend/app/services/__init__.py`
- `backend/app/services/auth.py`
- `backend/app/services/users.py`
- `backend/tests/conftest.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_users.py`

### Files modified

- `.env.example`
- `README.md`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/pyproject.toml`
- `backend/uv.lock`
- `exec-plans/active/M2-authentication.md`

The pre-existing M0/M1 execution-plan moves were not modified as part of M2.

### Preliminary validation results

- PASS — `UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv sync --all-groups`: 45 packages resolved and
  42 packages audited.
- PASS — `uv run ruff check app alembic tests`.
- PASS — `uv run ruff format --check app alembic tests`: 35 files already formatted.
- PASS — `uv run mypy app tests`: 33 source files, no issues.
- PASS — `uv run pytest -q tests/test_auth.py tests/test_users.py`: 14 passed. One external
  `StarletteDeprecationWarning` reports that FastAPI's current `TestClient` import uses deprecated
  httpx integration.
- PASS — `uv run python -m compileall -q app alembic tests`.
- PASS — OpenAPI assertion for all M2 routes and Bearer security, with
  `REFRESH_COOKIE_SECURE=false` supplied because the existing ignored local `.env` predates M2.
- PASS — `uv run python -m app.db.check` against the configured local PostgreSQL database when run
  outside the filesystem/network sandbox.
- PASS — `uv run alembic heads`: `a3930ac451be (head)`.
- PASS — `git diff --check`.
- PASS — focused scan of `backend/app` and `backend/tests` found no embedded JWT secret, PostgreSQL
  credential URL, or private-key marker.
- FAIL (environment state, not code drift) — `uv run alembic check` connected to the configured
  local development database but reported `Target database is not up to date`; `alembic current`
  showed no applied revision. The database was intentionally not upgraded because it was not
  established as disposable.
- The first standalone OpenAPI command failed because the existing ignored local `.env` lacked the
  new required `REFRESH_COOKIE_SECURE` value. It passed after supplying that documented setting;
  `.env.example` and README now document it.

### Remaining Phase 3 verification

- NOT RUN — full `pytest -q`, including the existing 26 M1 database tests, because no guarded
  disposable PostgreSQL URL ending in `_test` was available during Phase 2.
- NOT RUN — endpoint-level PostgreSQL integration for atomic registration, uniqueness races,
  login/current-user lookup, refresh user resolution, cross-business listing exclusion, and
  tenant-derived user creation.
- NOT RUN — migration upgrade/check/downgrade/re-upgrade lifecycle against a fresh disposable test
  database. No destructive migration command was run against the local development database.
- Phase 3 must provision or receive an explicit disposable `_test` database, migrate it to head,
  run the complete suite, and resolve any failures before M2 can be marked complete.

### Known limitations and security notes

- Refresh tokens remain stateless, non-rotating, and not immediately revocable, as approved for
  M2. Login rate limiting also remains out of scope.
- JWT role and business claims are informational; protected authorization loads the current User,
  role, and business relationship from PostgreSQL.
- The refresh cookie is HttpOnly, SameSite Lax, scoped to `/auth/refresh`, and controlled by the
  required `REFRESH_COOKIE_SECURE` environment value. HTTPS deployments must set it to `true`.
- Originless refresh remains supported for non-browser clients such as Postman; browser requests
  that provide `Origin` are checked against the configured explicit allowlist.
- The focused tests establish preliminary behavior but do not replace the Phase 3 PostgreSQL and
  tenant-isolation integration suite.
