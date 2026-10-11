# B5 — Deferred Unread Verification

Status: **NOT RUN — implementation-only phase**. No automated tests were created or changed.
No pytest, frontend tests, lint, typecheck, build, E2E, or migration execution was performed.
Static review is not integration evidence. Run the following in the final testing phase using
isolated disposable PostgreSQL data and independent authenticated browser sessions.

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
  receive no read receipt and retain independent counts. Verify both business and Customer
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
  Add focused automated regression coverage only when the final testing phase is authorized.
- Current history retrieval is unpaginated; reconciliation transfers full authorized history
  for a newly observed batch. Measure large-history behavior and unread query efficiency.
- WebSocket delivery remains best-effort and single-process; REST/refetch is authoritative.
  The server validates authorization and observed-message scope, not actual human attention.
- Do not treat this checklist as executed evidence or apply migrations to valuable data for
  verification. Record actual commands, failures, and NOT RUN items in the final testing phase.
