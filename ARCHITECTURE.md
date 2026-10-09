# ARCHITECTURE.md

# HelpDesk Mini - System Architecture

## 1. Overview

HelpDesk Mini is a multi-tenant ticketing system built with Next.js, FastAPI, and PostgreSQL.

The application enables customers to create support tickets and communicate with business agents through real-time WebSocket chat.

One platform serves multiple businesses, while each business maintains isolated users, tickets, and conversations.

### Architecture Goals

1. Enforce strict multi-tenant isolation.
2. Implement secure JWT authentication.
3. Provide role-based authorization.
4. Support reliable ticket management.
5. Enable real-time chat communication.
6. Maintain clean and testable code.
7. Keep the implementation simple enough for the assessment timeline.

**Architecture Style:** Modular Monolith

**Primary Principle:** Security and correctness before additional features.

---

## 2. Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js App Router | Routing and user interface |
| Language | TypeScript | Type safety |
| Styling | Tailwind CSS | Responsive UI |
| Data Fetching | TanStack Query | API server-state management |
| Backend | Python 3.11+ | Application runtime |
| API Framework | FastAPI | REST API and WebSocket |
| Validation | Pydantic | Request/response schemas |
| ORM | SQLAlchemy | Database operations |
| Migration | Alembic | Database schema versioning |
| Database | PostgreSQL | Persistent relational storage |
| Authentication | JWT | Access and refresh tokens |
| Password Hashing | Argon2 | Secure password storage |
| Real-time | FastAPI WebSocket | Live ticket communication |
| Testing | pytest | Backend unit and integration tests |

Docker Compose is optional and may be added after mandatory features are complete.

---

## 3. High-Level Architecture

The system consists of three primary components:

1. Next.js frontend.
2. FastAPI backend.
3. PostgreSQL database.

System flow:

    CUSTOMER / AGENT / ADMIN
               |
               v
       NEXT.JS FRONTEND
       - App Router
       - React Components
       - TanStack Query
       - Authentication UI
       - WebSocket Client
               |
          HTTPS / WSS
               |
               v
         FASTAPI BACKEND
       +-------------------+
       | REST API Routers  |
       | Auth Dependencies |
       | Role Authorization|
       | Tenant Isolation  |
       | Business Services |
       | WebSocket Manager |
       +-------------------+
               |
          SQLAlchemy
               |
               v
          POSTGRESQL
       +-------------------+
       | businesses        |
       | users             |
       | tickets           |
       | messages          |
       +-------------------+

### Communication

**HTTP REST API**

Used for:

- Registering businesses.
- Authentication and token refresh.
- User management.
- Ticket creation and retrieval.
- Ticket assignment and status updates.
- Loading message history.

**WebSocket**

Used for:

- Sending and receiving messages.
- Broadcasting ticket status changes.
- Updating active ticket conversations without refreshing.

The backend is the authority for authentication, authorization, tenant isolation, and business rules.

The frontend must never be trusted to enforce security independently.

---

## 4. Repository Architecture

Repository structure:

    helpdesk-mini/
    ├── AGENTS.md
    ├── ARCHITECTURE.md
    ├── README.md
    ├── .gitignore
    ├── .env.example
    │
    ├── docs/
    │   ├── REQUIREMENTS.md
    │   ├── SECURITY.md
    │   └── API_CONTRACT.md
    │
    ├── exec-plans/
    │   ├── active/
    │   └── completed/
    │
    ├── frontend/
    │   ├── src/
    │   │   ├── app/
    │   │   ├── components/
    │   │   ├── features/
    │   │   ├── hooks/
    │   │   ├── lib/
    │   │   └── types/
    │   └── package.json
    │
    └── backend/
        ├── app/
        │   ├── main.py
        │   ├── api/
        │   ├── core/
        │   ├── db/
        │   ├── models/
        │   ├── schemas/
        │   ├── services/
        │   └── websocket/
        ├── alembic/
        ├── tests/
        ├── scripts/
        ├── alembic.ini
        └── pyproject.toml

The structure is a target layout. Subdirectories should be created as needed, not populated with unnecessary placeholder files.

---

## 5. Backend Architecture

The backend follows a layered modular monolith pattern.

### 5.1 API Layer

Location: `backend/app/api/`

Responsibilities:

- Register REST endpoints.
- Validate incoming requests.
- Resolve authentication dependencies.
- Enforce role requirements.
- Delegate business operations to services.
- Return consistent HTTP responses.

API routers should remain thin.

Do not implement substantial business logic directly inside route handlers.

### 5.2 Service Layer

Location: `backend/app/services/`

Responsibilities:

- Implement application business rules.
- Apply ticket lifecycle rules.
- Validate user and agent relationships.
- Enforce resource-level permissions.
- Coordinate database operations.
- Handle transaction boundaries.

Suggested services:

- `auth_service.py`
- `user_service.py`
- `ticket_service.py`
- `message_service.py`

For protected ticket operations, service methods must apply tenant and ownership checks.

### 5.3 Model Layer

Location: `backend/app/models/`

Responsibilities:

- Define SQLAlchemy entities.
- Define database relationships.
- Define constraints and indexes.

Models represent persistence structures, not public API responses.

### 5.4 Schema Layer

Location: `backend/app/schemas/`

Responsibilities:

- Define Pydantic input schemas.
- Validate request payloads.
- Define typed API responses.
- Prevent sensitive fields from being returned.

Password hashes must never appear in public response schemas.

### 5.5 Core Layer

Location: `backend/app/core/`

Responsibilities:

- Environment configuration.
- JWT creation and validation.
- Password hashing and verification.
- Shared security configuration.

### 5.6 Database Layer

Location: `backend/app/db/`

Responsibilities:

- Database engine configuration.
- SQLAlchemy session lifecycle.
- Transaction management infrastructure.

Services must coordinate related database writes within appropriate transactions.

---

## 6. Multi-Tenant Architecture

### 6.1 Tenancy Model

The application uses a shared-database, shared-schema multi-tenant model.

Each business is identified by a unique `business_id`.

Every user belongs to exactly one business.

Tickets include a direct `business_id` reference.

Messages inherit their tenant scope through their associated ticket.

### 6.2 Tenant Isolation

The authenticated user's business must be derived from verified server-side authentication context.

Protected ticket queries must include tenant filtering.

Example:

    SELECT *
    FROM tickets
    WHERE id = :ticket_id
      AND business_id = :current_business_id;

Customer access requires an additional ownership check:

    customer_id = :current_user_id

### 6.3 Tenant Security Rules

- Business A cannot access Business B data.
- Customers cannot access other customers' tickets.
- Agents cannot assign tickets to agents from another business.
- Admins cannot create users in another business.
- Unauthorized ticket access returns HTTP 404.
- Tenant filtering is mandatory for ticket and message queries.
- WebSocket connections must enforce equivalent authorization.

Never derive trusted tenant identity from request body parameters.

### 6.4 Authorization Model

| Action | Admin | Agent | Customer |
|---|---|---|---|
| Create business | Public | Public | Public |
| Manage business users | Yes | No | No |
| View all business tickets | Yes | Yes | No |
| Create ticket | No | No | Yes |
| View own ticket | Yes | Yes | Yes |
| Assign agent | Yes | Self only | No |
| Update normal ticket status | Yes | Yes | No |
| Reopen resolved ticket | No | No | Own ticket |
| Send chat messages | No* | Yes | Own ticket |
| View permitted chat history | Yes | Yes | Own ticket |

*Implementation decision: Admins can inspect conversations but do not send messages. The assessment does not explicitly grant chat-sending permission to the Admin role. This restriction can be clarified with the reviewer.

All permissions are enforced in FastAPI, regardless of UI visibility.

---

## 7. Authentication Architecture

Authentication uses JWT access and refresh tokens.

### 7.1 Login Flow

    User submits credentials
              |
              v
       POST /auth/login
              |
              v
      Find user by email
              |
              v
      Verify password hash
              |
              v
       Generate JWT tokens
              |
              v
        Return credentials
              |
              v
       Frontend authenticated

### 7.2 Token Strategy

Access token:

- Short-lived JWT.
- Used for authenticated REST requests.
- Used to establish authorized WebSocket connections.
- Contains user identity and token type.
- May contain business and role claims.

Refresh token:

- Longer-lived JWT.
- Used only for refreshing authentication.
- Has a distinct token type.
- Must never authorize ordinary protected endpoints.

JWT validation must include:

- Signature.
- Expiration.
- Expected token type.
- Required claims.

Authorization must use trusted authentication context and current database state where necessary.

### 7.3 Frontend Token Handling

Selected implementation approach:

- Keep access tokens in memory.
- Use an HttpOnly cookie for persistent refresh-token handling.
- Use `SameSite=Lax` for the selected same-site setup.
- Scope the cookie to `Path=/auth/refresh`.
- Use `Secure=true` over HTTPS and `Secure=false` only for local HTTP development.
- Do not persist refresh tokens in localStorage.
- Automatically attempt refresh when appropriate.
- Redirect to `/login` when authentication cannot be restored.

The login API must still satisfy the assessment requirement to return access and refresh tokens. The frontend should avoid persisting the returned refresh-token body.

Cross-origin cookie handling and CORS must be explicitly configured when frontend and backend have different origins.

Future genuinely cross-site cookie deployments require `SameSite=None`, HTTPS, and appropriate CSRF protection. API tools such as Postman can exercise refresh by retaining the login cookie in a cookie jar; JSON-body refresh is not part of the selected contract.

### 7.4 Password Security

Use Argon2 password hashing.

Rules:

- Never store plaintext passwords.
- Never return password hashes.
- Never log passwords or tokens.
- Never commit production secrets.

### 7.5 Authentication Limitations

For the initial MVP, JWT refresh tokens may be stateless.

Immediate server-side token revocation is not guaranteed without additional session or revocation storage.

Document this limitation in README.

---

## 8. Database Architecture

The minimum database contains four entities.

### 8.1 Businesses

Fields:

- `id`
- `name`
- `slug`
- `created_at`

Constraints:

- Unique `slug`.

### 8.2 Users

Fields:

- `id`
- `business_id`
- `name`
- `email`
- `password_hash`
- `role`
- `created_at`

Constraints:

- Globally unique `email`.
- Required business foreign key.
- Role restricted to `admin`, `agent`, or `customer`.

### 8.3 Tickets

Fields:

- `id`
- `business_id`
- `customer_id`
- `assigned_agent_id`
- `subject`
- `category`
- `priority`
- `status`
- `created_at`
- `updated_at`

Constraints:

- Required business and customer references.
- Nullable assigned agent.
- Valid priority and status values.
- Index `(business_id, status)`.

Validate that assigned agents and customers belong to the ticket's business.

### 8.4 Messages

Fields:

- `id`
- `ticket_id`
- `sender_id`
- `body`
- `created_at`

Constraints:

- Required ticket and sender references.
- Message sender must be authorized for the ticket.
- Message body must pass input validation.

Recommended index:

- `(ticket_id, created_at, id)`.

### 8.5 Entity Relationships

    businesses
       |
       | 1:N
       v
      users
       |
       | customer / agent references
       v
     tickets
       |
       | 1:N
       v
     messages

A business has many users and tickets.

A customer has many tickets.

A ticket has zero or one assigned agent.

A ticket has many messages.

A user may send many messages.

### 8.6 Data Integrity

- Use foreign keys.
- Use database constraints where appropriate.
- Use Alembic migrations.
- Store timestamps in UTC.
- Update ticket activity timestamp when messages arrive or ticket state changes.
- Persist ticket creation and the first message atomically.
- Never manually modify production schemas outside migrations.

---

## 9. Ticket Management Architecture

### 9.1 Ticket Creation

Customer provides:

- Subject.
- Category.
- Priority.
- First message.

Backend workflow:

1. Authenticate customer.
2. Verify customer role.
3. Validate request data.
4. Derive `business_id` from authenticated context.
5. Create ticket.
6. Create initial message.
7. Commit both records atomically.
8. Return created ticket.

If either database operation fails, roll back the transaction.

### 9.2 Ticket Status Lifecycle

Allowed statuses:

    open
      |
      v
    in_progress
      |
      v
    resolved
      |
      v
    closed

Allowed reopen transition:

    resolved -> open

Transition rules:

- Agent or Admin can perform authorized normal transitions.
- Customer can reopen only their own resolved ticket.
- Closed is terminal.
- Closed tickets cannot receive new messages.
- Invalid transitions must be rejected.

### 9.3 Ticket Assignment

Admin:

- May assign tickets to Agents within the same business.

Agent:

- May take a ticket by assigning themselves.
- Cannot assign another agent.

Customer:

- Cannot modify agent assignments.

Concurrent assignment attempts should be handled safely through a conditional database update or equivalent transaction control.

### 9.4 Ticket Listing

Listing rules:

- Admin and Agent see tickets from their business.
- Customer sees only their tickets.
- Support filtering by status.
- Sort by `updated_at` descending.

---

## 10. WebSocket Architecture

### 10.1 Connection Endpoint

    /ws/tickets/{ticket_id}?token={access_token}

Each ticket acts as a separate WebSocket room.

### 10.2 Connection Lifecycle

    WebSocket request
           |
           v
     Validate JWT
           |
           v
    Resolve current user
           |
           v
   Verify tenant and role
           |
           v
    Verify ticket access
           |
           v
    Accept connection
           |
           v
      Join ticket room

If any authorization check fails, reject the WebSocket connection before joining the room.

### 10.3 Message Flow

    Customer Browser
           |
           | WebSocket event
           v
        FastAPI
           |
           v
     Validate sender
           |
           v
     Verify ticket status
           |
           v
    Save message to DB
           |
           v
     Commit transaction
           |
           v
    Broadcast saved message
           |
           v
       Agent Browser

Never broadcast an uncommitted message as successfully persisted.

### 10.4 Event Contracts

Suggested client-to-server event:

    {
      "type": "message.send",
      "body": "Hello, I need help."
    }

Suggested server-to-client event:

    {
      "type": "message.created",
      "data": {
        "id": "message-id",
        "ticket_id": "ticket-id",
        "sender_id": "user-id",
        "sender_name": "Customer",
        "sender_role": "customer",
        "body": "Hello, I need help.",
        "created_at": "ISO-8601 timestamp"
      }
    }

Status-change event:

    {
      "type": "ticket.status_changed",
      "data": {
        "ticket_id": "ticket-id",
        "status": "resolved"
      }
    }

These are implementation contracts proposed for the project, not predefined payloads from the assessment.

Final event names and schemas must be documented consistently in `docs/API_CONTRACT.md`.

### 10.5 WebSocket Security

- Validate authentication before accepting connections.
- Verify ticket-level access.
- Derive sender identity from authenticated context.
- Never accept client-supplied `sender_id` as authoritative.
- Reject messages to closed tickets.
- Validate payload types and sizes.
- Validate permitted connection origins.
- Recheck authorization for sensitive operations.
- Do not log query-string JWTs.

Use WSS in deployed HTTPS environments.

### 10.6 Connection Manager

Use a lightweight in-memory connection manager for the MVP.

Responsibilities:

- Register connections by ticket.
- Remove disconnected clients.
- Broadcast events to active ticket participants.
- Handle disconnected or failed connections safely.

**Limitation:** In-memory connection management only supports broadcasting within one backend process.

Multi-process deployments would require shared messaging infrastructure.

Redis or another broker is intentionally excluded from the initial scope.

---

## 11. Frontend Architecture

Use feature-oriented organization.

Suggested structure:

    frontend/src/
    ├── app/
    │   ├── login/
    │   ├── register/
    │   ├── tickets/
    │   │   ├── new/
    │   │   └── [id]/
    │   └── admin/
    │       └── users/
    │
    ├── components/
    │   └── ui/
    │
    ├── features/
    │   ├── auth/
    │   ├── tickets/
    │   ├── chat/
    │   └── users/
    │
    ├── hooks/
    ├── lib/
    │   ├── api/
    │   └── auth/
    └── types/

### 11.1 Routing

Required routes:

| Route | Purpose |
|---|---|
| `/login` | User login |
| `/register` | Business registration |
| `/tickets` | Ticket list |
| `/tickets/new` | Create ticket |
| `/tickets/[id]` | Ticket details and live chat |
| `/admin/users` | Business user management |

### 11.2 Server State

Use TanStack Query for:

- Authenticated user profile.
- Ticket listing.
- Ticket details.
- Message history.
- User listing.

Use local component state for:

- Form inputs.
- Open dialogs.
- UI-only interactions.

Do not duplicate server-state data unnecessarily.

### 11.3 WebSocket Integration

Use a dedicated chat hook or service.

Responsibilities:

- Establish connections after authentication.
- Handle incoming events.
- Update relevant TanStack Query cache.
- Manage connection status.
- Clean up connections.
- Handle reconnects when appropriate.

Avoid opening multiple connections for the same mounted ticket view.

On reconnect, refetch authoritative message history to recover missed events.

### 11.4 Authentication UX

- Redirect unauthenticated users to `/login`.
- Prevent unauthorized action controls from rendering.
- Handle token expiration.
- Show loading and error states.

Frontend role checks improve UX but do not replace backend authorization.

### 11.5 UI Priorities

Prioritize:

1. Working user flows.
2. Readable ticket information.
3. Responsive layout.
4. Clear loading and error states.
5. Reliable chat behavior.

Do not build analytics dashboards, complex animations, or unrelated pages for the MVP.

---

## 12. API Architecture

API routes are grouped by domain.

### Authentication

- `POST /auth/register-business`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

### Users

- `GET /users`
- `POST /users`

### Tickets

- `GET /tickets`
- `POST /tickets`
- `GET /tickets/{id}`
- `PATCH /tickets/{id}`
- `GET /tickets/{id}/messages`

### WebSocket

- `WS /ws/tickets/{id}`

Use FastAPI OpenAPI documentation.

The exact request/response schemas and authorization requirements must be defined in `docs/API_CONTRACT.md`.

### HTTP Status Conventions

| Status | Meaning |
|---|---|
| 200 | Successful request |
| 201 | Resource created |
| 401 | Authentication required or invalid |
| 403 | Role or operation not permitted |
| 404 | Resource missing or inaccessible |
| 422 | Invalid request data |
| 500 | Unexpected internal failure |

Do not expose internal stack traces or secrets in public responses.

Use a consistent JSON error structure.

---

## 13. Testing Architecture

Tests are organized by behavior and security boundary.

Suggested backend tests:

    backend/tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_users.py
    ├── test_tenant_isolation.py
    ├── test_tickets.py
    ├── test_ticket_status.py
    └── test_websocket.py

### Critical Integration Tests

- Cross-business ticket access returns 404.
- Same-business customer ownership is enforced.
- Cross-business ticket listing returns no data.
- Agent assignment is restricted to the correct business.
- Customer cannot perform Admin operations.
- Invalid JWTs are rejected.
- Refresh tokens cannot act as access tokens.
- Unauthorized WebSocket connections are rejected.
- Cross-tenant WebSocket connections are rejected.
- Closed tickets reject new messages.
- Invalid status transitions are rejected.
- Ticket creation persists the first message.
- Password hashes are not exposed.
- Message history remains available after reconnect.

Security-critical scenarios must be prioritized before optional feature tests.

---

## 14. Environment and Configuration

Use environment variables for configuration.

Suggested variables:

**Backend**

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ORIGINS`

**Frontend**

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_WS_URL`

Never store actual secrets inside source code.

Commit `.env.example`, not `.env`.

Validate required environment variables on application startup.

---

## 15. Deployment Architecture

Deployment is optional for the assessment.

The initial application must run locally without requiring paid cloud infrastructure.

A possible deployment:

- Next.js hosted on Vercel.
- FastAPI hosted on a WebSocket-capable Python service.
- PostgreSQL hosted on a managed database.

Requirements for deployment:

- HTTPS and WSS.
- Correct CORS and cookie configuration.
- Secure secrets.
- Database migrations.
- Persistent PostgreSQL storage.
- WebSocket-compatible hosting.

For the MVP, keep a single backend process when using an in-memory WebSocket manager.

Multi-instance scaling is out of scope.

---

## 16. Architecture Decisions and Trade-offs

### Decision 1: Modular Monolith

**Reason:** Small application scope and limited implementation time.

**Trade-off:** Components share a deployment boundary, but complexity stays manageable.

### Decision 2: Shared PostgreSQL Database

**Reason:** Simple relational structure with tenant isolation through business identifiers.

**Trade-off:** Every protected query must consistently enforce tenant boundaries.

### Decision 3: FastAPI Native WebSocket

**Reason:** Built-in asynchronous WebSocket support without introducing additional infrastructure.

**Trade-off:** Single-process broadcasting unless a shared broker is added later.

### Decision 4: TanStack Query

**Reason:** Centralized asynchronous server-state management and cache invalidation.

**Trade-off:** Adds an additional abstraction to the frontend.

### Decision 5: JWT Authentication

**Reason:** Required by the assessment and suitable for stateless API authentication.

**Trade-off:** Stateless refresh tokens do not support immediate revocation without additional storage.

### Decision 6: Authorization in Backend Services

**Reason:** Prevents unauthorized access regardless of frontend behavior.

**Trade-off:** Service boundaries must be consistently followed.

### Decision 7: Minimal Infrastructure

**Reason:** Mandatory features are more valuable than unnecessary production infrastructure in this assessment.

**Trade-off:** Advanced scalability and observability are deferred.

---

## 17. Known Assumptions

The following are implementation decisions rather than explicit assessment requirements:

1. Admins can view but not send chat messages.
2. Access tokens are held in frontend memory.
3. Refresh tokens are supported through HttpOnly cookies.
4. Initial WebSocket connection management is in-memory.
5. Timestamps are stored in UTC.
6. Closed tickets are terminal.
7. Additional infrastructure is deferred until mandatory functionality works.

Any conflicting interpretation must be recorded and resolved in the implementation plan.

Do not silently alter these decisions.

---

## 18. Implementation Milestones

| Milestone | Scope |
|---|---|
| M0 | Harness, documentation, project foundation |
| M1 | Database models and Alembic migrations |
| M2 | JWT authentication and business user management, with Admin-only and own-business enforcement on user endpoints |
| M3 | Comprehensive multi-tenant authorization audit, strengthening, and isolation tests; not the first introduction of authorization |
| M4 | Ticket management |
| M5 | WebSocket real-time chat |
| M6 | Next.js frontend |
| M7 | Testing, seed data, README, and demo |

Only one milestone should be implemented at a time.

Each milestone must define acceptance criteria and relevant tests.

Do not proceed automatically when validation fails.

---

## 19. Architecture Constraints

The following must not be introduced without a justified change:

- Microservices.
- Kubernetes.
- Kafka or RabbitMQ.
- Redis-based event infrastructure.
- Unnecessary caching layers.
- Distributed transactions.
- Advanced analytics modules.
- Additional business domains.
- Premature infrastructure abstractions.

Architecture changes must be documented and consistent with the assessment requirements.

---

## 20. Definition of Architectural Success

The architecture is successful when:

1. Users authenticate securely.
2. Each business has isolated data.
3. Roles and resource permissions are enforced by the backend.
4. Customers create and manage permitted tickets.
5. Agents and Admins perform their authorized operations.
6. Chat messages persist and update in real time.
7. Unauthorized WebSocket connections are rejected.
8. Database migrations execute correctly.
9. Critical security tests pass.
10. The application is understandable, maintainable, and runnable by a reviewer.

**Final Principle: Build the simplest secure architecture that satisfies every mandatory assessment requirement.**
