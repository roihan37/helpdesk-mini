# M5 — WebSocket Real-Time Chat

## Status

COMPLETE — PHASE 4 REVIEW PASSED

Planning date: 2026-10-10

## 1. Objective

Add secure, persistent, real-time Ticket chat to the existing FastAPI modular monolith. M5 will
provide authorized chronological message history, authenticated ticket-scoped WebSocket rooms,
post-commit `message.created` delivery, and post-commit `ticket.status_changed` delivery while
preserving the M2 authentication, M3 authorization, and M4 Ticket lifecycle rules.

M4 prerequisite review: **COMPLETE**. `exec-plans/completed/M4-ticket-management.md` exists and its
Phase 4 record reports 36 focused M4 tests, 76 M1-M3 regression tests, and all 112 backend tests
passing, plus compile, Ruff, mypy, Alembic-head/check, and diff checks passing. Source inspection
confirms the four Ticket REST operations, centralized tenant/owner resolver, row-locked updates,
atomic Ticket/first-Message creation, and no recorded critical M4 defect. The worktree was clean at
the start of this planning phase.

## 2. Mandatory Scope

- Add `GET /tickets/{id}/messages` with the documented `{ "data": [...] }` envelope, trusted
  sender metadata, and deterministic `created_at ASC, id ASC` ordering.
- Add `WS /ws/tickets/{id}?token=<access_token>` with authentication, current database-backed user
  resolution, tenant and Customer-owner authorization before acceptance, and origin validation.
- Support exactly the documented client event `message.send` and server events
  `message.created`, `ticket.status_changed`, and the already documented `error` event.
- Allow Agent and owning Customer writes; keep Admin connections read-only.
- Persist every accepted Message and update `tickets.updated_at` in the same transaction before
  broadcasting.
- Reject writes to a currently closed Ticket, including from connections opened before closure.
- Broadcast meaningful committed M4 status changes to the matching Ticket room only.
- Use a minimal in-memory Connection Manager and a single backend process.
- Add PostgreSQL-backed HTTP, WebSocket, security, transaction, lifecycle, and regression tests.

## 3. Out of Scope

- M6 React/Next.js pages, browser chat components, and frontend dependencies.
- A REST message-creation endpoint, message editing/deletion, pagination, search, attachments,
  typing indicators, read receipts, unread counts, or presence.
- Redis, Kafka, Socket.IO, a broker, distributed locks, an outbox, replay queues, or multi-process
  synchronization.
- Changes to the approved JWT cookie strategy or refresh flow.
- A new Ticket status endpoint or changes to the M4 transition/assignment policy.
- Authentication tokens in WebSocket messages, client-controlled identity fields, or HTML
  rendering behavior.
- M6 UI concerns are limited to documenting the existing interface: fetch history first, connect
  using the access token, consume documented events, reconcile the sender's `message.created`
  event without duplication, show disconnect/error state, update visible status, and disable input
  for Admin or closed Tickets.

## 4. Existing Implementation Inventory

| Requirement/component | Classification | Evidence and M5 use |
|---|---|---|
| `Business`, `User`, `Ticket`, `Message` models and relationships | IMPLEMENTED AND VERIFIED | M1/M4 tests; reuse without a migration |
| Message `(ticket_id, created_at, id)` index | IMPLEMENTED AND VERIFIED | Supports deterministic history query |
| JWT creation/decoding and access-vs-refresh validation | IMPLEMENTED AND VERIFIED | Reuse `decode_token(..., expected_type="access")` |
| Database-backed trusted current User resolution | IMPLEMENTED AND VERIFIED | Extract token-based resolver from the HTTP-only bearer dependency for shared use |
| Tenant/owner Ticket authorization | IMPLEMENTED AND VERIFIED | Reuse `get_authorized_ticket`, including `for_update=True` for writes |
| M4 status transitions and Ticket row locking | IMPLEMENTED AND VERIFIED | Preserve; expose only minimal change metadata for post-commit broadcast |
| Atomic Ticket plus first Message creation | IMPLEMENTED AND VERIFIED | Reuse transaction/rollback conventions |
| `MessageBody` validation (trimmed, 1–5,000 characters) | IMPLEMENTED AND VERIFIED for Ticket creation | Reuse in strict WebSocket event schema |
| Message response/event schemas | MISSING | Add explicit Pydantic contracts; never expose ORM objects directly |
| Message history service and endpoint | MISSING | Add tenant-authorized query and route |
| WebSocket auth adapter and route | MISSING | Add without applying `HTTPBearer` directly to WebSocket |
| In-memory Connection Manager | MISSING | Add a small Ticket-room manager |
| Message persistence service | MISSING | Add short-session, row-locked transaction |
| Status broadcast integration | MISSING | Add post-commit M4 route integration without duplicating transition rules |
| WebSocket and message-history tests | MISSING | Add real TestClient WebSocket plus PostgreSQL integration coverage |
| Chat UI | DEFERRED TO M6 | M5 exposes only the documented backend contract |
| Distributed broadcasting and optional chat features | OUT OF SCOPE | Not required for the assessment |

Relevant existing files are `app/core/security.py`, `app/api/dependencies.py`,
`app/services/authorization.py`, `app/services/tickets.py`, `app/api/routes/tickets.py`,
`app/db/session.py`, `app/models/message.py`, `app/models/ticket.py`, and
`app/schemas/ticket.py`. Existing pytest helpers and M2-M4 factories will be reused where their
transaction visibility is compatible; WebSocket tests need sessions visible across connections.

## 5. Architecture Decisions

- Keep the modular-monolith split: route handles protocol lifecycle, schemas validate input/output,
  service owns database rules, authorization helper owns tenant/owner policy, and manager owns only
  active connections and delivery.
- Extract a token-string current-user resolver that accepts a `Session`; keep `get_current_user` as
  the HTTPBearer adapter. WebSocket code calls the shared resolver rather than pretending an HTTP
  dependency works for WebSocket requests.
- Open and close a database Session for handshake authorization and for each sensitive incoming
  event. Never retain a Session or transaction while waiting for frames.
- Run synchronous SQLAlchemy work outside the async socket loop and let the database service own
  its Session in that worker invocation; do not move one Session concurrently across threads.
- Revalidate the original access token, current User, current role/business, Ticket access, and
  current Ticket status on every `message.send`.
- Use a Ticket row lock for message writes. This shares the M4 lock discipline and serializes a
  send against status closure so a message cannot pass a stale pre-close check.
- Reuse the configured `CORS_ORIGINS` allowlist for exact WebSocket `Origin` checks. Proposed
  review decision: require a present, allowed browser Origin; this is stricter than the docs'
  recommendation and avoids cross-site WebSocket use. Tests will send an allowed Origin.
- Keep Admin chat read-only, as already selected consistently in `ARCHITECTURE.md`,
  `docs/SECURITY.md`, and `docs/API_CONTRACT.md`.
- No schema migration or new dependency is expected. FastAPI/Starlette TestClient and the existing
  SQLAlchemy/PostgreSQL stack are sufficient.

Two documented ambiguities remain explicit for Phase 2 review:

1. ASGI servers may expose different HTTP responses for a pre-accept rejection. Tests should
   require rejection/no room membership/no protected payload and policy code `1008` where the
   TestClient exposes it, not a particular HTTP status.
2. The contract defines post-accept error payloads but not connection continuation. Proposed
   smallest behavior: send a sanitized `error` and continue for recoverable malformed,
   unsupported, Admin-send, and closed-Ticket events; close with `1008` when authentication has
   expired or current authorization is lost; close with `1011` after a sanitized internal failure
   when safe continuation is uncertain.

## 6. WebSocket Connection Lifecycle

1. Receive the Ticket UUID, token query parameter, and `Origin` without accepting.
2. Reject missing/disallowed Origin or missing token without adding the connection to a room.
3. In a short Session, validate JWT signature, expiration, and `access` type; resolve the current
   User from the database; resolve the Ticket with `get_authorized_ticket` so tenant and Customer
   ownership predicates are enforced.
4. Close the Session, accept the connection, then register it in the Ticket room. Protected data
   is not sent before these checks complete.
5. Receive JSON events in a loop. Validate each event; for every write, repeat access-token and
   database-backed user/Ticket authorization in a fresh short transaction.
6. Persist and commit an authorized Message, then broadcast its authoritative event to a snapshot
   of that Ticket room.
7. On normal or exceptional disconnect, remove the connection in `finally`; remove failed peers
   encountered during broadcast as well. Empty rooms and their locks are discarded.

Opening a closed Ticket room remains allowed for authorized read-only observation/history, but
every attempted write reads and locks current database state and returns `TICKET_CLOSED`.

## 7. Authentication and Authorization

| Actor | Connect/read | Send |
|---|---|---|
| Admin | Any Ticket in current business | Denied (`FORBIDDEN`) |
| Agent | Any Ticket in current business | Allowed unless closed |
| Customer | Own Ticket only | Allowed on own Ticket unless closed |
| Cross-business or non-owner Customer | Rejected before accept; no existence disclosure | Not possible |

- The query token is accepted only as an access token and is never logged, echoed, placed in the
  manager, or included in an event. Refresh, malformed, expired, and missing tokens fail.
- JWT claims identify only the candidate user. Current role and business always come from the User
  row, and Ticket scope comes from the M3 SQL predicates.
- Client `sender_id`, `sender_role`, `business_id`, `ticket_id`, timestamp, or extra fields are
  forbidden by strict event schemas. Sender metadata is loaded from trusted current state.
- If the user is deleted, token expires, role changes to Admin, business/ticket access changes, or
  Customer ownership no longer matches, the next sensitive event is denied using current state.
- Handshake failures reveal no Ticket data. Cross-tenant and missing Tickets remain
  indistinguishable at the authorization layer.

## 8. Message Persistence Strategy

- History first authorizes the Ticket, then joins/loads `Message.sender` and selects only
  `Message.ticket_id == authorized_ticket.id`, ordered by `created_at ASC, id ASC`.
- A send service receives only trusted `user_id`, path `ticket_id`, and validated body. In one fresh
  Session it re-resolves the current User, locks the authorized Ticket row, checks role and current
  status, inserts `Message(ticket_id=ticket.id, sender_id=user.id, body=...)`, and explicitly sets
  Ticket activity time using the database time convention.
- Message insertion and Ticket activity update commit together. Any exception rolls back both.
  Refresh/load the committed Message and sender before closing the Session, then return a detached
  explicit result safe for serialization.
- `message.created` is constructed from committed database values and broadcast afterward. A
  broadcast failure never rolls back the committed Message; reconnect/history is the recovery
  path.
- Concurrent sends use the Ticket row lock for commit ordering and compatibility with M4 status
  writes. History ordering remains deterministic using timestamp plus UUID. Live delivery will be
  serialized per in-process Ticket room; the database remains authoritative if network scheduling
  or disconnection prevents observation.

## 9. Connection Manager Design

- Store `dict[UUID, set[WebSocket]]` keyed only by Ticket ID. Store neither JWTs nor database
  Sessions.
- `connect` accepts only after the caller has completed authorization, then registers under an
  async lock. `disconnect` is idempotent and removes empty room state.
- `broadcast` copies the room membership under the lock, releases the lock before network I/O,
  sends the same already-serialized event to the snapshot, and removes connections whose send
  fails. One slow/broken client must not permanently block cleanup of other peers.
- A per-room async operation/broadcast lock preserves local `message.created` order and prevents
  concurrent mutation of the room structure; lock lifecycle is cleaned with the room.
- A connection is eligible for a room only because the route authorized it before registration.
  Every writer is reauthorized separately, so room membership never grants write permission.
- One module-level manager instance is shared by WebSocket routes and M4 status background
  broadcasts inside one FastAPI process.

This design intentionally requires `uvicorn ... --workers 1`. Independent workers/instances have
independent room maps, so they cannot deliver events to one another. README documentation of this
M5 limitation is allowed only during approved implementation and must use a verified run command.

## 10. Event Contracts

The implementation must match `docs/API_CONTRACT.md` exactly.

Client to server:

```json
{"type":"message.send","body":"Hello, I need help with my account."}
```

Server to authorized Ticket room, after commit:

```json
{"type":"message.created","data":{"id":"message-uuid","ticket_id":"ticket-uuid","sender_id":"user-uuid","sender_name":"Customer One","sender_role":"customer","body":"Hello, I need help with my account.","created_at":"2026-10-09T10:01:00Z"}}
```

Server to authorized Ticket room, after a meaningful status commit:

```json
{"type":"ticket.status_changed","data":{"ticket_id":"ticket-uuid","status":"resolved","updated_at":"2026-10-09T10:05:00Z"}}
```

Recoverable post-accept failure, sent only to the initiating connection:

```json
{"type":"error","data":{"code":"TICKET_CLOSED","message":"This ticket no longer accepts messages."}}
```

Strict Pydantic input parsing must reject malformed JSON, non-object payloads, missing/wrong
`type`, missing/non-string/empty/over-5,000-character body, identity fields, and every other extra
field. Use only documented error codes: `FORBIDDEN`, `VALIDATION_ERROR`, `TICKET_CLOSED`, and
`INTERNAL_SERVER_ERROR`. Do not send stack traces, SQL errors, token values, or protected details.

## 11. Ticket Status Broadcasting

- Do not add a status endpoint or reproduce transition rules. Continue to call the M4 update
  service, which locks, validates, commits, refreshes, and returns the authorized Ticket.
- Make the smallest internal service refinement: expose a typed update result containing the
  Ticket and `status_changed` boolean while preserving a compatibility wrapper if useful to avoid
  unnecessary test churn. The boolean is computed inside the existing locked transaction, not by
  a racy pre-read in the route.
- The existing PATCH route adds a Starlette/FastAPI background task only when `status_changed` is
  true. The async task broadcasts the documented event through the shared manager after the
  service has already committed. Assignment-only updates and same-status no-ops emit nothing.
- Failed authorization, validation, transition, or commit cannot enqueue an event. Event data uses
  the committed Ticket ID, status, and refreshed `updated_at`.
- Background delivery is best-effort in this single process. A process crash after commit but
  before broadcast can lose the live notification; the REST resource remains authoritative. An
  outbox/broker would close that gap but is explicitly outside M5.

## 12. Database Transaction Strategy

- HTTP history uses the ordinary request-scoped read Session and performs authorization before the
  Message query.
- WebSocket handshake uses one short read Session; idle sockets retain no Session.
- Every `message.send` opens a new Session inside the synchronous worker operation, performs token
  user resolution and row-locked Ticket authorization, changes Message and Ticket activity,
  commits once, refreshes the output, and closes. All exceptions roll back.
- M4 PATCH continues its existing request transaction and Ticket row lock. Status notification is
  scheduled only from its post-commit outcome.
- Row locking the same Ticket in message-send and status-update paths defines close-versus-send
  behavior: whichever transaction acquires the lock first commits first; the later writer observes
  the new current state. Once closure commits, later message transactions reject.
- No database transaction spans `receive`, socket send, room broadcast, or other network waits.
- M5 tests use a disposable PostgreSQL database ending `_test`, upgraded to Alembic head. Because
  WebSocket operations use independent sessions/threads, test setup cannot rely solely on an
  uncommitted outer transaction invisible to those sessions; fixtures must commit deterministic
  rows and clean only the disposable test database.

## 13. Security Invariants

- Authorization is complete before `accept()` and before room registration.
- Every Ticket access is scoped by trusted `current_user.business_id`; Customers additionally
  require `customer_id == current_user.id`.
- Every incoming write revalidates access-token expiration/type, current User/role/business,
  Ticket access, sender role, and current closed state.
- Admin is read-only. Agent may send within its business. Customer may send only to its own Ticket.
- Sender, tenant, Ticket, role, ID, and timestamp are never trusted from a client payload.
- A Message is broadcast only after its transaction commits; a failed insert/activity update emits
  no success event.
- Room keys and manager delivery isolate Tickets. Unauthorized sockets never join and unrelated
  rooms never receive an event.
- Closing a Ticket wins against subsequent sends through compatible database row locking; existing
  history remains readable.
- Browser origins must match the explicit configured allowlist. CORS middleware alone is not a
  WebSocket security control.
- Query tokens and complete authenticated WebSocket URLs are never logged. Production uses WSS.
- Errors expose neither resource existence across boundaries nor internal exceptions/credentials.
- User message bodies remain untrusted display text; M6 must render them as text, not raw HTML.

## 14. Ordered Implementation Tasks

### M5-01 — Define message and WebSocket schemas

**Objective:** Add explicit history and event contracts matching the documented envelope and
payloads.

**Existing components to reuse:** `StrictRequest`, `MessageBody`, User/Ticket enums, Pydantic UTC
datetime serialization, and `ErrorResponse` conventions.

**Expected files to modify:** create `backend/app/schemas/message.py`; minimally adjust
`backend/app/schemas/ticket.py` only if moving/re-exporting `MessageBody` prevents duplication.

**Implementation approach:** Define ORM-compatible Message output, `{data: list[...]}` response,
strict `message.send` input, `message.created`, `ticket.status_changed`, and WebSocket `error`
outputs. Forbid extra client fields and preserve the 1–5,000-character trimmed body rule.

**Dependencies:** Existing Pydantic configuration and documented API contract.

**Security implications:** Explicit schemas prevent sender/tenant/role/timestamp spoofing and ORM
field leakage.

**Acceptance criteria:** Examples validate; empty/oversized/wrong-type/extra-field inputs fail;
serialized outputs contain exactly documented public fields.

**Verification steps:** Run schema unit tests, Ruff, mypy, and import/compile checks.

### M5-02 — Add shared token authentication and authorized history

**Objective:** Reuse one database-backed access-token resolver and implement the authorized
chronological Message history endpoint.

**Existing components to reuse:** `decode_token`, `_token_error`, `get_current_user`,
`get_authorized_ticket`, `get_db`, Message sender relationship/index, and Ticket router.

**Expected files to modify:** `backend/app/api/dependencies.py`,
`backend/app/services/messages.py` (new), `backend/app/api/routes/tickets.py`,
`backend/tests/test_messages.py` (new).

**Implementation approach:** Extract a token-string resolver used by the unchanged HTTPBearer
adapter and later WebSocket auth. History first resolves the authorized Ticket, then selects that
Ticket's Messages with sender metadata ordered by `created_at, id`; register GET on the existing
Ticket router with the documented envelope.

**Dependencies:** M5-01, M2 authentication, and M3 authorization.

**Security implications:** The Message query cannot execute from an unverified path ID; inaccessible
or missing Tickets return the same 404 and password/token/internal fields never serialize.

**Acceptance criteria:** Admin/Agent can read same-business history, Customer can read only owned
history, cross-tenant/cross-Customer IDs return 404, missing/invalid/refresh tokens fail, empty
history is `data: []`, and order/sender metadata are correct.

**Verification steps:** Run focused history/API/OpenAPI tests against disposable PostgreSQL and the
M2/M3 authentication/authorization regressions.

### M5-03 — Implement the in-memory Ticket-room manager

**Objective:** Track, broadcast to, and clean up authorized connections in one process.

**Existing components to reuse:** FastAPI/Starlette `WebSocket`; no new package.

**Expected files to modify:** create `backend/app/websocket/__init__.py`,
`backend/app/websocket/manager.py`, and focused manager tests (either
`backend/tests/test_websocket_manager.py` or the M5 integration module).

**Implementation approach:** Implement async connect/disconnect/broadcast methods, room membership
snapshots, per-room synchronization, idempotent cleanup, and failed-peer removal. Export one shared
manager instance without importing routers or services.

**Dependencies:** M5-01 event serialization.

**Security implications:** Callers may register only post-authorization; broadcasts accept an
explicit Ticket ID and never enumerate/send to unrelated rooms; no token or Session is retained.

**Acceptance criteria:** Same-room clients receive events, other rooms do not, disconnect and send
failure remove members, empty room/lock state is released, and concurrent mutation is safe.

**Verification steps:** Run focused async/connection manager tests plus Ruff, mypy, and compile.

### M5-04 — Implement short-session message persistence

**Objective:** Persist authorized chat and Ticket activity atomically before producing a broadcast
payload.

**Existing components to reuse:** shared token resolver, `SessionLocal`/session factory, Message and
Ticket models, `get_authorized_ticket(for_update=True)`, role enums, and M4 rollback/locking pattern.

**Expected files to modify:** `backend/app/services/messages.py`, optionally a narrow injectable
session-factory helper in `backend/app/db/session.py`, and `backend/tests/test_messages.py`.

**Implementation approach:** Own a fresh Session per worker call; revalidate token/User, lock the
authorized Ticket, enforce Agent/Customer send roles and non-closed state, insert Message, explicitly
advance Ticket activity, commit once, refresh trusted output, and roll back on all failures.

**Dependencies:** M5-01 and M5-02; migrated disposable PostgreSQL.

**Security implications:** Current state is authoritative for each send; sender cannot be supplied;
the shared Ticket lock prevents stale close checks; no success payload exists before commit.

**Acceptance criteria:** Agent and owning Customer messages persist; Admin/cross-tenant/non-owner/
closed sends fail; Message plus activity update are atomic; insert/update failures roll back; two
concurrent sends remain persisted and deterministically retrievable.

**Verification steps:** Run PostgreSQL service/integration tests including forced rollback,
close-versus-send concurrency, activity timestamp, and trusted sender assertions.

### M5-05 — Add the authenticated WebSocket endpoint

**Objective:** Implement the complete pre-accept authorization and post-accept event loop at the
documented URL.

**Existing components to reuse:** M5-01 schemas, shared token resolver, M3 Ticket policy, M5-03
manager, M5-04 persistence service, settings `cors_origins`, and FastAPI application router.

**Expected files to modify:** create `backend/app/api/routes/websocket.py`; modify
`backend/app/api/router.py`; add `backend/tests/test_websocket_chat.py`.

**Implementation approach:** Validate Origin/token/Ticket access in a short worker session before
accepting; register only authorized sockets; parse JSON into the strict event schema; delegate each
send to the reauthorizing persistence service; broadcast committed `message.created`; map known
errors to sanitized documented events/close behavior; always disconnect in `finally`.

**Dependencies:** M5-01 through M5-04.

**Security implications:** Refresh/expired/invalid tokens and unauthorized Tickets never join;
every write rechecks current access; the URL/token is not logged; malformed input cannot select
identity or a different Ticket.

**Acceptance criteria:** Authorized Admin/Agent/owner connect; forbidden handshakes are rejected
pre-accept; Agent/Customer live sends persist and reach both same-room clients; Admin send is denied;
other rooms/businesses receive nothing; closed/currently unauthorized/expired writers cannot send;
disconnect cleanup works.

**Verification steps:** Run real `TestClient.websocket_connect` scenarios backed by PostgreSQL,
including two simultaneous clients, separate rooms, handshake failures, post-connect state changes,
malformed payloads, and disconnects.

### M5-06 — Broadcast committed meaningful Ticket status changes

**Objective:** Integrate the existing M4 PATCH workflow with `ticket.status_changed` without
duplicating lifecycle rules.

**Existing components to reuse:** `update_ticket`, M4 row lock and transition policy, Ticket router,
M5 manager, and status event schema.

**Expected files to modify:** `backend/app/services/tickets.py`,
`backend/app/api/routes/tickets.py`, `backend/tests/test_tickets.py`, and
`backend/tests/test_websocket_chat.py`.

**Implementation approach:** Return internal committed change metadata from the M4 service (keeping
a compatibility wrapper if valuable); enqueue an async manager background broadcast only for a
true status change after successful commit. Use committed Ticket fields. Do not emit for assignment
or same-status no-op.

**Dependencies:** M5-01, M5-03, and unchanged M4 policy behavior.

**Security implications:** Failed/unauthorized/invalid writes emit nothing; event scope is the
authorized path Ticket room and contains no private identity data.

**Acceptance criteria:** Every allowed meaningful status commit emits one matching event; failed
transition/commit, assignment-only update, and no-op emit none; unrelated rooms receive none; a
newly closed Ticket rejects subsequent messages on already-open sockets.

**Verification steps:** Run focused HTTP-plus-live-WebSocket status tests, all M4 Ticket tests, and
forced-failure/no-op checks.

### M5-07 — Complete adversarial integration and regression coverage

**Objective:** Prove end-to-end persistence, delivery, authorization, isolation, error handling,
and cleanup using the real app and PostgreSQL.

**Existing components to reuse:** existing TestClient, token factories, Business/User/Ticket
factories, disposable PostgreSQL guard, Alembic config, and M2-M4 regression suites.

**Expected files to modify:** `backend/tests/conftest.py`, `backend/tests/test_messages.py`,
`backend/tests/test_websocket_manager.py` if created, and
`backend/tests/test_websocket_chat.py`.

**Implementation approach:** Add committed multi-session fixtures/factories safe for WebSocket
threads, deterministic cleanup, an allowed test Origin, two-client scenarios, database assertions,
cross-room negative assertions with bounded receive techniques, and regression selections.

**Dependencies:** M5-01 through M5-06 and an Alembic-upgraded disposable PostgreSQL `_test`
database.

**Security implications:** Tests explicitly target cross-business/cross-Customer leakage, token
type/expiry/deletion, spoof fields, Admin writes, post-connect revocation/closure, error disclosure,
and room isolation.

**Acceptance criteria:** All Section 16 criteria have executable positive and negative coverage;
real PostgreSQL and real ASGI WebSocket behavior are exercised; no critical defect or flaky
unbounded receive remains.

**Verification steps:** Run focused M5, M2-M4 regression, and full backend suites, then static and
Alembic checks from Section 17.

### M5-08 — Final verification and execution record

**Objective:** Execute the approved checks, record exact outcomes, and document the verified
single-process run constraint without starting M6.

**Existing components to reuse:** this plan, current README backend commands, pyproject tool config,
and M4 reporting format.

**Expected files to modify:** `exec-plans/active/M5-websocket-chat.md` and `README.md` only where an
actually verified single-worker command/limitation is needed. Move the plan to `completed/` only in
an explicitly approved final-completion phase after all criteria pass.

**Implementation approach:** Run every Section 17 command, preserve exact PASS/FAIL/NOT RUN output,
inspect diff/status for scope and secrets, update only accurate instructions, and report defects and
limitations honestly.

**Dependencies:** M5-01 through M5-07.

**Security implications:** Verification must use only disposable `_test` data; inspect for token,
password, URL-query, stack-trace, and cross-tenant exposure; never commit `.env` or credentials.

**Acceptance criteria:** Required checks pass or exact blockers are recorded; documentation matches
verified behavior; no unresolved critical M5 defect; no M6 implementation, commit, or push occurs.

**Verification steps:** Execute all Section 17 commands, `git diff --check`, `git status --short`,
and focused secret/scope review; append exact results to this plan.

## 15. Testing Strategy

Use real FastAPI TestClient WebSocket sessions and a real disposable PostgreSQL database; manager
unit tests alone are insufficient.

- **History:** all roles, empty/non-empty, sender fields, UTC timestamps, deterministic same-time
  ordering, 401, same non-disclosing 404 for missing/cross-business/cross-Customer.
- **Handshake auth:** valid access token; missing, malformed, expired, refresh token, deleted User,
  disallowed/missing Origin, cross-business Ticket, and non-owner Customer. Assert no room join or
  protected payload.
- **Role/write auth:** Agent and owner Customer send; Admin connects/read-only but gets
  `FORBIDDEN`; extra `sender_id`/`business_id`/`ticket_id`/role fields are rejected; current User
  deletion/role or authorization change is honored on the next write.
- **Validation/errors:** malformed JSON, array/scalar payload, unsupported/missing type,
  missing/non-string/blank/over-5,000 body, sanitized database failure, and continued/closed
  connection behavior per approved decision.
- **Live chat:** two authorized clients in one room receive one authoritative event after send;
  database row and activity timestamp commit first; sender metadata/timestamp are correct; reconnect
  plus history recovers the Message; failed commit produces no event.
- **Isolation:** a separate Ticket room and separate-business room receive no foreign event. Use
  bounded synchronization/timeouts or manager observation so negative receive assertions cannot
  hang the suite.
- **Status:** allowed PATCH emits after commit; no-op, assignment-only, invalid transition,
  unauthorized update, and forced failure do not; payload and room are correct.
- **Closed lifecycle/concurrency:** history is still readable; already-closed and newly closed
  Tickets reject sends; row-lock concurrency proves no post-close stale acceptance.
- **Lifecycle:** normal disconnect, abrupt disconnect, failed peer send, and empty-room cleanup.
- **Regression:** M2 auth/user tests, M3 authorization tests, all M4 Ticket tests, then the complete
  backend suite. Do not claim browser UI behavior; that belongs to M6.

## 16. Acceptance Criteria

M5 is acceptable only when all are verified:

1. The history endpoint returns only authorized Ticket Messages in documented order/envelope.
2. Access-token WebSocket authentication and current database User resolution work.
3. Missing, invalid, expired, refresh, deleted-user, and unauthorized handshakes are rejected
   before room membership and protected output.
4. Tenant isolation and Customer ownership apply to history, connection, sending, and delivery.
5. Admin is read-only; Agent and owning Customer send permissions work.
6. Client input cannot spoof sender, role, business, Ticket, IDs, or timestamps.
7. Each accepted Message and Ticket activity update commit atomically in PostgreSQL.
8. `message.created` is broadcast only after commit to all current same-room authorized clients and
   never to another Ticket/business.
9. Persisted Messages survive disconnect/reconnect and appear through history with trusted sender
   name, role, body, and UTC timestamp.
10. Meaningful committed status changes emit exactly one documented event to the correct room;
    failure, assignment-only, and no-op do not.
11. Closed Tickets preserve history but reject every new write using current database state.
12. Connection and per-room synchronization state is cleaned after disconnect/failure.
13. Malformed/unsupported input and internal failures produce sanitized documented protocol
    behavior without false success.
14. M2, M3, and M4 behavior remains passing; static checks and full backend suite pass.
15. The single-process limitation and verified one-worker run command are documented.
16. No unresolved critical current-scope security/correctness defect remains.

## 17. Verification Commands

Run from `backend/`. Set `TEST_DATABASE_URL` to a disposable PostgreSQL database whose name ends in
`_test`; never point these commands at valuable development or production data. First upgrade that
database to the single Alembic head using the existing guarded procedure from the completed M4 plan.

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m compileall -q app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff check app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff format --check app alembic tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run mypy app tests
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run pytest -q tests/test_messages.py tests/test_websocket_manager.py tests/test_websocket_chat.py --tb=short
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run pytest -q tests/test_auth.py tests/test_users.py tests/test_m2_integration.py tests/test_authorization.py tests/test_models.py tests/test_tickets.py --tb=short
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run pytest -q --tb=short
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run alembic heads
```

If M5-03 keeps manager cases in `test_websocket_chat.py` rather than creating
`test_websocket_manager.py`, omit that nonexistent path from the focused command and record the
exact executed command. Also execute the M4 guarded `alembic check` wrapper against the disposable
database and, from the repository root:

```bash
git diff --check
git status --short
```

These are planned commands, not results. No M5 implementation tests were run during Phase 1.

## 18. Risks and Trade-offs

- **Single-process delivery:** In-memory rooms do not cross worker/instance boundaries. Run one
  worker; scaling requires a broker later and is intentionally not solved here.
- **Commit/broadcast gap:** A crash or failed socket send after commit can lose the live event.
  Persistence/history remains correct; an outbox/replay system is out of scope.
- **Query token exposure:** The mandated URL can appear in infrastructure logs. Use short-lived
  access tokens, WSS, URL redaction, and never log the complete URL; the client cannot set a normal
  browser Authorization header for this connection shape.
- **Long-lived authentication:** Token/authorization is rechecked on sensitive sends, not
  continuously while idle. A revoked idle socket may remain connected and receive room events
  until disconnect unless Phase 2 adds per-recipient revalidation; user deletion/role mutation is
  not currently an exposed runtime workflow. This residual risk must be documented and reviewed.
- **Origin decision:** Requiring an Origin improves browser security but excludes non-browser
  clients that omit it unless the policy is relaxed. This proposed behavior needs Phase 2 approval.
- **Synchronous database stack:** SQLAlchemy work must leave the async event loop and own its Session
  in the worker. This adds a small adapter but avoids idle transactions and event-loop blocking.
- **Ordering:** Ticket locking and per-room serialization provide local commit/broadcast order;
  history's `(created_at, id)` sort is authoritative. No global ordering exists across Tickets.
- **Status delivery:** FastAPI background delivery is post-commit and best-effort. It must not
  change the already-successful PATCH response if a peer disconnects.
- **Test isolation:** Existing outer-transaction fixtures are insufficient for independently opened
  WebSocket Sessions. New committed fixtures require strict `_test` guards and deterministic
  cleanup.
- **No migration expected:** Existing fields/indexes are sufficient. If implementation uncovers a
  schema need, stop and amend/review this plan rather than silently adding a migration.

## 19. Definition of Done

M5 is done only after explicit Phase 2 implementation approval and subsequent verification shows:

- M5-01 through M5-08 are implemented within scope.
- Every Section 16 criterion has executed evidence using FastAPI WebSockets and disposable
  PostgreSQL where applicable.
- Focused M5, M2-M4 regression, complete backend, compile, Ruff, mypy, Alembic, diff, and secret
  checks have actual recorded outcomes.
- The API and event shapes remain consistent with `docs/API_CONTRACT.md`; proposed ambiguity
  decisions are approved and documented consistently if selected.
- No critical tenant-isolation, authorization, persistence, closed-Ticket, or cross-room defect is
  open.
- README accurately states the tested single-worker limitation and actual run instructions.
- This execution plan records exact results and limitations; it is moved to `completed/` only after
  an approved final review.
- No frontend/M6 work, optional infrastructure, automatic commit, or push has occurred.

Phase 1 stops here and waits for review.

## 20. Phase 2 Implementation Record

Implementation date: 2026-10-10

Phase status: **IMPLEMENTED, PENDING PHASE 3 VERIFICATION**. This plan remains in `active/`; no M6
work, commit, or push was performed.

### Implemented scope

- Added strict message/history and WebSocket event schemas, including trimmed 1–5,000-character
  bodies and forbidden client-supplied extra identity fields.
- Added tenant- and owner-authorized chronological message history at
  `GET /tickets/{id}/messages`.
- Added the pre-accept authenticated and origin-checked
  `WS /ws/tickets/{id}?token=<access-token>` endpoint.
- Added a single-process Ticket-room connection manager with failed-peer and empty-room cleanup.
- Added per-send token/User/Ticket authorization revalidation, Agent/Customer write policy,
  Admin read-only behavior, current closed-Ticket rejection, Ticket row locking, and atomic
  Message/activity timestamp persistence before broadcast.
- Added post-commit `ticket.status_changed` delivery for meaningful M4 status transitions.
- Added focused schema, manager, HTTP history, live WebSocket, persistence, isolation, role,
  closed-Ticket, and status-broadcast tests. No migration or dependency was added.

### Files created or modified

- Modified `backend/app/api/dependencies.py`, `backend/app/api/router.py`,
  `backend/app/api/routes/tickets.py`, `backend/app/db/session.py`, and
  `backend/app/services/tickets.py`.
- Created `backend/app/api/routes/websocket.py`, `backend/app/schemas/message.py`,
  `backend/app/services/messages.py`, `backend/app/websocket/__init__.py`,
  `backend/app/websocket/events.py`, and `backend/app/websocket/manager.py`.
- Created `backend/tests/test_messages.py`, `backend/tests/test_websocket_chat.py`, and
  `backend/tests/test_websocket_manager.py`.
- Updated this execution record and `README.md` with verified behavior and the one-worker command.

### Actual validation results

- **PASS** — focused M5 suite: `14 passed, 1 warning in 0.60s`.
- **PASS** — corrected M2-M4 regression selection with both `TEST_DATABASE_URL` and legacy
  `M1_TEST_DATABASE_URL` set to `helpdesk_m5_test`: `112 passed, 1 warning in 3.37s`.
- **PASS** — complete backend suite with both test URL variables: `126 passed, 1 warning in 3.47s`.
- **PASS** — the exact credential-redacting guarded full-suite command now documented in README:
  `126 passed, 1 warning in 3.59s`.
- **PASS** — `python -m compileall -q app alembic tests`.
- **PASS** — Ruff format check: `51 files already formatted`.
- **PASS** — Ruff lint: `All checks passed!`.
- **PASS** — strict mypy: `Success: no issues found in 49 source files`.
- **PASS** — Alembic reports one head: `a3930ac451be (head)`.
- **PASS** — guarded `alembic check` on `helpdesk_m5_test`: `No new upgrade operations detected.`
- **PASS** — verified one-worker startup on port 8015 and `GET /health`: HTTP 200 with
  `{"status":"ok"}`; the temporary server shut down normally.
- **WARNING** — pytest reports the existing Starlette TestClient/httpx deprecation warning; it
  does not fail the suite and no unnecessary dependency change was made.

Two setup/configuration failures were resolved and retained here for accuracy:

- The first disposable migration wrapper populated settings before replacing `DATABASE_URL`, so
  Alembic used the cached development URL and the focused suite then reported eight missing-table
  setup errors (six unit tests passed). The wrapper was corrected to set the disposable URL and
  clear the settings cache before importing Alembic; upgrade then created the test schema and the
  focused suite passed 14 tests. No development downgrade or schema mutation occurred.
- The first regression invocation set only `TEST_DATABASE_URL`; 86 tests passed and 26 M1 model
  tests refused to run because they require `M1_TEST_DATABASE_URL`. Re-running with both variables
  pointing to the same guarded `_test` database passed all 112 selected tests.

### Phase 2 handoff items and limitations

- Phase 3 must perform the comprehensive security/concurrency matrix from Section 15, including
  expired/deleted-user handshakes, malformed frames, forced commit failures, reconnect recovery,
  negative cross-room delivery, concurrent close/send behavior, and exact no-event assertions.
- The connection manager is intentionally process-local; run exactly one worker. Multi-process
  fan-out requires infrastructure outside M5 scope.
- An idle revoked/deleted User socket can remain connected and receive room broadcasts until it
  disconnects; every sensitive send is revalidated against the current database state.
- Broadcast is best-effort after commit. A process failure in the commit/broadcast gap does not
  lose the stored Message, but clients may need history reload to observe it.
- Access tokens remain in the approved WebSocket query parameter shape and can be exposed by
  upstream URL logging; production must use WSS and redact complete WebSocket URLs.

## 21. Phase 3 Validation Record

Validation date: 2026-10-10

Phase status: **PHASE 3 VERIFIED, PENDING PHASE 4 REVIEW**. M5 remains in `active/`; it has not been
marked complete, and no M6 work, commit, or push was performed.

### Coverage added

- Verified deterministic history ordering for equal timestamps, Admin read-only history access,
  and preserved history for closed Tickets.
- Verified expired-token and deleted-User handshake rejection in addition to the existing missing,
  invalid, refresh-token, tenant, and Customer-ownership cases.
- Verified current database role enforcement on every send, malformed/unsupported event recovery,
  sanitized internal errors, and absence of false broadcasts after a rolled-back database write.
- Verified two authorized live clients exchange persisted messages, reconnect/history consistency,
  same-business and cross-business Ticket-room isolation, and disconnect membership cleanup.
- Verified concurrent Message writes remain consistent in PostgreSQL and that Ticket row locking
  prevents a Message from committing after a concurrent close.
- Verified status broadcasts are not scheduled for no-op, assignment-only, rejected, or failed
  updates. Existing tests continue to verify exactly one post-commit event for a meaningful status
  change.

### Actual validation results

- **PASS** — final focused M5 suite: `25 passed, 1 warning in 1.16s`.
- **PASS** — M2-M4 regression selection: `112 passed, 1 warning in 3.13s`.
- **PASS** — final complete backend suite: `137 passed, 1 warning in 4.43s`.
- **PASS** — final syntax/import compilation: `python -m compileall app tests`.
- **PASS** — final Ruff lint: `All checks passed!`.
- **PASS** — final Ruff format check: `51 files already formatted`.
- **PASS** — final strict mypy: `Success: no issues found in 49 source files`.
- **PASS** — Alembic reports one head: `a3930ac451be (head)`.
- **PASS** — guarded `alembic check` on disposable `helpdesk_m5_test`:
  `No new upgrade operations detected.`
- **PASS** — `git diff --check`.
- **PASS** — Phase 3 diff scan found no likely credential/private-key material.
- **NOT RUN: 0** — every Phase 3 verification category in the approved plan was exercised by the
  focused, regression, full-suite, or static/database checks.
- **WARNING** — pytest still reports the existing Starlette TestClient/httpx deprecation warning;
  it does not fail the suite and no dependency change was introduced.

The pytest command counts overlap: the 25 focused and 112 regression cases are included in the
137-test full suite and must not be summed as distinct tests.

### Failures investigated

- The first expanded focused run reported `24 passed, 1 failed`. The failure was in the new test,
  which inspected a nonexistent private Starlette queue attribute. It was corrected to use the
  installed transport's public stream statistics; the application behavior was not changed, and
  all subsequent focused and full runs passed.
- An initial non-escalated database-backed command was blocked because the sandbox denied local
  PostgreSQL/cache access. It was rerun through the permitted execution path against the guarded
  disposable `_test` database and passed. No valuable database was reset or downgraded.

### Defects and changes

- No production M5 defect was confirmed, so no application source, dependency, migration, API
  contract, or runtime configuration was changed in Phase 3.
- Added only the essential M5 regression and integration cases to
  `backend/tests/test_websocket_chat.py`, plus this evidence record.

### Security and correctness conclusion

- Handshake authentication, current-User resolution, tenant isolation, Customer ownership,
  Admin read-only policy, Agent/Customer writes, closed-Ticket enforcement, room scoping, and
  sanitized failure handling passed against real FastAPI WebSockets and disposable PostgreSQL.
- Message persistence precedes broadcast, forced database failure rolls back without broadcasting,
  history matches committed data, and concurrent close/send behavior preserves the closed-Ticket
  invariant.
- Status delivery remains post-commit and limited to meaningful status changes; failure,
  assignment-only, and no-op paths emit no event.

### Remaining risks

- The documented process-local connection manager still requires exactly one backend worker.
- Broadcast remains best-effort after commit; a process crash in the commit/broadcast gap can
  require clients to reload history.
- An idle revoked/deleted User connection is not continuously revalidated and can receive room
  events until its next sensitive send or disconnect.
- Query-string WebSocket access tokens require WSS and upstream URL redaction in production.

## 22. Phase 4 Final Review and Milestone Completion

Review date: 2026-10-10

Milestone status: **COMPLETE**. All 16 mandatory acceptance criteria in Section 16 were verified
against the implementation and executable tests. No M6 or M7 implementation was performed.

### Review scope and repository evidence

- Reviewed the M5 implementation commit `5aa3c43` and Phase 3 integration/security test commit
  `82abe46`, plus the current source, supporting requirements, security, API, and architecture
  documentation.
- The worktree was clean when Phase 4 began. This review changed only this execution record and
  the README milestone/integration documentation; no application source or test behavior changed.
- Tests used only the guarded disposable PostgreSQL database `helpdesk_m5_test`. It was upgraded
  to Alembic head; no downgrade, reset, or destructive action was performed on valuable data.

### Acceptance criteria result

1. **PASS** — authorized history is tenant/owner scoped and deterministically ordered.
2. **PASS** — WebSocket authentication accepts only access tokens and resolves the current User.
3. **PASS** — missing, malformed, expired, refresh, and deleted-User credentials are rejected
   before acceptance.
4. **PASS** — cross-business and cross-Customer HTTP/WebSocket access is non-disclosing and
   rejected.
5. **PASS** — Agent and owning Customer can write; Admin is read-only.
6. **PASS** — sender identity is server-derived and cannot be spoofed.
7. **PASS** — Message persistence and Ticket activity updates commit atomically in PostgreSQL.
8. **PASS** — committed messages reach authorized clients in only the matching Ticket room.
9. **PASS** — disconnect/reconnect history is consistent with committed database state.
10. **PASS** — meaningful committed status changes broadcast exactly once; failed, no-op, and
    assignment-only updates do not broadcast status events.
11. **PASS** — closed Tickets preserve history and reject writes, including already-connected
    clients.
12. **PASS** — disconnect and failed-peer cleanup remove stale room membership.
13. **PASS** — malformed input and internal failures return sanitized errors without false
    persistence or broadcast.
14. **PASS** — focused M5, M2-M4 regressions, full suite, static analysis, and migration checks pass.
15. **PASS** — the required single-worker deployment constraint is documented and reflected in
    the verified backend command.
16. **PASS** — no unresolved critical M5 security or correctness defect was found.

Acceptance totals: **16 PASS / 0 FAIL / 0 NOT RUN**.

### Exact Phase 4 validation commands and results

The three pytest commands used the following guarded command shape, executed from `backend/` with
each exact argument list shown below. It derived `helpdesk_m5_test` from typed settings, asserted
PostgreSQL and a database name ending in `_test`, assigned the result to all three test URL
settings, cleared the settings cache, and invoked `pytest.main(...)` without printing credentials:

```text
pytest -q --tb=short tests/test_messages.py tests/test_websocket_manager.py tests/test_websocket_chat.py
PASS: 25 passed, 1 warning in 0.82s

pytest -q --tb=short tests/test_auth.py tests/test_users.py tests/test_m2_integration.py tests/test_authorization.py tests/test_models.py tests/test_tickets.py
PASS: 112 passed, 1 warning in 3.77s

pytest -q --tb=short
PASS: 137 passed, 1 warning in 3.49s
```

```bash
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; u=make_url(get_settings().database_url).set(database='helpdesk_m5_test'); assert u.get_backend_name() == 'postgresql' and (u.database or '').endswith('_test'); v=u.render_as_string(hide_password=False); os.environ['DATABASE_URL']=v; os.environ['TEST_DATABASE_URL']=v; os.environ['M1_TEST_DATABASE_URL']=v; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','--tb=short','tests/test_messages.py','tests/test_websocket_manager.py','tests/test_websocket_chat.py']))"

UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; u=make_url(get_settings().database_url).set(database='helpdesk_m5_test'); assert u.get_backend_name() == 'postgresql' and (u.database or '').endswith('_test'); v=u.render_as_string(hide_password=False); os.environ['DATABASE_URL']=v; os.environ['TEST_DATABASE_URL']=v; os.environ['M1_TEST_DATABASE_URL']=v; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','--tb=short','tests/test_auth.py','tests/test_users.py','tests/test_m2_integration.py','tests/test_authorization.py','tests/test_models.py','tests/test_tickets.py']))"

UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -c "import os; from sqlalchemy.engine import make_url; from app.core.config import get_settings; u=make_url(get_settings().database_url).set(database='helpdesk_m5_test'); assert u.get_backend_name() == 'postgresql' and (u.database or '').endswith('_test'); v=u.render_as_string(hide_password=False); os.environ['DATABASE_URL']=v; os.environ['TEST_DATABASE_URL']=v; os.environ['M1_TEST_DATABASE_URL']=v; get_settings.cache_clear(); import pytest; raise SystemExit(pytest.main(['-q','--tb=short']))"
```

The exact non-pytest commands and results were:

```text
UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run python -m compileall -q app alembic tests
PASS (exit 0)

UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff check app alembic tests
PASS: All checks passed!

UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run ruff format --check app alembic tests
PASS: 51 files already formatted

UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run mypy app tests
PASS: Success: no issues found in 49 source files

UV_CACHE_DIR=/tmp/helpdesk-mini-uv-cache uv run alembic heads
PASS: a3930ac451be (head)

Guarded command.upgrade(Config('alembic.ini'), 'head') on helpdesk_m5_test
PASS: disposable database migrated to head

Guarded command.check(Config('alembic.ini')) on helpdesk_m5_test
PASS: No new upgrade operations detected.
```

The focused and regression tests are subsets of the 137-test full suite and are not additive.
Test totals for the final full run are **137 PASS / 0 FAIL / 0 NOT RUN**. The sole warning is the
existing upstream Starlette TestClient/httpx deprecation warning; it does not affect behavior and
no dependency change was justified for M5.

### Defects, security conclusion, and limitations

- No confirmed M5-scoped production defect was found in Phase 4, so no source fix or additional
  regression test was necessary.
- Authentication occurs before WebSocket acceptance; database-backed tenant, Customer ownership,
  and current-role checks protect both handshake and message processing. Database commit precedes
  message/status broadcast, and the tests found no room leakage or post-close committed Message.
- The connection manager remains process-local. Production must use exactly one backend worker;
  multi-process fan-out requires later infrastructure outside M5.
- Post-commit broadcasts are best-effort. A process failure in the commit/broadcast gap requires
  clients to recover from message history.
- Idle sockets are not continuously reauthenticated, and query-string tokens require WSS plus
  upstream URL redaction in production.

### M6 frontend integration requirements

- Load authorized REST message history before opening the Ticket WebSocket, then reconcile live
  `message.created` events by Message ID to avoid duplicates.
- Open only one Ticket socket per mounted detail view, use the in-memory access token, support the
  configured exact Origin, and close/reconnect cleanly during navigation or authentication expiry.
- Render Message bodies as text, trust server-provided sender metadata, and handle
  `message.created`, `ticket.status_changed`, and sanitized `error` events.
- Disable message input for Admin and closed Tickets in the UI while retaining backend enforcement;
  reload history after reconnect to recover from best-effort delivery gaps.
