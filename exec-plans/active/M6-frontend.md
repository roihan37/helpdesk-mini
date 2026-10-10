# M6 - Next.js Frontend

## Status

**PLANNED — AWAITING PHASE 2 APPROVAL**

Phase 1 planning date: 2026-10-10

This document is the implementation plan for M6 only. No frontend implementation, backend
contract change, commit, or push is authorized by this phase.

The supplied Phase 1 brief ends mid-sentence after requiring tasks to be organized in dependency
order. The complete preceding requirements are actionable; the ordered tasks below use those
requirements without inventing additional product scope.

## 1. Objective

Deliver the six required responsive Next.js pages and their shared application shell, authentication
lifecycle, REST integration, and real-time Ticket conversation experience. The frontend must expose
only role-appropriate actions while treating the FastAPI backend as the authority for authentication,
authorization, tenant isolation, state transitions, and message persistence.

M6 succeeds when the required Customer, Agent, and Admin workflows operate against the existing M2
through M5 contracts, including two-browser real-time chat, without persisting JWTs in browser
storage or adding unsupported product features.

## 2. Prerequisite and Repository Review

### Milestone readiness

- `exec-plans/completed/M5-websocket-chat.md` is present and marks M5 **COMPLETE**.
- Its Phase 4 record reports 16 PASS, 0 FAIL, and 0 NOT RUN acceptance criteria and 137 passing
  backend tests.
- No critical M5 blocker is recorded.
- M5 explicitly hands off REST-history-first loading, one Ticket socket per mounted detail view,
  ID-based message deduplication, post-reconnect reconciliation, in-memory access tokens, exact
  Origin handling, and text-only message rendering to M6.

### Existing frontend

- Next.js 16.4 App Router, React 19.3, strict TypeScript, and Tailwind CSS 4 are installed.
- Routes currently consist only of `src/app/layout.tsx` and a static M0 `src/app/page.tsx`.
- `globals.css` contains only the Tailwind import and minimal light/dark scaffold styles.
- There are no providers, feature modules, API client, authentication state, reusable components,
  required product routes, or frontend tests.
- TanStack Query is selected by `ARCHITECTURE.md` but is not currently a direct dependency.
- No component framework, icon library, form library, state library, or Geist/Inter font asset is a
  direct dependency.
- Existing scripts are `dev`, `build`, `start`, `lint`, and `typecheck`.
- `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` already exist in `.env.example` and the ignored
  local frontend environment file.

### Existing backend contract

- REST uses a `{ "data": ... }` success envelope and a structured `{ "error": ... }` failure
  envelope.
- Browser access tokens use the Authorization header and remain in memory. The refresh token is an
  HttpOnly, `SameSite=Lax`, `/auth/refresh` cookie; refresh calls require credentials.
- Public auth endpoints are business registration, login, and refresh. `/auth/me` resolves the
  authenticated user and business. There is no logout or token-revocation endpoint.
- Admin-only `/users` supports list and create for Agent or Customer users.
- Ticket list/detail/create/update and message-history endpoints are implemented with role, tenant,
  ownership, assignment, and transition enforcement.
- WebSocket connections use `/ws/tickets/{ticket_id}?token=<access-token>` and emit
  `message.created`, `ticket.status_changed`, and structured `error` events.

## 3. Scope

### In scope

- `/login`
- `/register` for a Business and its initial Admin
- `/tickets`
- `/tickets/new` for Customers
- `/tickets/[id]`
- `/admin/users` for Admins
- Auth bootstrap, one-time refresh-and-retry, protected page handling, and role-aware navigation
- Typed REST client and response/error normalization
- TanStack Query server-state setup
- Native WebSocket lifecycle for Ticket rooms
- Responsive application shell and the design system in `docs/FRONTEND_UIUX.md`
- Loading, empty, error, validation, pending, unauthorized, disconnected, and closed states
- Accessibility, keyboard, responsive, lint, type, build, and browser workflow verification

### Out of scope

- Backend or API-contract changes, including a fabricated logout endpoint
- M7 seed/demo work or additional backend test scope
- Analytics, dashboards, reports, billing, notification centers, settings, search, or pagination
- User edit/delete/invite/password reset
- Attachments, typing indicators, read receipts, presence, or unread counts
- Ticket actions not defined by the contract, including customer close or agent assignment to others
- Redux, a large UI framework, shadcn installation, an HTTP client library, or a form framework
- Multi-process WebSocket infrastructure

## 4. Architecture Decisions

### 4.1 Dependencies

Add `@tanstack/react-query` as the only planned runtime dependency because it is an explicit
architecture decision and provides request caching, invalidation, and mutation state. Use native
`fetch`, native `WebSocket`, semantic HTML, and small local components for everything else. Do not
import transitive packages as if they were direct dependencies.

No custom font asset is installed. Use a stable system sans-serif stack preferring locally available
Geist or Inter names, with `ui-sans-serif` and platform fallbacks; do not add a font package or a
runtime remote-font request solely for styling.

### 4.2 Rendering and state boundaries

- App Router files compose routes and layouts; interactive forms, auth, queries, and sockets live in
  focused Client Components.
- TanStack Query owns remote server state. Local component state owns form drafts, disclosures,
  navigation state, and transient connection state.
- A small Auth provider owns only the in-memory access token, current user, bootstrap state, and
  login/refresh helpers. Do not duplicate user or ticket collections into another global store.
- REST and WebSocket payload types mirror the documented contract; SQLAlchemy entities are never
  treated as frontend contracts.

### 4.3 Planned source layout

Create directories only as implementation requires:

```text
frontend/src/
├── app/
│   ├── (auth)/login/page.tsx
│   ├── (auth)/register/page.tsx
│   ├── (app)/layout.tsx
│   ├── (app)/tickets/page.tsx
│   ├── (app)/tickets/new/page.tsx
│   ├── (app)/tickets/[id]/page.tsx
│   ├── (app)/admin/users/page.tsx
│   ├── layout.tsx
│   └── page.tsx
├── components/          # shared shell and small UI primitives
├── features/auth/       # auth provider, guard, forms
├── features/tickets/    # list, forms, detail, actions, chat
├── features/users/      # Admin user list/create flow
├── hooks/               # reusable lifecycle hooks only
├── lib/                 # env, API client, query client, formatting
└── types/               # API and WebSocket contract types
```

Route groups do not change public URLs. Prefer feature-local files until a component is reused.

### 4.4 Authentication lifecycle

1. On first client mount, auth state is `bootstrapping`; protected content is not rendered.
2. Attempt `POST /auth/refresh` with `credentials: "include"`, retain only the returned access token
   in memory, then call `/auth/me`.
3. A successful login retains `data.access_token`, deliberately discards the response-body refresh
   token, resolves `/auth/me`, and navigates to `/tickets`.
4. The API client adds the current access token. On an eligible 401, all concurrent requests share
   one refresh promise, then each retries at most once. Auth and refresh requests are never placed in
   a retry loop.
5. Failed refresh clears in-memory auth, clears protected query data, closes active sockets, and
   redirects protected routes to `/login` with a return path that is local and validated.
6. Public auth pages redirect an already authenticated user to `/tickets` after bootstrap.
7. Role guards improve presentation only. A forbidden backend response remains authoritative.

Because the HttpOnly refresh cookie cannot be cleared by frontend JavaScript and the API exposes no
logout endpoint, M6 must not show a misleading Sign out action. The Account menu displays current
identity and business only; true logout remains an explicitly documented backend limitation.

### 4.5 API and error handling

- Validate both public environment variables at startup/use and produce a clear development error
  when missing. Remove trailing slashes before building paths.
- Parse success and error envelopes centrally. Preserve HTTP status, backend code, message, and
  validation details in a typed frontend error.
- Map 401 to auth recovery; 403 to a permission message; 404 to a non-disclosing not-found state;
  409 to an inline conflict/state message plus relevant query refresh; 422 to field or form errors;
  and network/5xx failures to retryable page or section states.
- Encode path and query values, never trust IDs from the route, and never expose `business_id` as an
  editable field.
- Use `credentials: "include"` for login, registration if harmlessly consistent, and especially
  refresh. Authorization remains bearer-based for protected REST calls.

### 4.6 Query strategy

- Stable keys: `['me']`, `['tickets', { status }]`, `['ticket', id]`,
  `['ticket-messages', id]`, and `['users']`.
- Do not query protected data before auth bootstrap succeeds.
- Treat list filters as URL search parameters so refresh/back navigation preserves them.
- After successful mutations, update exact known records from the server response and invalidate the
  smallest affected queries.
- Avoid aggressive automatic retries for 4xx errors. Permit limited retry for transient network/5xx
  reads; mutations require explicit user retry.

### 4.7 WebSocket lifecycle

1. Load authorized Ticket detail and persisted history over REST.
2. Open one socket only after both auth and history are ready.
3. On open, refetch history once to close the REST-to-socket race, then merge by message `id` and
   order by `(created_at, id)`.
4. Add `message.created` only after the server event confirms persistence. Never render an optimistic
   success message.
5. Apply `ticket.status_changed` to Ticket detail/list caches and composer/action availability.
6. Show `connecting`, `connected`, `reconnecting`, or `offline` quietly. Disable send unless the
   socket is open, the role can send, and the Ticket is not closed.
7. Reconnect unexpected closures with bounded exponential delays while the page, user, Ticket, and
   token remain valid. Refetch detail/history after reconnect. Do not reconnect 1008 authorization
   failures blindly; refresh authentication once where appropriate, then require navigation/login.
8. Close the socket and cancel reconnect timers on unmount, Ticket change, auth loss, or navigation.

Message bodies are rendered as text. The token is necessarily present in the WebSocket query string
under the approved M5 contract; production must use WSS and infrastructure must redact query strings.

## 5. Authorization and Role Matrix

| Capability | Admin | Agent | Customer |
|---|---:|---:|---:|
| View Ticket list | Business-wide | Business-wide | Own only |
| Create Ticket | No | No | Yes |
| View authorized chat | Yes | Yes | Own only |
| Send chat message | No | Yes | Own only |
| Assign Agent | Any permitted same-business Agent | Self only | No |
| Advance normal status | Yes | Yes | No |
| Reopen resolved Ticket | No | No | Own only |
| List/create users | Yes | No | No |

The UI derives visibility from `/auth/me`, but every operation still handles server denial. Cross-
tenant and same-business cross-customer 404 responses use one generic inaccessible/not-found view.

## 6. Ordered Implementation Tasks

### M6-01 — Establish frontend foundations

**Depends on:** M5 complete.

- Add `@tanstack/react-query` and update the lockfile.
- Add the root Query provider, environment validation, global design tokens, base typography, focus
  styles, and minimal reusable primitives (Button, Input, Select, Badge, Alert, Skeleton).
- Replace the M0 root placeholder with deterministic routing to login or the authenticated workspace.

**Acceptance:** App boots with one Query client, no large UI dependency, tokens match the UI/UX
specification, and environment failures are explicit.

### M6-02 — Implement typed transport and auth lifecycle

**Depends on:** M6-01.

- Define REST/WebSocket types and strict envelope/error parsing.
- Implement bearer requests, credentialed refresh, single-flight one-retry handling, Auth provider,
  `/me` loading, and protected/public/role route guards.
- Ensure access and response-body refresh tokens never enter Web Storage, URLs, logs, or rendered UI.

**Acceptance:** Reload restores a valid cookie session; invalid/expired sessions reach login; refresh
storms and infinite retry loops are prevented; role checks never replace backend checks.

### M6-03 — Build responsive authenticated shell

**Depends on:** M6-02.

- Implement desktop sidebar/topbar, tablet collapse, mobile drawer, skip link, current-page state,
  role-specific navigation, business/user context, and Account identity menu.
- Manage drawer focus, Escape close, focus return, and body overflow.

**Acceptance:** All roles see only documented navigation; keyboard and mobile navigation work; no
unsupported settings or fake logout action appears.

### M6-04 — Implement login and business registration

**Depends on:** M6-02.

- Build `/login` and `/register` using contract field names and constraints.
- Include password visibility controls, inline accessible validation, pending states, duplicate
  conflict handling, and success feedback. Registration returns to login and does not assume a
  session was issued.

**Acceptance:** Login establishes memory-only auth; registration creates a Business/Admin payload;
errors retain safe field values and never reveal/store passwords.

### M6-05 — Implement Ticket list workspace

**Depends on:** M6-03.

- Query `/tickets` with optional status, URL-backed filter, desktop table, and mobile compact rows.
- Show only subject, status, priority, assignee, and latest activity supplied by the API.
- Add Customer-only New Ticket action and complete loading/empty/error/refetch states.

**Acceptance:** Role-scoped results and latest-activity order are displayed as returned; status
filter is preserved; there is no client claim of tenant security, search, analytics, or pagination.

### M6-06 — Implement Customer Ticket creation

**Depends on:** M6-03 and M6-05.

- Build `/tickets/new` with subject, category, priority, and initial message.
- Enforce documented lengths, show field/API errors, guard unsent double submission, and navigate to
  the server-created Ticket detail after success.

**Acceptance:** Customer creation works once per submit; other roles cannot enter through normal UI;
the first message is supplied in the atomic create request.

### M6-07 — Implement Ticket detail and persisted history

**Depends on:** M6-03 and M6-05.

- Build the responsive Ticket header, chronological conversation, details disclosure/panel, message
  identities, accessible timestamps, empty/error/loading states, and generic 404 state.
- Keep Admin chat read-only and closed Ticket history readable.

**Acceptance:** Authorized users see contract fields only; Customer ownership and tenant boundaries
are not inferred client-side; arbitrary message text is safely rendered.

### M6-08 — Integrate real-time chat

**Depends on:** M6-02 and M6-07.

- Implement the lifecycle in Section 4.7 with native WebSocket.
- Add confirmed-send behavior, ID deduplication, deterministic ordering, status event updates,
  reconnect reconciliation, authentication expiry handling, and cleanup.

**Acceptance:** Two authorized browser clients exchange confirmed messages in real time; refresh
shows persistence; rooms do not leak; disconnected/closed/Admin clients cannot send from the UI.

### M6-09 — Implement Ticket actions

**Depends on:** M6-07 and M6-08.

- Derive only valid next status actions from current status and role.
- Add Agent self-assignment, Admin assignment using Admin-authorized `/users` Agent records, and
  Customer reopen for an owned resolved Ticket.
- Disable duplicate actions, handle 409 stale-state responses by refetching, and rely on the server
  for final authorization.

**Acceptance:** The UI never offers invalid transitions or unassignment; committed updates appear
locally and reach another connected viewer through M5 status events.

### M6-10 — Implement Admin Team management

**Depends on:** M6-03.

- Build `/admin/users` list and accessible create-user dialog/form.
- Permit Agent or Customer creation only, with documented name/email/password validation and safe
  pending/error/success behavior.

**Acceptance:** Admin can list and create own-business users; other roles are guarded and server 403
is handled; password hashes and unsupported actions never appear.

### M6-11 — Accessibility, responsiveness, and resilience pass

**Depends on:** M6-04 through M6-10.

- Verify keyboard order, labels, descriptions, error announcements, focus restoration, contrast,
  responsive breakpoints, long content, timezone formatting, mobile keyboard/composer behavior, and
  reduced-motion preference.
- Exercise 401/403/404/409/422/network/5xx and pending states for every page.

**Acceptance:** Required flows are usable at 320 CSS pixels and desktop width without page-level
horizontal overflow; all actions have visible focus and non-color status labels.

### M6-12 — Final M6 verification and documentation

**Depends on:** M6-11.

- Run install reproducibility, lint, typecheck, and production build.
- Run the browser role/security/real-time matrix against disposable demo data and a single-worker
  backend; record exact evidence and unexecuted checks.
- Update README only with commands and frontend behavior actually verified.
- Mark and move this plan to `completed/` only after a separate approved final review confirms all
  mandatory criteria.

**Acceptance:** Mandatory checks pass or exact blockers remain documented; no M7 work, automatic
commit, or push occurs.

## 7. Page and State Acceptance Matrix

| Route | Loading | Empty/success | Validation/pending | API/auth failure | Mobile |
|---|---|---|---|---|---|
| `/login` | Auth bootstrap indicator | Focused form | Inline fields; disabled submit | Generic credential/network message | Single column |
| `/register` | Auth bootstrap indicator | Business/Admin form; success route | Inline fields; disabled submit | Duplicate slug/email and server errors | Single column |
| `/tickets` | Row skeletons | Role-specific empty copy/table or list | Filter pending without blanking useful data | Retry; auth recovery | Stacked rows |
| `/tickets/new` | Guard indicator | Form | Length errors; disabled submit | Inline 403/409/422/network | Full-width controls |
| `/tickets/[id]` | Detail/history skeletons | Conversation and details | Disabled pending actions/composer | Generic 404; reconnect/error banners | Conversation first; details disclosure |
| `/admin/users` | Row skeletons | Empty/team table | Inline create form; disabled submit | 403/409/422/retry | Compact rows and full-screen-width dialog |

Every asynchronous status uses visible text or an accessible live region; color or spinner alone is
not sufficient.

## 8. Security Considerations

- Never store access or refresh tokens in localStorage, sessionStorage, IndexedDB, or readable
  cookies. Deliberately discard the login response's refresh-token string.
- Never render tokens, passwords, backend details, raw HTML, or stack traces.
- Use same-origin production HTTPS/WSS where possible; explicitly configure credentialed CORS and
  permitted WebSocket Origin. Never use wildcard credentialed origins.
- Treat route roles, hidden controls, UUIDs, and cached data as untrusted presentation state.
- Clear protected query caches on auth loss so one user cannot see the preceding user's data in the
  same browser process.
- Use generic 404 copy for inaccessible Tickets and do not distinguish cross-tenant ownership.
- Escape all user content through normal React text rendering; do not use `dangerouslySetInnerHTML`.
- Avoid including sensitive data in client logs, analytics, error telemetry, or test screenshots.
- Verify dependency changes and do not accept breaking automatic audit fixes without review.

## 9. Verification Plan

### Static and build checks

Run from `frontend/` after implementation:

```bash
npm ci
npm run lint
npm run typecheck
npm run build
```

Run from the repository root:

```bash
git diff --check
git status --short
```

### Browser integration matrix

Use the documented environment and disposable demo/test data. Run the FastAPI backend with one
worker because M5's connection manager is process-local.

1. Register a Business/Admin; verify duplicate and invalid inputs.
2. Login/reload with Admin, Agent, and Customer; verify cookie refresh and role navigation.
3. Verify expired/invalid authentication redirects without exposing cached protected data.
4. Admin lists/creates Agent and Customer; non-Admin cannot use the workflow.
5. Customer creates a Ticket with first message and sees it in own list/detail.
6. Verify status filter and latest activity rendering for each role.
7. In two browsers, Customer and Agent open one Ticket, exchange messages, observe sender/role/time,
   reload, and confirm persisted history without duplicates.
8. Confirm Admin is read-only, Agent can self-assign/change allowed status, Admin can assign an Agent,
   and Customer can only reopen own resolved Ticket.
9. Confirm status changes appear in the second browser only after committed HTTP success.
10. Confirm closed Ticket history remains visible and message submission is unavailable.
11. Confirm a Business A session receives a generic not-found result for a Business B Ticket URL;
    confirm one Customer cannot open another Customer's Ticket.
12. Interrupt/restart connectivity; verify send is disabled, reconnection refetches missed history,
    unauthorized close does not loop, and navigation leaves no active old-room socket.
13. Exercise 320px mobile, tablet, and desktop layouts with keyboard-only navigation.

Do not report any item as PASS without executing it. Record failures and NOT RUN items exactly.

## 10. M6 Acceptance Criteria

1. All six required routes exist and match their documented access model.
2. Access tokens remain memory-only and the HttpOnly refresh-cookie strategy is preserved.
3. Refresh bootstrap and a single retry recover valid sessions without loops or request storms.
4. Protected routes redirect invalid sessions; role-aware UI never substitutes for backend checks.
5. Admin, Agent, and Customer navigation and actions match the permission matrix.
6. Ticket list supports status filtering and displays all required available fields responsively.
7. Customer Ticket creation sends the atomic first-message payload.
8. Ticket detail loads persisted history before opening one authorized Ticket socket.
9. Server-confirmed messages and committed status changes update two authorized clients in real time.
10. Message IDs are deduplicated; reconnect refetches history; old sockets/timers are cleaned up.
11. Admin and closed Tickets cannot send; Agent and owning Customer can send when permitted.
12. Assignment and state controls expose only backend-supported operations and recover from conflicts.
13. Admin can list/create Agent and Customer users without unsupported management features.
14. 401, 403, 404, 409, 422, network, loading, empty, pending, and mobile states are handled.
15. User content is rendered as text, focus is visible, controls are labelled, and layouts remain
    usable without page overflow at 320px.
16. Lint, strict typecheck, production build, and the mandatory browser matrix pass, or exact
    blockers are recorded with no false success claim.

## 11. Known Risks and Mitigations

| Risk | Mitigation / required evidence |
|---|---|
| No backend logout/cookie-clear endpoint | Do not present fake logout; document limitation for later approved contract work. |
| Access token is lost on reload | Bootstrap with credentialed refresh before protected queries render. |
| Concurrent 401s cause refresh storms | Share one refresh promise and retry each request at most once. |
| REST history/socket-open race loses a message | Refetch history after socket opens and merge by ID/order. |
| Duplicate events/reconnects duplicate UI | Deduplicate on server message UUID and sort deterministically. |
| Query-string WebSocket token leaks through infrastructure logs | Require WSS in production and query-string redaction; never client-log socket URLs. |
| In-memory M5 rooms do not cross workers | Verify and document single-worker backend execution. |
| Socket auth becomes stale while idle | Handle 1008/action errors, refresh once where valid, refetch, and stop blind reconnects. |
| Admin assignment needs Agent choices | Use Admin-only `/users` data and filter `role === "agent"`; Agent sees only self-assign. |
| No frontend test framework is installed | Do not add one casually in M6; require compile checks and a recorded browser matrix. Reassess focused automation in M7. |
| Remote font loading harms reproducibility/privacy | Use the local system font stack; no remote runtime font request. |
| Phase 1 source brief is truncated | Treat only its complete explicit requirements as scope; request review of this plan before implementation. |

## 12. Phase 1 Record

### Files created

- `exec-plans/active/M6-frontend.md`
- `docs/FRONTEND_UIUX.md`

### Phase 1 validation

- **PASS** — `rg -n '^### M6-[0-9]{2}' exec-plans/active/M6-frontend.md` found the ordered
  tasks M6-01 through M6-12.
- **PASS** — route coverage search found `/login`, `/register`, `/tickets`, `/tickets/new`,
  `/tickets/[id]`, and `/admin/users` in both planning artifacts.
- **PASS** — whitespace validation found no trailing whitespace after cleanup.
- **PASS** — `git status --short --untracked-files=all` showed only the two Phase 1 documents as
  new files.
- **NOT RUN** — frontend lint, typecheck, build, and browser integration. This is a planning-only
  phase and no frontend source or dependency file was changed.

## 13. Approval Gate

Stop after Phase 1. Phase 2 may begin only after this plan and `docs/FRONTEND_UIUX.md` are reviewed
and explicitly approved. Do not proceed automatically to implementation or M7.
