# HelpDesk Mini - API Contract

**Project:** HelpDesk Mini  
**Document:** `docs/API_CONTRACT.md`  
**Version:** 1.0  
**Status:** Proposed Implementation Contract  
**Backend:** FastAPI  
**Frontend:** Next.js App Router  
**Protocol:** HTTP REST + WebSocket

---

## 1. Purpose

This document defines the communication contract between the Next.js frontend and FastAPI backend.

It specifies:

- REST API endpoints.
- Authentication and token handling.
- Request and response schemas.
- Role-based authorization.
- Multi-tenant access restrictions.
- HTTP status codes.
- WebSocket connection rules.
- Real-time event payloads.
- Validation and error conventions.

Both frontend and backend must follow the same contract.

Do not silently modify endpoint paths, request fields, response structures, or WebSocket events.

Any approved contract change must update this document and the affected implementation.

### 1.1 Source of Truth

The original SVO Connect technical assessment remains authoritative when available. Within this repository, follow:

1. `docs/REQUIREMENTS.md`.
2. `docs/SECURITY.md`.
3. This API contract.
4. `ARCHITECTURE.md`.
5. The active execution plan.
6. Existing source code and tests.

**MUST** means explicitly required by the assessment.

**DECISION** means a selected implementation approach not prescribed by the assessment.

---

## 2. API Conventions

### 2.1 Base URLs

**DECISION**

Development:

```text
REST API: http://localhost:8000
WebSocket: ws://localhost:8000
Swagger: http://localhost:8000/docs
Frontend: http://localhost:3000
```

The backend may optionally use an API prefix in the future, but all documented endpoint paths must remain consistent.

### 2.2 Content Type

REST requests and responses use:

```http
Content-Type: application/json
```

Exceptions include WebSocket communication and responses that do not require a body.

### 2.3 Resource Identifiers

**DECISION**

Use UUID identifiers for primary keys.

Example:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

UUIDs do not replace authorization.

All protected resource requests must still validate tenant membership and ownership.

### 2.4 Timestamp Format

**DECISION**

Return timestamps using ISO 8601 in UTC.

Example:

```json
{
  "created_at": "2026-10-09T10:00:00Z"
}
```

The frontend may convert timestamps to the user's local timezone.

---

## 3. Standard API Responses

### 3.1 Successful Response

**DECISION**

Use a consistent `data` envelope.

Example:

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Example Business"
  }
}
```

For collections:

```json
{
  "data": []
}
```

Do not introduce unnecessary pagination metadata until pagination is implemented.

### 3.2 Error Response

**DECISION**

All REST API errors use:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": null
  }
}
```

Field validation errors may contain structured `details`.

The `details` property must not expose database internals, JWT secrets, passwords, or stack traces.

### 3.3 HTTP Status Codes

| Status | Meaning |
|---|---|
| 200 | Request successful |
| 201 | Resource created |
| 400 | Malformed or unsupported operation |
| 401 | Missing or invalid authentication |
| 403 | Authenticated role lacks permission |
| 404 | Resource not found or inaccessible |
| 409 | Resource conflict or invalid state transition |
| 422 | Request validation failed |
| 500 | Unexpected internal server error |

**MUST:** Preserve the assessment's required 401, 403, 404, and 422 semantics.

**DECISION:** Use 409 for conflicts such as duplicate unique values or invalid ticket state transitions.

### 3.4 Standard Error Codes

| Error code | HTTP status |
|---|---|
| AUTH_INVALID_CREDENTIALS | 401 |
| AUTH_TOKEN_INVALID | 401 |
| AUTH_TOKEN_EXPIRED | 401 |
| AUTH_TOKEN_WRONG_TYPE | 401 |
| FORBIDDEN | 403 |
| RESOURCE_NOT_FOUND | 404 |
| TICKET_NOT_FOUND | 404 |
| CONFLICT | 409 |
| INVALID_STATUS_TRANSITION | 409 |
| TICKET_ALREADY_ASSIGNED | 409 |
| TICKET_CLOSED | 409 |
| VALIDATION_ERROR | 422 |
| INTERNAL_SERVER_ERROR | 500 |

Cross-tenant ticket requests must return `TICKET_NOT_FOUND` without revealing whether the ticket exists in another business.

---

## 4. Authentication Contract

### 4.1 Authentication Strategy

**MUST**

- JWT access token.
- JWT refresh token.
- Password hashing.
- Authenticated `/me` endpoint.
- Protected frontend routing.

**DECISION**

- Access token transported through the Authorization header.
- Access token stored in frontend memory.
- Login response returns both tokens as required.
- Browser refresh token additionally stored in an HttpOnly cookie.
- Browser refresh operations use the refresh cookie.
- Refresh-token rotation is not required for the initial MVP.

### 4.2 Access Token

REST requests use:

```http
Authorization: Bearer <access_token>
```

Recommended JWT claims:

```json
{
  "sub": "user-uuid",
  "business_id": "business-uuid",
  "role": "agent",
  "type": "access",
  "exp": 1791543600
}
```

Claims are implementation decisions.

Backend authorization must not trust unverified JWT claims.

After validating the token, resolve the authenticated user and apply current business and role restrictions.

### 4.3 Refresh Token

A refresh token must:

- Have a distinct `type` claim.
- Have a valid signature.
- Have a valid expiration.
- Be rejected when used as an access token.

**DECISION**

Initial expiration policy:

- Access token: 15 minutes.
- Refresh token: 7 days.

Configure these values through environment variables.

### 4.4 Browser Token Handling

**DECISION**

For browser authentication:

1. Login returns access and refresh tokens in JSON.
2. Backend also sets the refresh token in an HttpOnly cookie.
3. Frontend retains the access token in memory.
4. Frontend does not persist the response-body refresh token.
5. Browser calls `/auth/refresh` with credentials enabled.
6. Backend reads the refresh token from the cookie.
7. Successful refresh returns a new access token.

Recommended cookie properties:

- `HttpOnly=true`.
- `SameSite=Lax` for the selected same-site setup.
- `Path=/auth/refresh`.
- `Secure=true` over HTTPS.
- `Secure=false` only for local HTTP development.

Use allowed-origin validation and CSRF protection appropriate to the cookie deployment configuration.

Future genuinely cross-site deployments require `SameSite=None`, HTTPS (`Secure=true`), and appropriate CSRF protection.

For different frontend/backend origins, configure CORS with explicit allowed origins and credential support.

Never use wildcard origins with credentialed CORS.

---

## 5. Authentication Endpoints

### AUTH-01: Register Business

```http
POST /auth/register-business
```

**Access:** Public  
**Success:** 201 Created

**DECISION: Request schema**

```json
{
  "business": {
    "name": "Alpha Store",
    "slug": "alpha-store"
  },
  "admin": {
    "name": "Alpha Admin",
    "email": "admin@alpha.test",
    "password": "DemoPass123!"
  }
}
```

**Response**

```json
{
  "data": {
    "business": {
      "id": "business-uuid",
      "name": "Alpha Store",
      "slug": "alpha-store",
      "created_at": "2026-10-09T10:00:00Z"
    },
    "admin": {
      "id": "admin-uuid",
      "business_id": "business-uuid",
      "name": "Alpha Admin",
      "email": "admin@alpha.test",
      "role": "admin",
      "created_at": "2026-10-09T10:00:00Z"
    }
  }
}
```

**Business Rules**

- Create business and Admin in one database transaction.
- Roll back both records if either creation fails.
- Business slug must be unique.
- Email must be globally unique.
- Password must be hashed.
- Do not return passwords or hashes.
- Public registration creates only an Admin account, not an Agent or Customer account.

**Possible Errors**

- 409: Duplicate email or slug.
- 422: Invalid input.

---

### AUTH-02: Login

```http
POST /auth/login
```

**Access:** Public  
**Success:** 200 OK

**Request**

```json
{
  "email": "admin@alpha.test",
  "password": "DemoPass123!"
}
```

**Response**

```json
{
  "data": {
    "access_token": "jwt-access-token",
    "refresh_token": "jwt-refresh-token",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

The response also sets the HttpOnly refresh-token cookie for browser clients.

**Business Rules**

- Verify credentials using the configured password hashing algorithm.
- Use a generic error for incorrect email or password.
- Never expose whether a particular email exists.
- Do not log plaintext passwords or tokens.

**Possible Errors**

- 401: Invalid credentials.
- 422: Invalid input.

---

### AUTH-03: Refresh Access Token

```http
POST /auth/refresh
```

**Access:** Valid refresh token  
**Success:** 200 OK

**DECISION: Browser Request**

The browser sends the refresh token through its HttpOnly cookie.

No JSON request body is required.

API clients such as Postman can test refresh by retaining the login response cookie in a cookie jar and sending it to this endpoint. JSON-body refresh tokens are not part of this contract.

**Response**

```json
{
  "data": {
    "access_token": "new-jwt-access-token",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

**Business Rules**

- Validate refresh-token signature.
- Validate expiration.
- Validate token type.
- Reject access tokens used as refresh tokens.
- Reject tokens whose associated user is no longer valid.
- Issue a new access token.

The initial MVP does not guarantee immediate refresh-token revocation or rotation.

**Possible Errors**

- 401: Missing refresh token.
- 401: Invalid or expired refresh token.

---

### AUTH-04: Current User

```http
GET /auth/me
```

**Access:** Authenticated  
**Success:** 200 OK

**Response**

```json
{
  "data": {
    "id": "user-uuid",
    "name": "Alpha Admin",
    "email": "admin@alpha.test",
    "role": "admin",
    "business": {
      "id": "business-uuid",
      "name": "Alpha Store",
      "slug": "alpha-store"
    }
  }
}
```

**Business Rules**

- User identity comes from validated authentication.
- Return the user's own business only.
- Never return a password or password hash.

**Possible Errors**

- 401: Missing or invalid access token.

---

## 6. User Management Endpoints

### USER-01: List Business Users

```http
GET /users
```

**Access:** Admin only  
**Success:** 200 OK

**Response**

```json
{
  "data": [
    {
      "id": "user-uuid",
      "business_id": "business-uuid",
      "name": "Customer One",
      "email": "customer1@alpha.test",
      "role": "customer",
      "created_at": "2026-10-09T10:00:00Z"
    }
  ]
}
```

**Business Rules**

- Derive business membership from the authenticated Admin.
- Return only users belonging to that business.
- Exclude password hashes.
- Agent and Customer requests must be rejected.

**Possible Errors**

- 401: Unauthenticated.
- 403: Incorrect role.

---

### USER-02: Create Business User

```http
POST /users
```

**Access:** Admin only  
**Success:** 201 Created

**Request**

```json
{
  "name": "Support Agent",
  "email": "agent@alpha.test",
  "password": "DemoPass123!",
  "role": "agent"
}
```

**Allowed roles**

- `agent`
- `customer`

**Response**

```json
{
  "data": {
    "id": "user-uuid",
    "business_id": "business-uuid",
    "name": "Support Agent",
    "email": "agent@alpha.test",
    "role": "agent",
    "created_at": "2026-10-09T10:00:00Z"
  }
}
```

**Business Rules**

- Use the authenticated Admin's `business_id`.
- Do not accept client-controlled tenant assignment.
- Admin cannot create another Admin through this endpoint.
- Email must be globally unique.
- Password must be hashed.

**Possible Errors**

- 401: Unauthenticated.
- 403: Incorrect role.
- 409: Email already exists.
- 422: Invalid input or unsupported role.

---

## 7. Ticket Data Contracts

### 7.1 Priority

Allowed values:

```text
low
medium
high
```

### 7.2 Status

Allowed values:

```text
open
in_progress
resolved
closed
```

### 7.3 Ticket Representation

**DECISION**

Ticket responses use the following core fields:

```json
{
  "id": "ticket-uuid",
  "business_id": "business-uuid",
  "customer_id": "customer-uuid",
  "assigned_agent_id": null,
  "subject": "Unable to access my account",
  "category": "account",
  "priority": "high",
  "status": "open",
  "created_at": "2026-10-09T10:00:00Z",
  "updated_at": "2026-10-09T10:00:00Z"
}
```

Additional read-only customer and assignee information may be included in ticket detail responses.

### 7.4 Status Transition Rules

Allowed transitions:

| Current status | Next status | Authorized role |
|---|---|---|
| open | in_progress | Agent, Admin |
| in_progress | resolved | Agent, Admin |
| resolved | closed | Agent, Admin |
| resolved | open | Owning Customer |

**DECISION**

- Reject unsupported transitions with 409.
- A request to retain the current status is treated as a no-op.
- Closed is terminal.
- Customer cannot change status except for the permitted reopen operation.
- Admin and Agent cannot use the Customer-only reopen operation.

These rules follow the assessment's defined lifecycle and documented reopen path.

---

## 8. Ticket Endpoints

### TICKET-01: List Tickets

```http
GET /tickets
```

Optional query parameter:

```http
GET /tickets?status=open
```

**Access:** All authenticated roles  
**Success:** 200 OK

**Response**

```json
{
  "data": [
    {
      "id": "ticket-uuid",
      "business_id": "business-uuid",
      "customer_id": "customer-uuid",
      "assigned_agent_id": "agent-uuid",
      "subject": "Unable to access my account",
      "category": "account",
      "priority": "high",
      "status": "in_progress",
      "created_at": "2026-10-09T09:00:00Z",
      "updated_at": "2026-10-09T10:00:00Z",
      "assigned_agent": {
        "id": "agent-uuid",
        "name": "Support Agent"
      }
    }
  ]
}
```

**Business Rules**

- Admin sees all tickets within their business.
- Agent sees all tickets within their business.
- Customer sees only their own tickets.
- Filter by `status` when provided.
- Order by `updated_at` descending.
- Return an empty array when no tickets match.

**Possible Errors**

- 401: Unauthenticated.
- 422: Invalid status filter.

---

### TICKET-02: Create Ticket

```http
POST /tickets
```

**Access:** Customer only  
**Success:** 201 Created

**Request**

```json
{
  "subject": "Unable to access my account",
  "category": "account",
  "priority": "high",
  "message": "I cannot log in to my account."
}
```

**Response**

```json
{
  "data": {
    "id": "ticket-uuid",
    "business_id": "business-uuid",
    "customer_id": "customer-uuid",
    "assigned_agent_id": null,
    "subject": "Unable to access my account",
    "category": "account",
    "priority": "high",
    "status": "open",
    "created_at": "2026-10-09T10:00:00Z",
    "updated_at": "2026-10-09T10:00:00Z"
  }
}
```

**Business Rules**

- Only Customers can create tickets.
- Derive `business_id` and `customer_id` from authenticated context.
- Initial status is `open`.
- Initial assignee is `null`.
- Persist the first message in the `messages` table.
- Create the ticket and first message in one transaction.
- Roll back both if either operation fails.
- Reject invalid priority values.

**Possible Errors**

- 401: Unauthenticated.
- 403: Incorrect role.
- 422: Invalid input.

---

### TICKET-03: Ticket Details

```http
GET /tickets/{id}
```

**Access:** Authorized ticket viewers  
**Success:** 200 OK

**Response**

```json
{
  "data": {
    "id": "ticket-uuid",
    "business_id": "business-uuid",
    "customer_id": "customer-uuid",
    "assigned_agent_id": "agent-uuid",
    "subject": "Unable to access my account",
    "category": "account",
    "priority": "high",
    "status": "in_progress",
    "created_at": "2026-10-09T09:00:00Z",
    "updated_at": "2026-10-09T10:00:00Z",
    "customer": {
      "id": "customer-uuid",
      "name": "Customer One"
    },
    "assigned_agent": {
      "id": "agent-uuid",
      "name": "Support Agent"
    }
  }
}
```

**Business Rules**

- Admin and Agent can view tickets in their business.
- Customer can view only their own tickets.
- A ticket belonging to another business returns 404.
- Customer ownership violations also return 404 as a documented security decision.

**Possible Errors**

- 401: Unauthenticated.
- 404: Ticket does not exist or cannot be accessed.

Never reveal whether an inaccessible ticket exists.

---

### TICKET-04: Update Ticket

```http
PATCH /tickets/{id}
```

**Access:** Depends on operation  
**Success:** 200 OK

This endpoint supports status updates and agent assignment.

#### Update Status

**Request**

```json
{
  "status": "in_progress"
}
```

**Permissions**

- Admin: permitted normal transitions.
- Agent: permitted normal transitions.
- Customer: only `resolved -> open` for their own ticket.

#### Assign Agent

**Admin request**

```json
{
  "assigned_agent_id": "agent-uuid"
}
```

**Agent self-assignment**

```json
{
  "assigned_agent_id": "current-agent-uuid"
}
```

**Business Rules**

- Admin can assign a same-business Agent.
- Agent can assign themselves.
- Agent cannot assign another Agent.
- Customer cannot assign Agents.
- Reject a target user who is not a same-business Agent.
- Never accept a cross-tenant assignment.
- Validate the requested state transition.

**DECISION**

An Agent may claim an unassigned ticket or a ticket already assigned to themselves.

An Agent may not take a ticket already assigned to a different Agent. Return 409.

Admin may reassign a ticket to another Agent within the business.

#### Response

Return the updated ticket using the ticket-detail response structure:

```json
{
  "data": {
    "id": "ticket-uuid",
    "business_id": "business-uuid",
    "customer_id": "customer-uuid",
    "assigned_agent_id": "agent-uuid",
    "subject": "Unable to access my account",
    "category": "account",
    "priority": "high",
    "status": "in_progress",
    "created_at": "2026-10-09T09:00:00Z",
    "updated_at": "2026-10-09T10:00:00Z",
    "customer": {
      "id": "customer-uuid",
      "name": "Customer One"
    },
    "assigned_agent": {
      "id": "agent-uuid",
      "name": "Support Agent"
    }
  }
}
```

**Possible Errors**

- 401: Unauthenticated.
- 403: Operation not allowed for the role.
- 404: Ticket missing or inaccessible.
- 409: Assignment conflict or invalid transition.
- 422: Invalid request data.

### Real-Time Update Requirement

After a successful status change:

1. Persist the update.
2. Commit the database transaction.
3. Broadcast a ticket status event to connected ticket viewers.

Broadcast only committed state.

---

## 9. Message Contract

### 9.1 Message Representation

**DECISION**

```json
{
  "id": "message-uuid",
  "ticket_id": "ticket-uuid",
  "sender_id": "sender-uuid",
  "sender_name": "Customer One",
  "sender_role": "customer",
  "body": "I cannot log in to my account.",
  "created_at": "2026-10-09T10:01:00Z"
}
```

Every displayed message must include:

- Sender name.
- Sender role.
- Sending timestamp.
- Message content.

### 9.2 Message History Endpoint

```http
GET /tickets/{id}/messages
```

**Access:** Authorized ticket viewers  
**Success:** 200 OK

**Response**

```json
{
  "data": [
    {
      "id": "message-uuid",
      "ticket_id": "ticket-uuid",
      "sender_id": "customer-uuid",
      "sender_name": "Customer One",
      "sender_role": "customer",
      "body": "I cannot log in to my account.",
      "created_at": "2026-10-09T10:01:00Z"
    },
    {
      "id": "message-uuid-2",
      "ticket_id": "ticket-uuid",
      "sender_id": "agent-uuid",
      "sender_name": "Support Agent",
      "sender_role": "agent",
      "body": "I will help you check the issue.",
      "created_at": "2026-10-09T10:02:00Z"
    }
  ]
}
```

**Business Rules**

- Verify ticket access before retrieving messages.
- Enforce tenant isolation.
- Enforce Customer ownership.
- Sort by `created_at` ascending.
- Use message ID as a secondary sort key for deterministic ordering.
- Return an empty array when no messages exist.

**Possible Errors**

- 401: Unauthenticated.
- 404: Ticket missing or inaccessible.

Message creation is performed through the WebSocket protocol for the required live-chat workflow.

No additional REST message-creation endpoint is required by the initial assessment.

---

## 10. WebSocket Contract

### 10.1 Connection Endpoint

```text
WS /ws/tickets/{ticket_id}?token=<access_token>
```

Example development URL:

```text
ws://localhost:8000/ws/tickets/{ticket_id}?token=<access_token>
```

Use WSS when deployed over HTTPS.

### 10.2 Connection Authentication

**MUST**

Before accepting the connection:

1. Extract the token.
2. Validate JWT signature.
3. Validate token expiration.
4. Confirm token type is `access`.
5. Resolve the authenticated user.
6. Retrieve the requested ticket with tenant filtering.
7. Verify role and Customer ownership.
8. Accept the connection only if authorized.

Reject invalid and unauthorized connections before joining the ticket room.

Do not send ticket details or other protected data to unauthorized connections.

**DECISION**

Use a WebSocket policy-violation close code (`1008`) where applicable.

When the handshake is rejected before acceptance, the HTTP-level rejection behavior may depend on the ASGI server.

Do not require REST-style JSON errors for failed WebSocket handshakes.

### 10.3 WebSocket Permissions

| Role | Connect to permitted ticket | Send message |
|---|---|---|
| Admin | Yes | No |
| Agent | Yes | Yes |
| Customer | Own ticket only | Own ticket only |

**DECISION**

Admin connections are read-only.

The assessment explicitly grants chat replies to Agents and Customers but does not clearly define Admin message-sending permission.

This implementation choice must remain consistent with `ARCHITECTURE.md`.

---

## 11. WebSocket Event Schemas

**DECISION**

All WebSocket messages use JSON.

Each event contains a `type` field.

Server-to-client data events use a `data` property.

### WS-01: Send Message

**Direction:** Client -> Server

```json
{
  "type": "message.send",
  "body": "Hello, I need help with my account."
}
```

**Business Rules**

- Use the authenticated WebSocket user as the sender.
- Ignore no client-supplied identity; reject unexpected identity fields.
- Validate non-empty message content.
- Confirm the user can send to the ticket.
- Confirm the ticket is not closed.
- Save the message before broadcasting it.

**DECISION**

Initial message body limit: 5,000 characters.

Reject oversized or empty messages.

### WS-02: Message Created

**Direction:** Server -> Authorized ticket room

```json
{
  "type": "message.created",
  "data": {
    "id": "message-uuid",
    "ticket_id": "ticket-uuid",
    "sender_id": "customer-uuid",
    "sender_name": "Customer One",
    "sender_role": "customer",
    "body": "Hello, I need help with my account.",
    "created_at": "2026-10-09T10:01:00Z"
  }
}
```

**Business Rules**

- Broadcast only after successful persistence.
- Include the authoritative database message ID.
- Send to currently connected authorized clients.
- Include the sender so clients can reconcile their sent message.
- Never broadcast to another ticket room.

### WS-03: Ticket Status Changed

**Direction:** Server -> Authorized ticket room

```json
{
  "type": "ticket.status_changed",
  "data": {
    "ticket_id": "ticket-uuid",
    "status": "resolved",
    "updated_at": "2026-10-09T10:05:00Z"
  }
}
```

**Business Rules**

- Emit after successful committed status changes.
- Notify all connected viewers of that ticket.
- Do not notify unrelated ticket rooms.
- Frontend updates the displayed status.

### WS-04: Error Event

**Direction:** Server -> Client

```json
{
  "type": "error",
  "data": {
    "code": "TICKET_CLOSED",
    "message": "This ticket no longer accepts messages."
  }
}
```

Possible errors:

- `FORBIDDEN`
- `VALIDATION_ERROR`
- `TICKET_CLOSED`
- `INTERNAL_SERVER_ERROR`

For rejected authentication handshakes, do not expose protected details through an error event.

WebSocket application errors are not HTTP responses and must not be treated as HTTP status codes.

---

## 12. WebSocket Message Processing

### 12.1 Server Processing Sequence

```text
Receive WebSocket event
        |
        v
Validate event structure
        |
        v
Resolve authenticated sender
        |
        v
Verify ticket authorization
        |
        v
Check ticket is not closed
        |
        v
Persist message in PostgreSQL
        |
        v
Update ticket activity timestamp
        |
        v
Commit transaction
        |
        v
Broadcast message.created
```

### 12.2 Important Invariants

- Never trust a client-provided `sender_id`.
- Never trust a client-provided `business_id`.
- Never broadcast uncommitted messages.
- Never allow messages to closed tickets.
- Never send cross-tenant data through WebSocket.
- Never treat successful message delivery as proof of database persistence.
- Never allow unauthorized clients to join a ticket room.

### 12.3 Connection Management

**DECISION**

Use an in-memory WebSocket connection manager for the single-process MVP.

A ticket room is identified by `ticket_id`.

The manager must:

- Register accepted connections.
- Track ticket room membership.
- Remove disconnected connections.
- Broadcast events to the correct room.
- Handle failed connections safely.

The initial architecture does not support cross-process WebSocket broadcasting.

Document this limitation in README.

---

## 13. Frontend Integration Contract

### 13.1 HTTP API Client

The frontend must use a consistent typed API client.

Responsibilities:

- Configure the API base URL.
- Attach access tokens to authenticated requests.
- Handle API errors.
- Handle token expiration.
- Use credentials for browser refresh requests.
- Avoid exposing tokens through logs.

### 13.2 Token Refresh Flow

**DECISION**

```text
Frontend sends authenticated request
              |
              v
         HTTP 401
              |
              v
      POST /auth/refresh
       with credentials
              |
        +-----+-----+
        |           |
      Success      Failure
        |           |
        v           v
   Store new     Clear auth
   access token  state
        |           |
        v           v
   Retry once    Redirect
                 to /login
```

Only retry the original request once after a successful refresh.

Avoid infinite refresh loops and concurrent refresh storms.

### 13.3 TanStack Query

Use TanStack Query for:

- `/auth/me`.
- `/users`.
- `/tickets`.
- `/tickets/{id}`.
- `/tickets/{id}/messages`.

Relevant query cache must be updated or invalidated after successful mutations.

### 13.4 WebSocket Integration

When opening `/tickets/[id]`:

1. Confirm authenticated user.
2. Fetch ticket details.
3. Fetch message history.
4. Establish WebSocket connection if authorized.
5. Listen for `message.created`.
6. Listen for `ticket.status_changed`.
7. Update frontend state accordingly.

When leaving the page:

- Clean up the WebSocket connection.
- Remove relevant event listeners.

### 13.5 Reconnection

**DECISION**

On unexpected disconnection:

- Attempt a controlled reconnect.
- Obtain a valid access token if necessary.
- Revalidate ticket authorization.
- Refetch message history after reconnection.
- Prevent duplicate rendering using message IDs.

Automatic reconnection is an implementation-quality choice, not an additional mandatory assessment feature.

---

## 14. Role-Based API Matrix

| Endpoint | Admin | Agent | Customer |
|---|---|---|---|
| POST /auth/register-business | Public | Public | Public |
| POST /auth/login | Public | Public | Public |
| POST /auth/refresh | Valid refresh | Valid refresh | Valid refresh |
| GET /auth/me | Yes | Yes | Yes |
| GET /users | Yes | No | No |
| POST /users | Yes | No | No |
| GET /tickets | Business-wide | Business-wide | Own tickets |
| POST /tickets | No | No | Yes |
| GET /tickets/{id} | Business-wide | Business-wide | Own ticket |
| PATCH /tickets/{id} | Normal status / assign | Normal status / self-assign | Own resolved ticket reopen |
| GET /tickets/{id}/messages | Business-wide | Business-wide | Own ticket |
| WS /ws/tickets/{id} | Read-only | View and send | Own ticket, view and send |

**Important**

"Business-wide" always means within the authenticated user's own business.

No role may access another business's protected resources.

The authorization matrix does not override resource-level ownership checks.

---

## 15. Input Validation Rules

Use Pydantic schemas for REST request validation.

**DECISION**

Recommended initial constraints:

| Field | Validation |
|---|---|
| Business name | Required, non-empty |
| Business slug | Required, unique, lowercase URL-safe |
| User name | Required, non-empty |
| Email | Valid email format, globally unique |
| Password | Minimum 8 characters |
| User role | agent or customer during user creation |
| Ticket subject | Required, 1-150 characters |
| Ticket category | Required, non-empty string |
| Ticket priority | low, medium, high |
| Ticket status | Supported status values |
| Initial message | Required, 1-5000 characters |
| WebSocket message body | Required, 1-5000 characters |

These numeric limits and detailed validation rules are project decisions, not explicit assessment constraints.

### Unknown Fields

**DECISION**

Reject unexpected request fields for write operations using strict Pydantic schemas.

In particular, client submissions must not override:

- `business_id`.
- `customer_id`.
- `sender_id`.
- System timestamps.
- Authorization-related fields.

---

## 16. Multi-Tenant Security Contract

### SEC-01: Trusted Tenant Identity

All trusted tenant identity must originate from validated authentication and authorized database context.

### SEC-02: Ticket Access

Protected ticket queries must enforce:

```text
ticket.business_id == current_user.business_id
```

Customers additionally require:

```text
ticket.customer_id == current_user.id
```

### SEC-03: Cross-Tenant Responses

Example:

```http
GET /tickets/{business-b-ticket-id}
Authorization: Bearer <business-a-access-token>
```

Expected:

```http
404 Not Found
```

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket not found.",
    "details": null
  }
}
```

The API must not disclose that the requested ticket belongs to another business.

### SEC-04: Customer Ownership

A Customer accessing another Customer's ticket must be denied.

**DECISION:** Return 404 for this case as well.

### SEC-05: Assignment Isolation

A ticket cannot be assigned to a user from another business.

The target must also have the Agent role.

### SEC-06: Message Isolation

Message retrieval and creation must enforce authorization through the parent ticket.

### SEC-07: WebSocket Isolation

A WebSocket connection may join a ticket room only after ticket-level authorization succeeds.

The server must never broadcast protected ticket events to unauthorized connections.

---

## 17. API Error Handling Rules

All error paths must use the standard API error response.

### Authentication Failure

```http
401 Unauthorized
```

```json
{
  "error": {
    "code": "AUTH_TOKEN_INVALID",
    "message": "Authentication is invalid.",
    "details": null
  }
}
```

### Role Authorization Failure

```http
403 Forbidden
```

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You are not allowed to perform this action.",
    "details": null
  }
}
```

### Tenant Isolation Failure

```http
404 Not Found
```

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket not found.",
    "details": null
  }
}
```

### Invalid State Transition

```http
409 Conflict
```

```json
{
  "error": {
    "code": "INVALID_STATUS_TRANSITION",
    "message": "The requested ticket status transition is not allowed.",
    "details": null
  }
}
```

### Validation Failure

```http
422 Unprocessable Entity
```

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      {
        "field": "priority",
        "message": "Unsupported priority value."
      }
    ]
  }
}
```

All responses must avoid leaking internal exception details.

---

## 18. API Contract Acceptance Tests

These tests define minimum recommended verification of the contract.

### Authentication

- [ ] Business registration returns 201.
- [ ] Registration creates the business and Admin atomically.
- [ ] Login returns access and refresh tokens.
- [ ] `/auth/me` returns the authenticated user and business.
- [ ] Refresh returns a new access token.
- [ ] Missing authentication returns 401.
- [ ] Refresh tokens cannot access protected REST endpoints.

### User Management

- [ ] Admin can list same-business users.
- [ ] Admin can create Agents.
- [ ] Admin can create Customers.
- [ ] Agent cannot create users.
- [ ] Customer cannot create users.
- [ ] Global email uniqueness is enforced.

### Ticket Management

- [ ] Customer can create a ticket with an initial message.
- [ ] Ticket creation is atomic.
- [ ] Customer lists only owned tickets.
- [ ] Admin and Agent list only their business's tickets.
- [ ] Status filtering works.
- [ ] Ticket listing uses latest activity order.
- [ ] Agent can assign themselves.
- [ ] Admin can assign a same-business Agent.
- [ ] Cross-business assignment is rejected.
- [ ] Invalid status transitions are rejected.
- [ ] Customer can reopen an owned resolved ticket.
- [ ] Closed tickets cannot receive new messages.

### Multi-Tenant Security

- [ ] Business A cannot access Business B ticket details.
- [ ] Cross-business ticket access returns 404.
- [ ] Customer cannot access another Customer's ticket.
- [ ] Business A cannot access Business B message history.
- [ ] Client-provided tenant IDs cannot override server authorization.

### WebSocket

- [ ] Valid authorized WebSocket connection succeeds.
- [ ] Missing token is rejected.
- [ ] Invalid token is rejected.
- [ ] Refresh token is rejected for WebSocket authentication.
- [ ] Cross-business connection is rejected.
- [ ] Cross-customer unauthorized connection is rejected.
- [ ] Agent and Customer messages are delivered in real time.
- [ ] Messages are persisted before broadcasting.
- [ ] Status changes are broadcast after persistence.
- [ ] Closed tickets reject new messages.
- [ ] Admin message sending is rejected according to the selected architecture decision.

### Frontend Integration

- [ ] Frontend handles standard response envelopes.
- [ ] Frontend handles API errors.
- [ ] Access token is attached to authenticated requests.
- [ ] Refresh flow works without an infinite retry loop.
- [ ] Protected pages redirect to login when necessary.
- [ ] WebSocket resources are cleaned up.
- [ ] Chat displays new messages without manual refresh.
- [ ] Ticket status updates without manual refresh.

---

## 19. Contract Change Policy

Any change to this API contract must:

1. Be consistent with the original assessment.
2. Be reviewed against `docs/REQUIREMENTS.md`.
3. Preserve security invariants.
4. Update affected request and response schemas.
5. Update frontend API clients.
6. Update backend route and service implementations.
7. Update relevant tests.
8. Be documented when it introduces an engineering trade-off.

Do not silently change public API behavior.

If a contract decision is unresolved, document the assumption before implementation.

---

## 20. Definition of Done

The API contract is considered implemented when:

- [ ] All mandatory REST endpoints function.
- [ ] REST request and response schemas match this document.
- [ ] JWT authentication works correctly.
- [ ] Backend role authorization is enforced.
- [ ] Backend tenant isolation is enforced.
- [ ] Unauthorized resources remain inaccessible.
- [ ] Ticket lifecycle rules are enforced.
- [ ] WebSocket authentication and authorization work.
- [ ] Messages are persisted and delivered in real time.
- [ ] Status updates are broadcast in real time.
- [ ] Standard JSON error responses are implemented.
- [ ] Relevant API integration tests pass.
- [ ] FastAPI OpenAPI documentation reflects the implemented REST endpoints.
- [ ] Frontend and backend use consistent data types and event schemas.

**Final Principle:** The backend is the authority for identity, permissions, tenant membership, ticket state, and message persistence.

Frontend behavior must follow the backend contract and must never replace backend security enforcement.
