# B6 — Typing and Read-Receipt Verification

Status (2026-10-12): **automated FastAPI/PostgreSQL verification PASS; browser verification NOT RUN**.
The implementation-only deferral is superseded by this pre-deployment audit.

## Executed evidence

- `backend/tests/test_chat_bonuses.py`: real authorized WebSocket typing start/stop, no self echo,
  malformed/spoofed events, Admin/closed-ticket denial, recipient-specific persistent history,
  reconnect history, and independent readers. Real PostgreSQL-backed stale sessions that lose
  ownership/role are rejected for message, attachment, status, typing, and read-receipt delivery.
- `backend/tests/test_event_delivery.py`: current role/business/ownership/deletion/JWT checks,
  recipient-specific receipt audiences, and cleanup on revoked authorization. A failing status
  delivery regression confirmed raw broadcast bypassed reauthorization; status and text-message
  routes now use the existing authorized delivery helpers.
- `backend/tests/test_websocket_manager.py`: deterministic inactivity expiry without sleeps,
  expiry/start race, and last-tab disconnect cleanup. Controlled async futures replace real timers.
- Shared targeted run: **84 PASS, 0 FAIL**; full `.venv/bin/pytest -q`: **285 PASS, 0 FAIL**.
  Frontend `npm test`: **26 PASS, 0 FAIL**, including BIGINT/receipt/deduplication regressions;
  `npm run typecheck`, `npm run lint`, `npm run build`: PASS. These do not establish browser E2E.
- Commands and isolated DB setup are in `exec-plans/active/M7-final-verification.md`, section 13.

## Still NOT RUN / supplementary checklist

Independent browser sessions, UI timing/visibility, mobile/keyboard behavior, token-refresh and
logout interactions, and batched-query instrumentation remain manual verification items.
The following checklist is supplementary, not a list of entirely executed checks.

## Preconditions

- Use an isolated disposable PostgreSQL database and the existing B5 Alembic migration.
  B6 adds no migration. Verify historical Message sequence backfill and current migration head.
- Use actual FastAPI and frontend clients, two independent browser sessions, multiple Agents,
  the owning Customer, another Customer, an Admin, and a second business. Do not alter demo seed
  data or valuable databases to create test fixtures.

## Typing and connection lifecycle

- Verify Agent/Customer typing start/stop, two-second frontend heartbeat, server start throttle,
  five-second server expiry and six-second UI fallback. Typing causes no database writes.
- Verify own presence is hidden, multiple participants appear independently, and one user's
  inactive tab cannot clear their other actively typing tab. Confirm all tabs stopping clears it.
- Verify idle, send, blur, hidden tab, navigation, unmount, logout, abrupt disconnect, refresh,
  and Ticket closure clear presence. Closed Tickets and Admins cannot start typing.
- Verify strict payload rejection, spoofed identity/receipt rejection, invalid/expired/refresh
  token rejection, current database role changes, cross-room, cross-business, and other-Customer
  isolation. Exercise disconnect/expiry/start races and excessive event traffic.

## Persistent, recipient-specific receipts

- "Sent" appears only for server-confirmed persisted outgoing messages. One reader produces
  "Seen by [name]" only for covered messages, not proof that every recipient read. Two Agents
  reading independently must preserve both readers; Admin review and own reads do not count.
- History exposes `read_by` only for the requesting sender's messages. Receipt events reach
  only currently authorized covered-message authors, excluding the reader. No unrelated list
  subscriber receives a cursor or receipt; unread counts stay independent per User.
- Verify read state commits before publication; failed or rolled-back acknowledgements emit
  no receipt. Repeated/stale acknowledgements do not regress state or duplicate writes/events.
- Race concurrent message writers/readers, out-of-order receipts and history responses, and
  messages beyond the acknowledged boundary. Compare BIGINT decimal strings without precision
  loss. Check query counts for batched history receipt lookup and no N+1 behavior.
- Verify no acknowledgement from hidden, prefetched, off-screen, loading, failed, or scrolled-away
  history; reconcile unseen earlier socket messages before acknowledging a visible boundary.
- Reload, reconnect, token refresh, and a different login session restore persisted receipts;
  historical messages without cursors have no read evidence. Logout/user changes must clear
  previous-user cache/receipts and never resurrect authentication or leak presence.

## Regression and final evidence

- Verify B4 list notifications, B5 private unread badges/acknowledgements, pagination/search,
  status filters, latest activity, authentication, RBAC, ticket lifecycle, closed-message rejection,
  room chat persistence, and status broadcasts with real PostgreSQL and browser clients.
- In the authorized final testing phase, add focused regression coverage and run actual repository
  backend/frontend test commands, typecheck, lint, build, migrations, and real browser flows.
  Record exact commands, PASS/FAIL/NOT RUN counts, and defects; do not infer E2E from mocks/builds.
- Review mobile layout, long participant names, multiple readers, keyboard/blur behavior, status
  announcements, and absence of repeated notification noise or new parallel sockets.

## Known limitations

Presence and event delivery are single-process/in-memory and best-effort. REST history restores
durable receipt evidence, not missed ephemeral typing. Per-connection typing throttling does not
replace global connection abuse controls. History remains unpaginated. A visible-render acknowledgement
cannot prove human attention. Browser integration remains unverified. Authorization is rechecked
before delivery, but a narrow database-check/socket-send race remains; this is not atomic revocation.
