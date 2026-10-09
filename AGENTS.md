# AGENTS.md
# HelpDesk Mini | Engineering Agent Instructions

## 1. Project Overview

HelpDesk Mini is a multi-tenant ticketing application where customers create support tickets and business staff communicate through real-time chat.

The platform supports multiple businesses. Each business has its own users, tickets, and messages.

**Primary objective:** Deliver a secure, functional, and maintainable application that satisfies the SVO Connect Junior Developer technical assessment.

**Core requirements:**
1. JWT authentication with access and refresh tokens.
2. Role-based access control (RBAC).
3. Strict multi-tenant data isolation.
4. Ticket management and controlled status transitions.
5. Real-time WebSocket chat.
6. Persistent message history.
7. Responsive Next.js frontend.

Security, correctness, and mandatory features take priority over UI polish and bonus functionality.

## 2. Technology Stack

### Frontend
- Next.js App Router
- TypeScript
- Tailwind CSS
- TanStack Query

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

### Database
- PostgreSQL

### Authentication
- JWT access and refresh tokens
- Argon2 or bcrypt password hashing

### Real-Time Communication
- Native FastAPI WebSocket

### Development
- Git and GitHub
- pytest
- Docker Compose (optional bonus)

Do not introduce additional technologies without a clear requirement or documented technical justification.

## 3. Source of Truth

Read the relevant project documentation before making changes.

Priority order:

1. Original SVO Connect technical assessment.
2. `docs/REQUIREMENTS.md`
3. `docs/SECURITY.md`
4. `ARCHITECTURE.md`
5. `docs/API_CONTRACT.md`
6. Active milestone in `exec-plans/active/`
7. Existing implementation and tests.

If instructions conflict, do not silently choose an interpretation.

Report the conflict and propose the smallest compliant resolution.

Do not invent requirements.

If a specification is ambiguous, document the assumption before implementation.

## 4. Repository Structure

Expected structure:

```text
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
│
└── backend/
```

Preserve this structure unless a change is justified.

Keep documentation concise and avoid duplicating information across files.

## 5. Architecture Principles

Use a modular monolith.

### Backend responsibilities

- Router: HTTP routing, request parsing, response handling.
- Service: Business rules and application workflows.
- Model: SQLAlchemy database entities.
- Schema: Pydantic request and response validation.
- Dependency: Authentication, database sessions, and authorization.
- WebSocket: Authenticated connection management and real-time events.

Keep database and authorization logic out of frontend components.

Do not introduce microservices, message brokers, or unnecessary infrastructure.

### Frontend responsibilities

- App Router for routing.
- Reusable UI components.
- Typed API client.
- TanStack Query for server-state management.
- Dedicated authentication handling.
- Dedicated WebSocket connection lifecycle.
- Explicit loading, error, and empty states.

Avoid unnecessary global state and premature abstractions.

## 6. Security Invariants

These rules are mandatory and must never be bypassed.

### 6.1 Multi-Tenant Isolation

Every user belongs to exactly one business.

Tickets and their related messages must be accessible only within the authenticated user's business.

For ticket access, always enforce:

- `ticket.business_id == current_user.business_id`
- Customer ownership where applicable.
- Required role permissions.

Never trust a client-provided `business_id` for authorization.

Never query a protected ticket by ID alone without applying tenant isolation.

A ticket belonging to another business must return HTTP 404.

A customer must not access another customer's ticket, even within the same business.

Apply the same authorization rules to WebSocket connections.

### 6.2 Role-Based Access

Roles:

**Admin**
- Manage users in their business.
- View all business tickets.
- Assign tickets to agents.
- Update ticket status.

**Agent**
- View all business tickets.
- Assign tickets to themselves.
- Send messages.
- Update ticket status.

**Customer**
- Create tickets.
- View their own tickets.
- Send messages in their own tickets.
- Reopen their own resolved tickets.

Frontend visibility restrictions are not security controls.

Every protected backend operation must enforce authorization.

### 6.3 Authentication

- Hash all passwords using an approved password hashing algorithm.
- Never store plaintext passwords.
- Never return password hashes in API responses.
- Validate JWT signature, expiration, and token type.
- Refresh tokens must not be accepted as access tokens.
- Protect authenticated endpoints.
- Reject invalid or expired authentication.
- Never commit actual credentials, JWT secrets, or environment files.
- Use secure token storage and handling practices.

### 6.4 WebSocket Authorization

Before accepting a WebSocket connection:

1. Validate the provided token.
2. Identify the authenticated user.
3. Verify the requested ticket exists within the user's business.
4. Verify role and customer ownership permissions.
5. Reject unauthorized connections.

Validate permissions again before processing sensitive operations.

Closed tickets must reject new messages.

Do not rely exclusively on frontend WebSocket validation.

## 7. Database Rules

Minimum required tables:

- `businesses`
- `users`
- `tickets`
- `messages`

Requirements:

- `businesses.slug` must be unique.
- `users.email` must be globally unique.
- Every user must reference exactly one business.
- Tickets must store `business_id`.
- Tickets must reference their customer.
- Assigned agent may be nullable.
- Messages must reference their ticket and sender.
- Add an index on `(business_id, status)` for tickets.
- Use foreign keys and appropriate constraints.
- Create and modify schemas through Alembic migrations.

Do not modify database schemas manually.

Validate that related users and tickets belong to the correct business.

Creating a ticket and its first message must be atomic.

## 8. Ticket Business Rules

Allowed priorities:

- `low`
- `medium`
- `high`

Allowed statuses:

- `open`
- `in_progress`
- `resolved`
- `closed`

Normal transitions:

```text
open -> in_progress -> resolved -> closed
```

Reopen transition:

```text
resolved -> open
```

Rules:

- Customers may reopen only their own resolved tickets.
- Closed tickets cannot be reopened.
- Closed tickets cannot receive new messages.
- Reject invalid status transitions.
- Validate agent assignment against business membership and role.
- Ticket lists must support status filtering.
- Ticket lists must be ordered by latest activity.

Do not allow unrestricted status updates.

## 9. Real-Time Rules

Each ticket represents one chat room.

Mandatory behavior:

- Authenticated WebSocket connections.
- Ticket-level access verification.
- Persist messages in PostgreSQL.
- Broadcast new messages to authorized room participants.
- Broadcast ticket status changes.
- Load message history when opening a ticket.
- Display sender name, role, and timestamp.
- Prevent sending messages to closed tickets.

The database is the source of truth for messages.

Never consider a message successfully stored solely because a WebSocket event was emitted.

For the initial implementation, an in-memory connection manager is acceptable for a single backend process.

Document this limitation if used.

## 10. API Conventions

Use REST conventions and consistent JSON responses.

Required HTTP status behavior:

- `401`: Missing or invalid authentication.
- `403`: Authenticated user lacks permission.
- `404`: Resource does not exist or is inaccessible across tenant boundaries.
- `422`: Invalid input.

Do not expose internal exceptions or sensitive information to API consumers.

Maintain accurate OpenAPI documentation.

Prefer explicit request and response schemas.

Do not expose SQLAlchemy models directly as API contracts.

## 11. Frontend Requirements

Mandatory routes:

- `/login`
- `/register`
- `/tickets`
- `/tickets/new`
- `/tickets/[id]`
- `/admin/users`

Requirements:

- Redirect unauthenticated users to `/login`.
- Handle expired tokens correctly.
- Hide actions unavailable to the current role.
- Display clear loading and error states.
- Support responsive mobile layouts.
- Show real-time messages without manual refresh.
- Display current ticket status and assigned agent.
- Prevent unnecessary WebSocket connections.
- Clean up WebSocket connections during component unmount.

Do not prioritize decorative UI features over working business flows.

## 12. Testing Requirements

Use pytest for backend tests.

Prioritize critical security and functional behavior.

Minimum critical scenarios:

1. Business A cannot access Business B tickets.
2. Customers cannot access other customers' tickets.
3. Unauthorized roles cannot manage users.
4. Unauthorized roles cannot assign agents.
5. Cross-tenant agent assignments are rejected.
6. Invalid authentication is rejected.
7. Invalid WebSocket connections are rejected.
8. Cross-tenant WebSocket connections are rejected.
9. Closed tickets reject new messages.
10. Invalid status transitions are rejected.
11. Password hashes are never returned.
12. Ticket creation persists the first message.
13. Refresh tokens cannot authenticate access-only operations.
14. WebSocket messages persist and are broadcast correctly.

Use deterministic test data.

Do not claim tests passed unless they were actually executed.

If tests cannot run, report the exact blocker.

## 13. Agent Execution Workflow

Follow this workflow for every implementation task.

### Step 1: Inspect

Read only the documentation and source files relevant to the requested task.

Identify existing implementations before creating new ones.

Do not assume a file or feature is missing without checking.

### Step 2: Plan

For non-trivial changes, provide a short plan describing:

- Objective.
- Relevant files.
- Implementation approach.
- Security considerations.
- Verification steps.

Avoid unnecessary planning for trivial changes.

### Step 3: Implement

- Work on one milestone at a time.
- Make the smallest complete change.
- Follow existing naming conventions.
- Reuse existing utilities.
- Avoid unrelated refactoring.
- Avoid unnecessary dependencies.
- Do not silently change API contracts.
- Do not modify unrelated files.

### Step 4: Validate

Run relevant checks depending on the change:

**Backend**
- Syntax/import validation.
- Relevant pytest tests.
- Migration verification when applicable.

**Frontend**
- TypeScript type checking.
- Linting.
- Build validation when appropriate.

**Security**
- Authorization checks.
- Tenant isolation checks.
- Secret exposure checks where applicable.

Do not report unexecuted checks as successful.

### Step 5: Report

Respond concisely using:

```text
Summary:
- ...

Files changed:
- ...

Validation:
- PASS / FAIL / NOT RUN

Security impact:
- ...

Known limitations:
- ...

Next step:
- ...
```

Stop after completing the requested task.

Do not automatically begin the next milestone.

## 14. Milestone Execution

Project milestones:

- M0: Harness and project foundation.
- M1: Database models and migrations.
- M2: JWT authentication and user management.
- M3: Multi-tenant authorization.
- M4: Ticket management.
- M5: WebSocket chat.
- M6: Frontend implementation.
- M7: Testing, documentation, seed data, and demo preparation.

Before starting a milestone:

1. Read its active execution plan.
2. Identify prerequisites.
3. Confirm dependencies are implemented.
4. Follow acceptance criteria.

After completing a milestone:

1. Run relevant validation.
2. Summarize implementation results.
3. Record known limitations.
4. Wait for review before proceeding.

Do not move incomplete milestones into `completed/`.

## 15. Definition of Done

A task is complete only when:

- Requested requirements are implemented.
- Relevant authorization checks are present.
- Tenant isolation is preserved.
- Relevant validation has passed.
- No known critical security issue remains.
- Existing behavior is not unintentionally broken.
- Documentation is updated when necessary.
- Results and limitations are reported accurately.

An incomplete task must not be presented as complete.

## 16. Scope and Time Constraints

The assessment has a five-calendar-day completion window and an estimated workload of 15 to 20 hours.

Priorities:

**P0: Mandatory**
- Authentication.
- Multi-tenant isolation.
- Role authorization.
- Ticket management.
- Real-time chat.
- Required frontend pages.
- Required submission deliverables.

**P1: Quality**
- Critical tests.
- Clean architecture.
- Database integrity.
- Reliable error handling.
- Documentation and demo readiness.

**P2: Optional Bonuses**
- Docker Compose.
- Typing indicators.
- Read receipts.
- Unread message badges.
- Attachments.
- Pagination and search.
- Real-time ticket notifications.
- Login rate limiting.
- Deployment.

Do not implement P2 features while mandatory functionality remains incomplete.

## 17. Delivery Requirements

The repository must include:

- `frontend/` and `backend/`.
- README setup instructions.
- Environment variable documentation.
- `.env.example` without real secrets.
- Alembic migrations.
- Seed data for two businesses.
- One Admin, one Agent, and two Customers per business.
- Demo account information.
- Technical decisions and trade-offs.
- Known limitations.
- Meaningful Git commit history.

The final demo must demonstrate:

1. Customer and Agent real-time chat in two browsers.
2. Agent updating ticket status.
3. Business A failing to access a Business B ticket.

Do not include real credentials in the repository.

## 18. Prohibited Behavior

The coding agent must not:

- Invent requirements.
- Ignore tenant isolation.
- Trust client-side authorization.
- Store plaintext passwords.
- Expose credentials.
- Add unnecessary infrastructure.
- Rewrite unrelated modules without justification.
- Claim tests passed without executing them.
- Hide failures or implementation limitations.
- Implement unrelated bonus features.
- Automatically advance through milestones.
- Generate large amounts of speculative code.

## 19. Final Engineering Principle

Build the simplest implementation that fully satisfies the technical assessment.

Prioritize security, correctness, readability, testability, and explainability.

Every important implementation decision must be understandable during the technical review.

**A smaller, verified solution is preferable to a larger, unverified solution.**