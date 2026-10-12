# Logout and account-switch security verification

## Scope and findings

Review date: 2026-10-12. No database reset, backend contract change, or UI redesign.

Confirmed frontend races: logout retained local authentication until its network request finished;
late authenticated responses could reach the next session; an old refresh failure could clear a
new session; overlapping login/logout requests could reorder refresh-cookie writes. Chat cleanup
also needed synchronous token-change handling rather than relying only on React effect cleanup.

Fixes use session-generation checks, serialized login/logout cookie writes, immediate local logout,
guarded auth-provider completions, and synchronous chat cleanup. Existing ticket-list subscription
guards are retained and covered with additional delayed-callback regression tests.

## Executed evidence

From `frontend/`:

```sh
npm test && npm run typecheck && npm run lint && npm run build
```

- PASS: 41 frontend tests, 0 failures or skips; TypeScript, ESLint, production build.
- New coverage: 11 API/session tests and 3 ticket-list lifecycle tests. Includes delayed success,
  delayed 401/body parsing, old refresh completion/failure, rapid login, cookie-write ordering,
  failed logout, late mutation cache writes, stale list callbacks, reconnect refresh and invalidation.
- Initial targeted reproduction against the original API implementation: 1 passed, 5 failed.
  Final results above include fixes. Mock HTTP/socket tests are not browser E2E evidence.

From `backend/`:

```sh
.venv/bin/pytest -q tests/test_auth.py tests/test_websocket_manager.py tests/test_login_rate_limit.py
```

- PASS: 38 tests; one Starlette/httpx deprecation warning. Not PostgreSQL integration proof.

Runtime probes:

```sh
docker compose ps --format json
curl --max-time 3 -s -o /dev/null -w 'Backend HTTP %{http_code}\n' http://127.0.0.1:8000/health
curl --max-time 3 -s -o /dev/null -w 'Frontend HTTP %{http_code}\n' http://127.0.0.1:3000/login
```

- FAIL (environment): Docker daemon unavailable; both HTTP probes returned 000 (connection failed).
  Probes were repeated with approved sandbox escalation; services remained unavailable.
- NOT RUN: real browser account-switch E2E and PostgreSQL integration. Browser tooling alone cannot
  verify the workflow without running application services.

## Pending real-browser verification

Use local demo/test data only. Start Docker, then run the existing commands from the repository root:

```sh
docker compose up --build -d
docker compose --profile test run --build --rm tests
```

The test profile uses its separate test database; do not delete demo volumes. These commands were
not executed in this review. For the default local demo, open `http://localhost:3000/login` and use
the documented demo-only password `HelpdeskDemo2026!`.

1. Browser profile A: log in as `agent@northstar.helpdeskmini.dev`, open `/tickets`.
2. Independent profile B: log in as `customer1@northstar.helpdeskmini.dev`, send a uniquely labeled
   message to an owned ticket. A must show activity/unread updates without refresh.
3. In the same tab/profile A, logout and login as `agent@orbit.helpdeskmini.dev`.
4. B creates a ticket and sends another Northstar message. A must show no Northstar notice, ticket,
   unread count, message, or stale response. Inspect Network: old sockets closed, one active Orbit
   list subscription. A's access to the saved Northstar ticket must return 404.
5. Independent profile C: login as `customer1@orbit.helpdeskmini.dev`, send a message to an Orbit
   ticket. A must receive its own activity/unread update; open the ticket and verify live chat.
6. Repeat steps 1–5 with slow-network throttling and pending list/history requests, a pending token
   refresh, a visible notification, and rapid logout/login. Delayed Northstar work must not alter
   Orbit state. Reload A and confirm Orbit session/data, then check navigation closes chat sockets.
7. Do not export headers, JWTs, cookies, or unredacted network captures as evidence. Record only
   account labels, expected/actual behavior and sanitized status codes.

## Remaining limitations

- End-to-end tenant isolation and Orbit live-update continuity remain pending the browser run above.
- Stateless logout does not revoke copied access/refresh JWTs; existing expiry rules still apply.
- Serialization is tab-local, not cross-tab account coordination. Failed network logout cannot
  guarantee server cookie expiration. A stalled cookie-writing request delays subsequent login.
- Existing in-memory WebSocket delivery still requires a single backend worker.
