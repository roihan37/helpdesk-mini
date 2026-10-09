# HelpDesk Mini - Security Specification

**Project:** HelpDesk Mini  
**Document:** `docs/SECURITY.md`  
**Version:** 1.0  
**Status:** Security Baseline  
**Architecture:** Modular Monolith  
**Backend:** FastAPI + PostgreSQL  
**Authentication:** JWT Access + Refresh Token

---

## 1. Purpose

This document defines the security requirements, authorization policies, trust boundaries, implementation rules, and verification procedures for HelpDesk Mini.

Its primary purpose is to prevent:

1. Cross-business data exposure.
2. Unauthorized resource access.
3. Authentication bypass.
4. Role-based privilege escalation.
5. Unauthorized WebSocket communication.
6. Password and credential exposure.
7. Invalid ticket operations.

Security controls must be enforced by the backend.

Frontend permission checks are intended for user experience and must never be treated as security boundaries.

### 1.1 Security Principles

All implementation must follow these principles:

- Deny access by default.
- Authenticate before authorizing.
- Apply tenant isolation to every protected resource.
- Validate role and resource ownership.
- Never trust client-controlled identity fields.
- Store passwords using secure hashing.
- Validate JWT signatures, expiration, and token type.
- Never expose protected information through error responses.
- Persist business changes before broadcasting real-time events.
- Verify security-sensitive behavior using automated tests.

### 1.2 Requirement Classification

**MUST**

Mandatory security requirement from the original SVO Connect assessment.

**DECISION**

Additional implementation decision selected for HelpDesk Mini.

**RECOMMENDED**

Security practice that improves implementation quality but is not explicitly required by the assessment.

---

## 2. Security Priorities

| ID | Security Area | Priority |
|---|---|---|
| SEC-001 | Multi-tenant isolation | Critical |
| SEC-002 | Customer ticket ownership | Critical |
| SEC-003 | Password hashing | Critical |
| SEC-004 | JWT validation | Critical |
| SEC-005 | Role-based authorization | Critical |
| SEC-006 | WebSocket authentication | Critical |
| SEC-007 | WebSocket ticket authorization | Critical |
| SEC-008 | Secret management | Critical |
| SEC-009 | Database integrity | High |
| SEC-010 | Ticket state validation | High |
| SEC-011 | Input validation | High |
| SEC-012 | Secure token handling | High |
| SEC-013 | Security logging | Recommended |
| SEC-014 | Login rate limiting | Bonus |

Critical requirements must be verified before submission.

---

## 3. Security Architecture

### 3.1 Trust Boundaries

The system contains three primary layers.

```text
UNTRUSTED CLIENT
Next.js Browser Application
        |
        | HTTPS / WSS
        v
TRUSTED APPLICATION BOUNDARY
FastAPI Backend
        |
        | Authentication
        | JWT Validation
        | Role Authorization
        | Tenant Isolation
        | Resource Ownership
        | Business Rules
        |
        v
PERSISTENCE LAYER
PostgreSQL
        |
        | businesses
        | users
        | tickets
        | messages
```

All input originating from the client is untrusted.

This includes:

- Request body.
- Query parameters.
- Path parameters.
- HTTP headers.
- WebSocket payloads.
- Client-supplied identifiers.

JWT claims become usable only after successful cryptographic validation.

Even after JWT validation, resource authorization must be independently enforced.

### 3.2 Protected Data

Security-sensitive data includes:

- Password hashes.
- JWT access and refresh tokens.
- Authentication secrets.
- Business membership.
- User identities and email addresses.
- Ticket details.
- Ticket messages.
- Customer information.

Protected information must never be exposed to unauthorized businesses or users.

---

## 4. Authentication Security

### 4.1 Authentication Method

**MUST**

Use JWT-based authentication with:

- Access token.
- Refresh token.

Users authenticate with:

- Email.
- Password.

The backend must validate user credentials before issuing tokens.

### 4.2 Password Hashing

**MUST**

Passwords must never be stored in plaintext.

**DECISION**

Use Argon2 through a maintained Python password-hashing library.

Password registration flow:

```text
Receive password
       |
       v
Validate input
       |
       v
Hash with Argon2
       |
       v
Store password_hash
```

Login verification:

```text
Receive credentials
       |
       v
Find user by email
       |
       v
Verify password against hash
       |
    +--+--+
    |     |
  Valid Invalid
    |     |
    v     v
  JWT    401
```

Security rules:

- Never store plaintext passwords.
- Never return password hashes.
- Never include passwords in application logs.
- Never use reversible encryption as password hashing.
- Never compare password hashes using plaintext string comparisons.
- Use the password hashing library's verification function.

### 4.3 Login Error Handling

**DECISION**

Invalid login attempts return a generic error.

Example:

```json
{
  "error": {
    "code": "AUTH_INVALID_CREDENTIALS",
    "message": "Invalid email or password.",
    "details": null
  }
}
```

Do not disclose whether the email exists.

Return HTTP 401.

---

## 5. JWT Security

### 5.1 JWT Signing

**DECISION**

Use HS256 with a strong secret supplied through environment variables.

Required configuration:

- `JWT_SECRET`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`

Never hardcode JWT secrets.

JWT verification must explicitly allow only the configured, approved algorithm.

Do not trust the algorithm declared in an unverified JWT header.

Reject unsigned tokens and unexpected signing algorithms.

### 5.2 Access Token

**DECISION**

Access-token expiration:

15 minutes.

Suggested claims:

```json
{
  "sub": "user-uuid",
  "business_id": "business-uuid",
  "role": "agent",
  "type": "access",
  "iat": 1791540000,
  "exp": 1791540900
}
```

Required validation:

1. Valid signature.
2. Expected algorithm.
3. Valid expiration.
4. Valid user identifier.
5. Correct token type.
6. Existing authenticated user.

The user's current role and business membership must be derived from trusted server-side user information.

Do not authorize resources solely using unverified or stale role claims.

### 5.3 Refresh Token

**DECISION**

Refresh-token expiration:

7 days.

Refresh tokens must:

- Use a distinct token type.
- Be cryptographically validated.
- Be checked for expiration.
- Reference an existing user.
- Never authorize protected REST operations.
- Never authorize WebSocket connections.

Example:

```json
{
  "sub": "user-uuid",
  "type": "refresh",
  "iat": 1791540000,
  "exp": 1792144800
}
```

### 5.4 Token Type Isolation

A refresh token must not be accepted for:

```text
GET /auth/me
GET /users
POST /users
GET /tickets
POST /tickets
GET /tickets/{id}
PATCH /tickets/{id}
GET /tickets/{id}/messages
WS /ws/tickets/{id}
```

An access token must not be accepted as a refresh token.

Reject incorrect token types with HTTP 401 for REST requests.

### 5.5 Token Validation Flow

```text
Receive JWT
     |
     v
Verify signature
     |
     v
Verify expiration
     |
     v
Verify token type
     |
     v
Resolve user from DB
     |
     v
Build authenticated context
     |
     v
Apply role authorization
     |
     v
Apply tenant authorization
     |
     v
Allow operation
```

Never skip tenant authorization after successful authentication.

---

## 6. Frontend Token Security

### 6.1 Access Token Storage

**DECISION**

Store access tokens in frontend application memory.

Do not persist access tokens in:

- localStorage.
- sessionStorage.
- Non-HttpOnly cookies.

On browser refresh, the frontend may obtain a new access token using the refresh endpoint.

### 6.2 Refresh Token Storage

**DECISION**

Login returns access and refresh tokens in JSON, as required by the assessment.

For browser sessions:

- Backend additionally stores the refresh token in an HttpOnly cookie.
- Frontend does not persist the returned refresh-token body.
- Browser refresh requests include credentials.
- Backend reads the refresh token from the cookie.

Cookie configuration:

```text
HttpOnly = true
Secure = true in HTTPS environments
Path = /auth/refresh
SameSite = appropriate to deployment
```

Use `SameSite=Lax` when the deployment's same-site architecture permits it.

For genuinely cross-site cookie usage, `SameSite=None` requires `Secure` and appropriate CSRF protection.

### 6.3 CSRF Protection

**DECISION**

Because refresh authentication uses cookies, the backend must protect cookie-authenticated requests against cross-site request forgery.

For browser requests:

- Validate allowed origins.
- Reject requests from disallowed origins.
- Configure SameSite appropriately.
- Do not rely on CORS alone as CSRF protection.
- Apply an appropriate CSRF strategy for cross-site cookie configurations.

### 6.4 CORS Configuration

**MUST for selected cross-origin architecture**

Use an explicit list of authorized frontend origins.

Example development origin:

```text
http://localhost:3000
```

If credentials are enabled:

- Do not use wildcard origins.
- Permit only required methods and headers.
- Enable credentials only for trusted origins.

### 6.5 Token Expiration Handling

When an authenticated REST request returns 401:

1. Attempt token refresh if appropriate.
2. If refresh succeeds, retry the original request once.
3. If refresh fails, clear frontend authentication state.
4. Redirect to `/login`.

Avoid infinite refresh loops.

### 6.6 Refresh Token Limitations

**DECISION**

The MVP uses stateless JWT refresh tokens without server-side session storage.

Consequences:

- Immediate token revocation is not guaranteed.
- A copied refresh token may remain usable until expiration.
- Clearing a browser cookie does not invalidate previously copied tokens.
- Refresh-token rotation is not implemented initially.

These limitations must be disclosed in README.

Do not claim immediate server-side logout revocation unless it is implemented and verified.

---

## 7. Role-Based Access Control

### 7.1 Supported Roles

The application supports exactly three roles:

```text
admin
agent
customer
```

Each user has exactly one role and belongs to exactly one business.

### 7.2 Authorization Matrix

| Operation | Admin | Agent | Customer |
|---|---|---|---|
| Manage business users | Allow | Deny | Deny |
| View all business tickets | Allow | Allow | Deny |
| Create ticket | Deny | Deny | Allow |
| View own ticket | Allow | Allow | Allow |
| Assign agent | Allow | Self only | Deny |
| Change normal ticket status | Allow | Allow | Deny |
| Reopen resolved ticket | Deny | Deny | Owner only |
| View authorized chat | Allow | Allow | Owner only |
| Send chat messages | Deny* | Allow | Owner only |

*DECISION: Admin chat access is read-only. The assessment does not explicitly require Admin message sending.*

### 7.3 Authorization Enforcement

Authorization must be enforced in FastAPI.

Recommended implementation:

- Authentication dependencies identify users.
- Role dependencies reject unauthorized roles.
- Resource authorization verifies business and ownership.
- Service-level operations enforce business rules.

Do not rely solely on route-level role validation for resource authorization.

### 7.4 Permission Validation Order

For protected resource operations:

```text
Authenticate user
       |
       v
Resolve trusted user context
       |
       v
Check required role
       |
       v
Find resource within user's tenant
       |
       v
Check ownership where applicable
       |
       v
Execute authorized operation
```

When a resource identifier is supplied, avoid revealing cross-tenant resource existence.

### 7.5 Role Error Handling

Return:

- 401 when unauthenticated.
- 403 when the authenticated role cannot perform an operation.
- 404 when the requested ticket does not exist or is inaccessible.

For another Customer's ticket in the same business, return 404 as a documented implementation decision.

---

## 8. Multi-Tenant Isolation

### 8.1 Tenancy Model

**MUST**

Each user belongs to exactly one business.

Tickets belong to businesses.

Messages belong to tickets.

**DECISION**

Use a shared PostgreSQL database and shared schema.

Tenant boundaries are enforced in the backend.

### 8.2 Trusted Tenant Context

The backend must derive the authenticated tenant from trusted user information.

Never use a client-provided `business_id` to determine authorization.

Untrusted sources include:

```text
Request body
Query string
Route parameters
WebSocket payload
Frontend local state
```

### 8.3 Ticket Query Security

**MUST**

Protected ticket queries must be scoped by business.

Correct:

```python
ticket = (
    db.query(Ticket)
    .filter(
        Ticket.id == ticket_id,
        Ticket.business_id == current_user.business_id,
    )
    .first()
)
```

Incorrect:

```python
ticket = (
    db.query(Ticket)
    .filter(Ticket.id == ticket_id)
    .first()
)
```

The second example does not enforce tenant isolation.

### 8.4 Customer Ownership

**MUST**

Customers can access only tickets they own.

Additional condition:

```python
Ticket.customer_id == current_user.id
```

An Agent or Admin may view all tickets within their business according to the original assessment.

Assignment is not required for an Agent to view or reply to a same-business ticket.

### 8.5 Message Access

Messages inherit their tenant boundary through the parent ticket.

Before returning message history:

1. Authenticate the user.
2. Find the ticket within the user's business.
3. Verify Customer ownership if necessary.
4. Return messages belonging to the authorized ticket.

Do not retrieve messages by ticket ID without validating ticket access.

### 8.6 Cross-Business Access

Example:

```text
Business A
business_id = A

Business B
business_id = B

Ticket 123
business_id = B
```

Business A requests:

```http
GET /tickets/123
```

Expected:

```http
404 Not Found
```

Response:

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket not found.",
    "details": null
  }
}
```

Never reveal whether the inaccessible ticket exists.

### 8.7 Tenant Isolation Scope

Tenant authorization must cover:

- Ticket lists.
- Ticket details.
- Ticket updates.
- Ticket assignment.
- Message history.
- Message creation.
- WebSocket connections.
- WebSocket events.
- Business user management.

Every relevant protected operation must preserve tenant isolation.

---

## 9. User Management Security

### 9.1 User Creation

**MUST**

Only Admin can create business users.

Allowed new-user roles:

```text
agent
customer
```

The new user's `business_id` must come from the authenticated Admin.

Client-supplied tenant identifiers must not override server-side membership.

### 9.2 Global Email Uniqueness

**MUST**

Each email must be unique across the entire platform.

Enforce this using a database uniqueness constraint.

Application-level existence checks may improve error messages, but the database constraint remains authoritative.

### 9.3 User Listing

Only Admin can list users in their business.

The endpoint must never expose users belonging to other businesses.

Never return:

- Password hashes.
- Authentication secrets.
- Refresh tokens.

---

## 10. Ticket Security

### 10.1 Ticket Creation

**MUST**

Only Customer can create tickets.

The backend must derive:

```text
business_id = current_user.business_id
customer_id = current_user.id
status = open
assigned_agent_id = null
```

The client must not control these fields during ticket creation.

### 10.2 Atomic Creation

**DECISION**

Create the ticket and initial message in one database transaction.

If message creation fails, roll back ticket creation.

Avoid tickets being created without their required first message.

### 10.3 Agent Assignment

**MUST**

Admin may assign tickets to an Agent within the same business.

Agent may assign a permitted ticket to themselves.

Customer may not assign tickets.

**DECISION**

Agent self-assignment is permitted only if:

- Ticket has no assigned Agent, or
- Ticket is already assigned to that Agent.

A ticket assigned to another Agent cannot be taken over by an Agent through self-assignment.

Admin may reassign within the same business.

### 10.4 Assignment Validation

The target Agent must:

1. Exist.
2. Have the `agent` role.
3. Belong to the ticket's business.

Reject cross-business assignments.

Do not leak target users from other businesses through detailed assignment errors.

### 10.5 Ticket State Security

Allowed statuses:

```text
open
in_progress
resolved
closed
```

Allowed transitions:

```text
open -> in_progress
in_progress -> resolved
resolved -> closed
resolved -> open (Customer owner only)
```

Rules:

- Agent and Admin perform normal transitions.
- Customer may reopen only their own resolved ticket.
- Closed tickets are terminal.
- Closed tickets cannot receive new messages.
- Invalid transitions are rejected.

**DECISION**

Return HTTP 409 for invalid state transitions.

### 10.6 State Validation

Ticket state transitions must be enforced in the backend service layer.

Do not trust frontend status controls.

Every update must verify:

- Current status.
- Requested status.
- Authenticated role.
- Ticket business.
- Customer ownership when applicable.

### 10.7 Concurrent Operations

**RECOMMENDED**

Protect concurrent writes to the same ticket.

In particular, prevent a message from being committed after a concurrent transaction closes the ticket.

A suitable PostgreSQL approach is to lock the ticket row during message insertion and status transitions.

Agent self-assignment should also use a transaction-safe conditional update or row lock to prevent conflicting claims.

Do not introduce a distributed locking service for the MVP.

---

## 11. WebSocket Security

### 11.1 WebSocket Endpoint

**MUST**

```text
/ws/tickets/{ticket_id}?token=<access_token>
```

Use the same JWT authentication system as REST requests.

Refresh tokens must not authorize WebSocket connections.

### 11.2 Connection Authorization

Before calling `websocket.accept()`:

1. Extract the access token.
2. Verify JWT signature.
3. Verify expiration.
4. Verify token type.
5. Resolve the authenticated user.
6. Verify ticket existence within the user's business.
7. Verify role and Customer ownership.
8. Accept only authorized connections.

Invalid or unauthorized connections must be rejected.

### 11.3 Connection Flow

```text
WebSocket handshake
        |
        v
Validate token
        |
        v
Resolve user
        |
        v
Verify ticket business
        |
        v
Verify role and ownership
        |
     +--+--+
     |     |
   Allow  Deny
     |     |
     v     v
   Accept Reject
     |
     v
Join ticket room
```

### 11.4 WebSocket Authorization Matrix

| Role | Connect | Read | Send |
|---|---|---|---|
| Admin | Same-business ticket | Yes | No |
| Agent | Same-business ticket | Yes | Yes |
| Customer | Own ticket | Yes | Yes |
| Other business | No | No | No |

Admin read-only access is a documented implementation decision.

### 11.5 Message Authorization

For every `message.send` event:

1. Validate the event payload.
2. Validate the sender's authenticated identity.
3. Verify that the user still has permission.
4. Verify that the ticket is not closed.
5. Persist the message.
6. Broadcast only after a successful commit.

Never trust client-provided:

- `sender_id`.
- `sender_role`.
- `business_id`.
- `ticket_id` overrides.
- System timestamps.

The sender must be determined from the authenticated connection.

### 11.6 WebSocket Token Expiration

**DECISION**

WebSocket authorization is checked during connection establishment.

Before processing subsequent sensitive message operations, revalidate relevant authentication and authorization state, including token expiration.

If authentication is no longer valid, close the connection.

Do not allow an expired connection to continue performing protected operations.

### 11.7 WebSocket Origin Validation

**RECOMMENDED**

Validate the browser's `Origin` header against configured allowed frontend origins before accepting connections.

WebSocket connections are not protected by CORS in the same way as ordinary browser HTTP requests.

Origin validation complements JWT authentication and does not replace it.

### 11.8 WebSocket Close Behavior

**DECISION**

Use a policy-violation close code such as `1008` for relevant authorization or policy violations when supported.

Handshake rejection before connection acceptance may use the ASGI server's HTTP rejection behavior.

Do not require ordinary REST JSON error responses during rejected WebSocket handshakes.

### 11.9 WebSocket Broadcasting

Only broadcast events to the authorized ticket room.

Example:

```text
Ticket A room
- Customer A
- Agent A

Ticket B room
- Customer B
- Agent B
```

A message from Ticket A must never be broadcast to Ticket B.

### 11.10 WebSocket Token Exposure

WebSocket authentication uses a query-string token because the assessment provides this endpoint format.

Query-string tokens may appear in:

- Proxy logs.
- Access logs.
- Debug output.
- Monitoring systems.

Security controls:

- Use WSS in production.
- Never log the complete WebSocket URL.
- Redact query-string tokens.
- Use short-lived access tokens.
- Never place refresh tokens in WebSocket URLs.

---

## 12. Database Security

### 12.1 Referential Integrity

Use foreign keys for:

- `users.business_id`.
- `tickets.business_id`.
- `tickets.customer_id`.
- `tickets.assigned_agent_id`.
- `messages.ticket_id`.
- `messages.sender_id`.

### 12.2 Relationship Validation

Foreign keys alone do not guarantee tenant isolation.

For example, an Agent may exist but belong to another business.

Therefore, service-layer validation must verify related business membership.

### 12.3 Database Constraints

Required:

- Unique business slug.
- Globally unique email.
- Ticket business foreign key.
- Required ticket status and priority values.
- Ticket `(business_id, status)` index.

Recommended:

- Additional foreign-key indexes where appropriate.
- Valid role constraints.
- Positive identifier and timestamp consistency.
- Database-level checks for enum-like values where suitable.

### 12.4 Migration Security

Use Alembic for all schema changes.

Do not manually modify database schemas outside the migration workflow.

Before applying destructive migrations:

- Review affected tables.
- Review data-loss implications.
- Verify migration compatibility.

Never run destructive database commands against production without explicit authorization.

### 12.5 SQL Injection Prevention

Use SQLAlchemy parameterized queries.

Never construct SQL by concatenating untrusted user input.

Avoid raw SQL unless necessary and safely parameterized.

---

## 13. Input Validation

### 13.1 REST Input Validation

Use Pydantic schemas.

**DECISION**

Apply the validation limits established in `docs/API_CONTRACT.md`.

Examples:

- Valid email.
- Required non-empty names.
- Valid user roles.
- Valid ticket priorities.
- Valid ticket statuses.
- Required subject.
- Required initial message.
- Maximum message length of 5,000 characters.

Reject unexpected write-request fields.

### 13.2 Mass Assignment Protection

Never blindly map request bodies into database models.

Example of prohibited behavior:

```python
ticket = Ticket(**request_data)
```

when untrusted fields have not been constrained by an explicit request schema.

Use explicitly validated and permitted fields instead.

### 13.3 WebSocket Payload Validation

For `message.send`:

- Require supported event type.
- Require a non-empty body.
- Enforce message size limits.
- Reject unsupported identity fields.
- Reject malformed JSON.
- Reject unsupported operations.

### 13.4 Output Encoding

User-submitted message content is untrusted.

Frontend chat content must be displayed safely.

Do not render arbitrary message HTML with `dangerouslySetInnerHTML`.

Do not execute JavaScript or HTML supplied through ticket messages.

---

## 14. API Error Security

### 14.1 Error Response Format

Use the JSON error contract defined in `docs/API_CONTRACT.md`.

Example:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You are not allowed to perform this action.",
    "details": null
  }
}
```

### 14.2 Required Status Semantics

| HTTP Status | Meaning |
|---|---|
| 401 | Authentication missing or invalid |
| 403 | Authenticated role lacks permission |
| 404 | Resource unavailable or cross-tenant |
| 422 | Invalid input |

**DECISION**

Use 409 for invalid state transitions and resource conflicts.

### 14.3 Information Disclosure Prevention

Never return:

- Database connection strings.
- Internal stack traces.
- JWT signing secrets.
- Password hashes.
- Raw database exception messages.
- Hidden cross-business resource information.

### 14.4 Unexpected Exceptions

Return a generic 500 response.

Record diagnostic information only in internal logs, with sensitive values redacted.

---

## 15. Secrets and Environment Security

### 15.1 Secret Management

Secrets must be loaded from environment variables.

Examples:

```text
DATABASE_URL
JWT_SECRET
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS
CORS_ORIGINS
```

### 15.2 Git Security

Never commit:

```text
.env
.env.local
.env.production
Actual JWT secrets
Production database credentials
Real API keys
Private keys
```

Commit:

```text
.env.example
```

The example file must contain placeholders only.

### 15.3 Environment Validation

Validate required environment variables during backend startup.

Do not silently fall back to insecure development secrets.

### 15.4 Demo Accounts

The assessment requires demo accounts in README.

Use disposable test-only credentials.

Never reuse personal or production passwords.

Demo credentials must not grant access to real data or deployed production systems.

---

## 16. Logging and Monitoring Security

### 16.1 Logging Objectives

Logs should help investigate:

- Authentication failures.
- Authorization failures.
- Unexpected application errors.
- WebSocket connection failures.
- Database errors.

### 16.2 Sensitive Data Redaction

Never log:

- Plaintext passwords.
- Password hashes.
- Full access tokens.
- Full refresh tokens.
- JWT signing secrets.
- Full authenticated WebSocket URLs containing tokens.
- Authentication cookies.

Avoid logging complete private chat messages.

### 16.3 Security Events

**RECOMMENDED**

Useful log fields include:

```text
timestamp
event
request_id
user_id
business_id
resource_type
status_code
```

Only include identifiers and metadata when appropriate.

Do not introduce a complex external monitoring platform for the MVP.

---

## 17. Security Testing Strategy

Use pytest for backend security tests.

Tests must verify behavior rather than merely checking implementation details.

### 17.1 Authentication Tests

- [ ] Valid login succeeds.
- [ ] Incorrect password returns 401.
- [ ] Unknown email returns generic 401.
- [ ] Expired access token is rejected.
- [ ] Invalid JWT signature is rejected.
- [ ] Refresh token cannot access protected endpoints.
- [ ] Access token cannot be used as refresh token.
- [ ] `/auth/me` requires authentication.
- [ ] Password hashes are never returned.

### 17.2 Role Authorization Tests

- [ ] Admin can create an Agent.
- [ ] Admin can create a Customer.
- [ ] Agent cannot create users.
- [ ] Customer cannot create users.
- [ ] Customer cannot assign Agents.
- [ ] Agent cannot assign another Agent.
- [ ] Admin assignment is restricted to same-business Agents.
- [ ] Customer cannot perform normal status changes.

### 17.3 Tenant Isolation Tests

- [ ] Business A cannot list Business B tickets.
- [ ] Business A cannot open Business B ticket details.
- [ ] Cross-business ticket access returns 404.
- [ ] Business A cannot read Business B messages.
- [ ] Customer A cannot open Customer B tickets.
- [ ] Customer A cannot read Customer B messages.
- [ ] Admin A cannot manage Business B users.
- [ ] Cross-business agent assignment is rejected.
- [ ] Client-provided `business_id` cannot bypass isolation.

### 17.4 WebSocket Tests

- [ ] Valid authorized connections succeed.
- [ ] Missing token is rejected.
- [ ] Invalid token is rejected.
- [ ] Expired token is rejected.
- [ ] Refresh token is rejected.
- [ ] Cross-business connection is rejected.
- [ ] Cross-customer unauthorized connection is rejected.
- [ ] Admin message sending is rejected according to the architecture decision.
- [ ] Agent message sending succeeds for permitted tickets.
- [ ] Customer message sending succeeds for owned tickets.
- [ ] Closed tickets reject new messages.
- [ ] Messages are stored before broadcasting.
- [ ] Status updates are broadcast to the correct room.
- [ ] No events are delivered across ticket rooms.

### 17.5 Database Security Tests

- [ ] Duplicate business slugs are rejected.
- [ ] Duplicate user emails are rejected globally.
- [ ] Invalid role values are rejected.
- [ ] Invalid ticket priority values are rejected.
- [ ] Ticket creation and initial-message persistence are atomic.
- [ ] Invalid foreign-key relationships are rejected.
- [ ] Related user membership is validated.

### 17.6 Secret Exposure Checks

- [ ] No real `.env` files are committed.
- [ ] No real credentials appear in source code.
- [ ] No JWT signing secrets are hardcoded.
- [ ] API responses do not expose passwords.
- [ ] Logs do not expose authentication tokens.

---

## 18. Security Acceptance Scenarios

### Scenario 1: Cross-Business Access

**Given:**

Business A has User A.

Business B has Ticket B.

**When:**

User A requests Ticket B.

**Then:**

- HTTP 404 is returned.
- Ticket contents are not returned.
- No information about Business B is disclosed.

### Scenario 2: Cross-Customer Access

**Given:**

Customer A and Customer B belong to the same business.

Customer B owns Ticket B.

**When:**

Customer A requests Ticket B.

**Then:**

- Access is rejected.
- HTTP 404 is returned according to the selected implementation policy.
- No ticket messages are exposed.

### Scenario 3: Unauthorized User Management

**Given:**

An authenticated Agent.

**When:**

The Agent calls `POST /users`.

**Then:**

- HTTP 403 is returned.
- No user is created.

### Scenario 4: Cross-Business Assignment

**Given:**

A ticket belongs to Business A.

An Agent belongs to Business B.

**When:**

Admin A attempts to assign Agent B.

**Then:**

- Assignment is rejected.
- Existing assignment remains unchanged.
- Agent B's protected information is not disclosed.

### Scenario 5: Unauthorized WebSocket

**Given:**

A valid Business A user.

**When:**

The user attempts to connect to Business B's ticket WebSocket.

**Then:**

- Connection is rejected.
- The user never joins the ticket room.
- No messages or status events are exposed.

### Scenario 6: Closed Ticket Protection

**Given:**

A ticket has status `closed`.

**When:**

An authorized participant attempts to send a message.

**Then:**

- Message creation is rejected.
- No new message is committed.
- No `message.created` event is broadcast.

### Scenario 7: Token Type Confusion

**Given:**

A valid refresh token.

**When:**

The token is used as a REST access token or WebSocket access token.

**Then:**

- Authorization fails.
- No protected data is returned.

---

## 19. Security Review Checklist

Before completing each milestone, review the relevant items.

### Authentication

- [ ] Password hashing is correct.
- [ ] JWT validation is correct.
- [ ] Access and refresh token types are separated.
- [ ] Sensitive credentials are not exposed.

### Authorization

- [ ] Every protected route checks authentication.
- [ ] Role permissions are enforced.
- [ ] Tenant membership is enforced.
- [ ] Resource ownership is enforced where required.

### Database

- [ ] Foreign keys are valid.
- [ ] Tenant-related references are validated.
- [ ] Writes use appropriate transactions.
- [ ] Cross-business data cannot be retrieved.

### WebSocket

- [ ] JWT is validated before connection acceptance.
- [ ] Ticket authorization is checked.
- [ ] Send permissions are validated.
- [ ] Closed-ticket restrictions are enforced.
- [ ] Broadcasts are scoped to the correct ticket.

### Secrets

- [ ] No actual credentials are committed.
- [ ] `.env.example` contains placeholders.
- [ ] Logs do not expose sensitive authentication data.

---

## 20. Automatic Failure Prevention

The original technical assessment defines four automatic-failure conditions.

### FAIL-001: Cross-Tenant Exposure

Another business's protected data is accessible through API requests or guessed resource IDs.

**Required prevention:**

Backend tenant filtering, resource authorization, and security tests.

### FAIL-002: Plaintext Passwords

Passwords are stored or returned in plaintext.

**Required prevention:**

Argon2 hashing and safe response schemas.

### FAIL-003: Exposed Secrets

Actual credentials or secrets are committed to Git.

**Required prevention:**

Environment variables, `.gitignore`, and secret-exposure checks.

### FAIL-004: Unexplainable Implementation

The candidate cannot explain their own code during technical review.

**Required prevention:**

- Simple architecture.
- Readable code.
- Small milestones.
- Meaningful tests.
- Documented decisions.
- No unnecessary abstractions.

---

## 21. Known Security Limitations

The following limitations are accepted for the initial assessment MVP.

### 21.1 Stateless Refresh Tokens

Immediate revocation is not supported without additional server-side token state.

### 21.2 Single-Process WebSocket Manager

In-memory WebSocket broadcasts do not work across multiple backend processes.

### 21.3 No Advanced Rate Limiting

Login rate limiting is a bonus feature in the assessment.

It may be added after mandatory features are complete.

### 21.4 No Distributed Security Infrastructure

The MVP does not use:

- Redis-based token revocation.
- Distributed WebSocket messaging.
- External identity providers.
- Dedicated secrets-management services.
- Enterprise audit infrastructure.

These are not required for the assessment.

Do not claim the MVP provides production-grade security capabilities that have not been implemented.

---

## 22. Security Definition of Done

Security implementation is considered complete for the assessment when:

- [ ] Passwords are securely hashed.
- [ ] JWT signature and expiration are validated.
- [ ] Access and refresh tokens are correctly distinguished.
- [ ] Role-based permissions are enforced.
- [ ] Cross-business resource access is blocked.
- [ ] Customer ticket ownership is enforced.
- [ ] Cross-tenant ticket requests return 404.
- [ ] Cross-business assignment is rejected.
- [ ] WebSocket authentication is enforced.
- [ ] WebSocket ticket authorization is enforced.
- [ ] Unauthorized WebSocket messages are rejected.
- [ ] Closed tickets cannot receive messages.
- [ ] Sensitive data is excluded from API errors and logs.
- [ ] No real secrets are committed.
- [ ] Critical security scenarios have been tested.
- [ ] No automatic-failure condition is present.
- [ ] Known limitations are documented honestly.

A security requirement is not complete merely because validation code exists.

Its expected behavior must be verified.

---

## 23. Codex Security Rules

When Codex implements or modifies security-sensitive code, it must:

1. Read the relevant security requirements.
2. Inspect existing authentication and authorization logic.
3. Preserve tenant isolation.
4. Reuse centralized authentication and authorization helpers.
5. Never remove security checks to make tests pass.
6. Never weaken validation without documented justification.
7. Never expose credentials or secrets.
8. Add or update relevant security tests.
9. Execute affected tests when possible.
10. Report validation results accurately.
11. Document unresolved security risks.
12. Stop after the requested milestone.

If a change creates a possible cross-tenant data exposure, treat it as a critical blocker.

Do not mark the milestone as completed.

---

## 24. Final Security Principle

HelpDesk Mini uses the backend as the single authority for:

- Authentication.
- User identity.
- Business membership.
- Role permissions.
- Resource ownership.
- Ticket state.
- Message authorization.
- Real-time communication access.

Every protected operation must be authenticated, authorized, and scoped to the correct business.

**Security is verified through observable behavior and tests, not assumed from implementation structure.**