# B5 — Unread Verification

Status (2026-10-12): **automated PostgreSQL/API verification PASS; browser verification NOT RUN**.
The original implementation-only deferral is superseded by the pre-deployment audit below.

## Executed evidence

- `backend/tests/test_chat_bonuses.py` exercises authenticated FastAPI requests with real
  PostgreSQL: sender exclusion, independent persistent cursors, idempotent/monotonic reads,
  observed-boundary validation, concurrent readers and a concurrent writer/reader race,
  paginated search/status counts, and tenant/customer denial. No demo database was touched.
- `backend/tests/test_event_delivery.py` verifies current recipient authorization and private
  list/receipt audiences. Confirmed queued-list delivery used stale ownership; delivery now
  reloads the Ticket's current business/customer before selecting recipients.
- `frontend/src/lib/domain.test.ts` covers precise BIGINT boundaries, recipient-specific receipt
  merging, and deduplication of history/socket messages including attachments. These are domain
  unit tests, not proof that browser visibility/scroll acknowledgement works.
- Fresh Alembic upgrade to head on `helpdesk_bonuses_test`: PASS. Full backend
  `.venv/bin/pytest -q`: **285 PASS, 0 FAIL**. Targeted B5–B7/security/manager/demo-start tests:
  **84 PASS, 0 FAIL** (a subset of the full suite). Frontend `npm test`: **26 PASS, 0 FAIL**;
  `npm run typecheck`, `npm run lint`, `npm run build`: PASS.
- Exact commands, isolated environment setup, initial failures/fixes, and shared audit findings
  are recorded in `exec-plans/active/M7-final-verification.md`, section 13.

## Still NOT RUN / supplementary checklist

Real browser visibility/scroll/cache/logout/reconnect flows, populated sequence backfill,
disposable downgrade/re-upgrade, query-count instrumentation, and Docker execution remain
unverified in this audit. The checklist below is retained for those checks; it is not a claim
that every scenario was executed.

## Database and aggregation

- Apply Alembic head to fresh and populated disposable databases. Verify message identity
  backfill, preserved messages/users/tickets, read-state primary/foreign keys, nonnegative
  cursor constraint, and `(ticket_id, sequence)` index. Test downgrade/re-upgrade only against
  disposable data. Existing migration-head assertions may need updating in that phase.
- Verify own messages never count; absent cursors count historical messages from other users.
  Verify counts persist across refresh, logout/login, and separate sessions. Admins and
  closed-ticket viewers can acknowledge authorized history without gaining send permission.
- Exercise multiple pages, subject search, status filters, empty results, and activity sorting.
  Counts must be user-specific and correct without changing pagination totals or query ordering.
  Inspect query counts to confirm a single grouped unread query, not N+1.

## Authorization and race conditions

- Reject missing/invalid/expired access authentication and refresh-token authentication.
  Cross-business and cross-customer Tickets return 404 for history and mark-read. A Message
  ID from a different Ticket returns 404 without exposing it. Extra request fields return 422.
- Repeat and reorder acknowledgements: cursor only increases and other users' state is
  unchanged. Acknowledging an observed boundary must not clear subsequently committed messages.
- Run concurrent message writers/readers, including a writer whose transaction began earlier
  but acquires the Ticket lock later. Verify sequence-based counts and database consistency.
- Deliver socket messages out of order. REST reconciliation must render all messages through
  the observed boundary before acknowledgement; no unseen message may be silently cleared.

## Real-time and frontend

- New messages update the list badge without refresh. Creation/status/assignment events must
  preserve filters, search, page, and latest-activity sorting. Read state does not change Ticket
  activity. Zero counts hide badges on desktop/mobile; accessible count labels remain usable.
- Private `ticket.read` synchronizes the reader's other sessions only, silently. Other users
  receive no receipt from this list stream and retain independent counts. B6 deliberately adds
  separate sender-scoped room receipts; see `CHAT_PRESENCE_VERIFICATION.md`. Verify both business and Customer
  isolation, current database role checks, expired-token rejection, and reconnect REST recovery.
- No acknowledgement on history prefetch, loading/error states, hidden tabs, off-screen chat,
  or scrolling away from the end. Successfully loaded, reconciled, rendered, visible history
  can be acknowledged. New messages outside the viewed boundary must stay unread.
- Simulate GET-history and POST-read failures: show safe Retry, retain authoritative unread
  state, and recover without request loops. Test navigation/unmount/logout abort cleanup,
  token refresh, cache isolation, and no additional WebSocket or polling connections.

## Regression and limitations

- Run existing backend authentication, tenant, Ticket, pagination/search, and WebSocket tests;
  run frontend tests, typecheck, lint, production build, and real browser integration checks.
  Existing automated coverage is recorded above; complete the remaining real-browser checks.
- Current history retrieval is unpaginated; reconciliation transfers full authorized history
  for a newly observed batch. Measure large-history behavior and unread query efficiency.
- WebSocket delivery remains best-effort and single-process; REST/refetch is authoritative.
  The server validates authorization and observed-message scope, not actual human attention.
- Do not treat this checklist as executed evidence or apply migrations to valuable data for
  verification. Record actual commands, failures, and NOT RUN items in the final testing phase.
