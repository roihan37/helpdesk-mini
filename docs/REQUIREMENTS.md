# HelpDesk Mini - Requirements Specification

**Project:** HelpDesk Mini - Multi-Business Ticketing Application  
**Assessment:** Junior Developer, SVO Connect  
**Original specification date:** October 7, 2026  
**Source:** `Test-Junior-Developer-HelpDesk-Mini.pdf`, pages 1-7  
**Document status:** Requirements baseline for implementation and review

## 1. Purpose and Scope

Build a multi-tenant helpdesk application in which customers create complaint tickets and business staff respond through real-time chat. One platform serves multiple businesses, and each business can have multiple users. A ticket acts as a chat room. Data belonging to one business must not be visible to another business.

The assessment primarily evaluates authentication, multi-tenant data modeling and isolation, and real-time communication between a Next.js frontend and a Python backend.

**Requirement labels**
- **MUST:** Mandatory in the original assessment.
- **BONUS:** Optional; only counted after all mandatory features work.
- **DECISION:** Engineering choice or clarification, not a mandatory requirement from the assessment.

Requirement IDs are local traceability identifiers for the project. They are not IDs assigned by SVO Connect.

## 2. Required Technology and Project Constraints

| ID | Level | Requirement |
|---|---|---|
| TECH-01 | MUST | Use Next.js App Router with TypeScript for the frontend. |
| TECH-02 | MUST | Use Python 3.11 or later for the backend. |
| TECH-03 | MUST | Use a relational database. |
| TECH-04 | MUST | Create and change the database schema through migrations, not manual setup. |
| TECH-05 | MUST | Use JWT access and refresh tokens for authentication. |
| TECH-06 | MUST | Store passwords as secure hashes, never plaintext. |
| TECH-07 | MUST | Use WebSocket for real-time communication. |
| TECH-08 | MUST | Keep frontend and backend together in one repository, using `frontend/` and `backend/`. |

**Suggested in the assessment, not mandatory:** Tailwind CSS, React Query or SWR, FastAPI or Django + Channels, PostgreSQL (SQLite is allowed for development), SQLAlchemy or SQLModel with Alembic, bcrypt or Argon2, and FastAPI's built-in WebSocket. Docker Compose is a bonus.

**Current architecture decisions:** Next.js, TypeScript, Tailwind CSS, TanStack Query, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Argon2, and native FastAPI WebSocket. These are documented design selections; the original assessment allows alternatives for suggested technologies when justified in README.

## 3. Roles and Authorization

Each user belongs to **exactly one business** and has **exactly one role**.

| ID | Role | Mandatory permissions |
|---|---|---|
| ROLE-01 | Admin (Business Admin) | Manage users in their own business; view all tickets in that business; assign tickets to agents; change ticket status. |
| ROLE-02 | Agent | View all tickets in their business; take a ticket by assigning themselves; reply through chat; change ticket status. |
| ROLE-03 | Customer | Create tickets; view and chat only in their own tickets. |
| ROLE-04 | All | Access only data allowed by both their business membership and their role/ownership. |

The original assessment does **not explicitly specify whether Admin can send chat messages**. Do not treat either permission or prohibition as a source requirement without documenting the chosen assumption.

## 4. Authentication and User Management

| ID | Level | Acceptance requirement |
|---|---|---|
| AUTH-01 | MUST | Public business registration creates one business **and** its Business Admin account. |
| AUTH-02 | MUST | Users can log in with email and password. |
| AUTH-03 | MUST | Login returns an access token and a refresh token. |
| AUTH-04 | MUST | A refresh endpoint issues a new access token from a valid refresh token. |
| AUTH-05 | MUST | A `/me` endpoint returns the authenticated user and their business information. |
| AUTH-06 | MUST | An Admin can create Agent and Customer accounts **only in their own business**. |
| AUTH-07 | MUST | Passwords are hashed in storage and are never included in API responses. |
| AUTH-08 | MUST | Pages requiring authentication redirect to `/login` if there is no valid login session or usable token. |
| AUTH-09 | MUST | Email is globally unique across the platform: one email belongs to only one business. |

**Acceptance checks:** Registration persists the business and admin together; login and refresh function; unauthenticated requests are rejected; Admin-created users inherit the Admin's business; responses never reveal passwords or hashes.

## 5. Multi-Tenant Isolation and Security

| ID | Level | Acceptance requirement |
|---|---|---|
| SEC-01 | MUST | All ticket and message access is restricted by the authenticated user's `business_id` on the **backend**. |
| SEC-02 | MUST | A user from Business A requesting a Business B ticket by guessed ID receives **HTTP 404**, not ticket data. |
| SEC-03 | MUST | A Customer cannot open another Customer's ticket, even inside the same business. |
| SEC-04 | MUST | WebSocket connections to tickets the user is not entitled to access are rejected. |
| SEC-05 | MUST | Role permissions are enforced on the backend even if UI controls are hidden. |
| SEC-06 | MUST | Invalid or absent WebSocket authentication is rejected. |
| SEC-07 | MUST | No plaintext password is stored or returned. |
| SEC-08 | MUST | No real secrets or credentials are committed to the repository. |

**Important:** Tenant isolation applies to lists, details, changes, chat history, WebSocket connections, and message sending. A frontend-only filter is insufficient.

**DECISION:** Return 404 rather than revealing the existence of another Customer's ticket. The assessment explicitly requires 404 for cross-business guessed IDs; it requires denial of same-business cross-customer access but does not explicitly prescribe that case's status code.

## 6. Ticket Management

| ID | Level | Acceptance requirement |
|---|---|---|
| TICK-01 | MUST | A Customer can create a ticket with subject/title, category, priority, and first message. |
| TICK-02 | MUST | Supported priorities are `low`, `medium`, and `high`. |
| TICK-03 | MUST | Ticket creation persists the ticket and its first message. |
| TICK-04 | MUST | Customers list only their own tickets. |
| TICK-05 | MUST | Agents and Admins list all tickets in their own business. |
| TICK-06 | MUST | Ticket lists support filtering by `status`. |
| TICK-07 | MUST | Ticket lists are ordered by latest activity. |
| TICK-08 | MUST | Agents can take tickets by assigning themselves. |
| TICK-09 | MUST | Admins can assign tickets to selected Agents. |
| TICK-10 | MUST | Allowed statuses are `open`, `in_progress`, `resolved`, and `closed`. |
| TICK-11 | MUST | Standard lifecycle is `open -> in_progress -> resolved -> closed`. |
| TICK-12 | MUST | A Customer may reopen their own `resolved` ticket to `open`. |
| TICK-13 | MUST | Only a `resolved` ticket can be reopened; `closed` is terminal. |
| TICK-14 | MUST | Closed tickets cannot receive new chat messages. |

**Acceptance checks:** Unauthorized roles cannot create/assign/change tickets; assignment is limited to appropriate agents in the ticket's business; status filters and latest-activity sorting work; invalid status changes are rejected.

**DECISION:** For implementation, update `tickets.updated_at` whenever a new message or meaningful ticket update occurs, so sorting reflects latest activity. This mechanism is not prescribed in the original assessment.

## 7. Real-Time Chat

| ID | Level | Acceptance requirement |
|---|---|---|
| CHAT-01 | MUST | Each ticket is a separate chat room. |
| CHAT-02 | MUST | A newly sent message appears in the other active participant's browser without refreshing. |
| CHAT-03 | MUST | Message history is persisted in the relational database. |
| CHAT-04 | MUST | Opening a ticket loads its previous messages. |
| CHAT-05 | MUST | Each displayed message includes sender name, sender role, and sent timestamp. |
| CHAT-06 | MUST | WebSocket authentication uses the same authentication tokens as the application. |
| CHAT-07 | MUST | WebSocket connections without valid authorization are rejected. |
| CHAT-08 | MUST | Ticket status changes are broadcast in real time to clients viewing the ticket. |
| CHAT-09 | MUST | Closed tickets reject newly submitted messages. |

**Acceptance checks:** Customer and Agent use two browser sessions; each sees messages without refresh; reconnecting/reopening shows persisted history; status updates reach connected viewers; unauthorized WebSocket connections never receive protected data.

**DECISION:** Use an in-memory WebSocket connection manager in a single backend process for the MVP. The assessment does not require multi-instance WebSocket scaling.

## 8. Minimum Relational Data Model

The assessment requires at least the following four tables. Additional fields or tables are allowed if explained in README.

| Table | Required main fields | Rules/notes |
|---|---|---|
| `businesses` | `id`, `name`, `slug`, `created_at` | `slug` unique. |
| `users` | `id`, `business_id`, `name`, `email`, `password_hash`, `role`, `created_at` | `email` globally unique; role is `admin`, `agent`, or `customer`. |
| `tickets` | `id`, `business_id`, `customer_id`, `assigned_agent_id`, `subject`, `category`, `priority`, `status`, `created_at`, `updated_at` | `assigned_agent_id` nullable; index on `(business_id, status)`. |
| `messages` | `id`, `ticket_id`, `sender_id`, `body`, `created_at` | Order message history by `created_at`. |

| ID | Level | Acceptance requirement |
|---|---|---|
| DB-01 | MUST | Create the four minimum tables through migrations. |
| DB-02 | MUST | Store `business_id` directly on `tickets` for efficient tenant filtering. |
| DB-03 | MUST | Enforce unique business slugs and globally unique user emails. |
| DB-04 | MUST | Support nullable assigned agents. |
| DB-05 | MUST | Create the `(business_id, status)` ticket index. |
| DB-06 | MUST | Preserve message history and retrieve it in chronological order. |

**DECISION:** Use foreign keys, transaction boundaries, UTC timestamps, and additional message indexes as implementation-quality safeguards. The specification mandates a relational schema and migrations but does not prescribe every constraint or index beyond those noted above.

## 9. Minimum API Surface

Path names may differ if they are consistent and documented. FastAPI Swagger/OpenAPI is sufficient for API documentation.

| Method | Reference path | Authorized role | Required behavior |
|---|---|---|---|
| POST | `/auth/register-business` | Public | Register business and Business Admin. |
| POST | `/auth/login` | Public | Authenticate and return access + refresh tokens. |
| POST | `/auth/refresh` | Valid refresh token | Issue a new access token. |
| GET | `/auth/me` | Authenticated | Return user and business. |
| GET | `/users` | Admin | List own-business users. |
| POST | `/users` | Admin | Create own-business Agent or Customer. |
| GET | `/tickets?status=` | Authenticated, role-scoped | List visible tickets and optionally filter status. |
| POST | `/tickets` | Customer | Create ticket and initial message. |
| GET | `/tickets/{id}` | Authorized ticket access | Read ticket detail. |
| PATCH | `/tickets/{id}` | Agent/Admin; Customer for reopen | Update permitted status or assignee fields. |
| GET | `/tickets/{id}/messages` | Authorized ticket access | Retrieve message history. |
| WS | `/ws/tickets/{id}?token=...` | Authorized ticket access | Exchange messages and status updates in real time. |

### API Error Contract

| ID | Status | Mandatory meaning |
|---|---|---|
| API-01 | `401` | Unauthenticated request. |
| API-02 | `403` | Authenticated role not authorized for the action. |
| API-03 | `404` | Resource not found or belongs to another business. |
| API-04 | `422` | Invalid input. |
| API-05 | Consistent JSON | All API errors return a consistent JSON format. |

The assessment does not prescribe a specific JSON error envelope, JWT claims, cookie approach, token expiry duration, or WebSocket event payload. Define those choices in `docs/API_CONTRACT.md` and `ARCHITECTURE.md`, and keep implementation consistent.

## 10. Mandatory Frontend Pages

| ID | Route | Intended access | Required content |
|---|---|---|---|
| UI-01 | `/login` | Public | Login form. |
| UI-02 | `/register` | Public | Register new business and Admin. |
| UI-03 | `/tickets` | All authenticated roles | Ticket list, status, priority, assignee, latest activity time, status filter. |
| UI-04 | `/tickets/new` | Customer | Create-ticket form. |
| UI-05 | `/tickets/[id]` | Authorized ticket access | Real-time chat and ticket information panel with role-appropriate actions. |
| UI-06 | `/admin/users` | Admin | List own-business users; add Agent or Customer. |
| UI-07 | Protected routes | Authenticated roles | Redirect to `/login` when not authenticated or token/session expires. |
| UI-08 | All pages | Appropriate users | Handle loading and error states and remain usable on mobile. |
| UI-09 | Role-specific actions | Appropriate roles | Hide unauthorized buttons/menus; backend independently rejects prohibited calls. |

Visual sophistication has relatively low priority; functioning flows, loading/error behavior, and mobile usability matter more.

## 11. Optional Bonuses

The following are **BONUS**, not mandatory, and only count after all mandatory functionality is operating:

- Docker Compose to run frontend, backend, and database with one command.
- pytest unit/integration tests, especially cross-business isolation tests.
- Typing indicator and message-read status.
- Unread message badge in ticket list.
- Image attachments in chat.
- Ticket pagination and search.
- Real-time ticket-list notifications for new tickets or messages.
- Login endpoint rate limiting.
- Online deployment (such as Vercel and Render/Railway).

**Implementation priority decision:** Still add a few focused isolation and authorization tests early to reduce disqualification risk, even though automated tests are listed as a scoring bonus.

## 12. Submission Deliverables

| ID | Level | Deliverable |
|---|---|---|
| DEL-01 | MUST | One GitHub repository URL, public or private with reviewer access. |
| DEL-02 | MUST | Source code in `frontend/` and `backend/`. |
| DEL-03 | MUST | `README.md` with complete setup-from-scratch instructions. |
| DEL-04 | MUST | Environment variable list and `.env.example` containing no real secrets. |
| DEL-05 | MUST | Seed script for **two businesses**, each with **one Admin, one Agent, and two Customers** (8 users total). |
| DEL-06 | MUST | List all demo accounts in README. |
| DEL-07 | MUST | **3-5 minute demo video** showing Customer and Agent chatting live in two browser sessions. |
| DEL-08 | MUST | Demo video showing an Agent changing ticket status. |
| DEL-09 | MUST | Demo video showing Business A cannot open Business B's ticket. |
| DEL-10 | MUST | README **Catatan** section explaining key decisions, trade-offs, and unfinished work. |
| DEL-11 | MUST | Reasonable Git commit history, not a single large final commit. |

The README should allow a reviewer to run the application in approximately **15 minutes**.

## 13. Assessment Rubric and Disqualifiers

**Passing threshold: 70/100**, with **no automatic-failure condition**.

| Assessment area | Weight |
|---|---:|
| Mandatory features working | 30% |
| Data isolation and security | 20% |
| Real-time chat | 15% |
| Code quality and structure | 15% |
| API and database design | 10% |
| Documentation and ease of running | 10% |

**Automatic failure conditions:**

1. Data from another business can be accessed through the API, including guessed IDs.
2. Passwords are stored or returned in plaintext.
3. Real secrets or credentials are committed to the repository.
4. The candidate cannot explain their own code during review.

After submission, selected candidates attend a **30-45 minute** code walkthrough and make a small live change.

## 14. Deadline and Working Rules

- **Time limit:** 5 calendar days from receipt of the assessment.
- **Estimated workload:** 15-20 hours.
- Libraries, boilerplates, and documentation are permitted.
- AI coding assistants are permitted, but the candidate must be able to explain every line used.
- Prioritize mandatory features over optional bonuses.
- Unfinished features do not automatically mean failure; disclose them honestly in README with a completion plan.
- Specification questions may be submitted on the first day. For later ambiguities, make reasonable, documented assumptions.

The PDF does not specify an absolute submission timestamp; calculate the actual deadline from the recorded receipt time or recruiter instructions rather than assuming one.

## 15. Reviewer-Oriented Acceptance Scenarios

These scenarios translate the original assessment into concrete verification steps. They are project tests, not additional product features.

- [ ] **AC-01 Registration:** Register Business A with Admin A; both records exist; duplicate globally unique emails are rejected.
- [ ] **AC-02 Auth:** Login returns both JWT token types; `/auth/me` returns the correct identity; refresh issues a new access token.
- [ ] **AC-03 User management:** Admin A creates an Agent and Customer scoped to Business A; Agent cannot create users.
- [ ] **AC-04 Cross-tenant detail:** An authenticated Business A user requests Business B's ticket ID and receives 404 with no leaked data.
- [ ] **AC-05 Customer ownership:** Customer A1 cannot open Customer A2's ticket within Business A.
- [ ] **AC-06 Tenant-scoped lists:** Business A never receives Business B's tickets or users.
- [ ] **AC-07 Ticket creation:** Customer creates ticket with first message, priority, category, and subject; both ticket and message persist.
- [ ] **AC-08 Ticket listing:** Visible tickets respect role, status filter, and latest-activity ordering.
- [ ] **AC-09 Assignment:** Agent takes a ticket; Admin assigns an Agent within the same business; cross-business assignment is blocked.
- [ ] **AC-10 Status lifecycle:** Valid transitions work; Customer can reopen their own resolved ticket; closed cannot be reopened.
- [ ] **AC-11 Closed chat:** New messages to a closed ticket are rejected.
- [ ] **AC-12 Chat persistence:** Opening a ticket loads messages with sender name, role, and timestamp.
- [ ] **AC-13 Live delivery:** Customer and Agent in separate browsers receive new messages without manual refresh.
- [ ] **AC-14 Live status:** Active ticket viewers see status changes without manual refresh.
- [ ] **AC-15 WebSocket auth:** Missing/invalid token and cross-business/unauthorized ticket connections are denied.
- [ ] **AC-16 Frontend access:** Unauthenticated protected navigation redirects to login; actions are shown only to appropriate roles.
- [ ] **AC-17 API errors:** Invalid authentication, role restrictions, inaccessible resources, and validation failures use documented consistent errors.
- [ ] **AC-18 Submission:** Fresh setup works, migrations and seed work, demo accounts are documented, and a 3-5 minute video shows the three requested scenarios.
- [ ] **AC-19 Safety:** No plaintext passwords, response password leaks, committed real secrets, or demonstrated tenant isolation failures.

## 16. Explicitly Unspecified Details and Design Decisions

The original assessment does **not** define the items below precisely. Do not present choices as if they were prescribed:

| Topic | Assessment coverage | Handling |
|---|---|---|
| Admin sending chat messages | Admin can view tickets; sending is not explicitly granted or denied. | Document the permission decision before implementation. |
| JWT expiry and refresh-token rotation | Access + refresh required; detailed lifecycle not specified. | Document token policy. |
| Refresh token transport/storage | Not specified. | Document cookie/header approach and frontend behavior. |
| WebSocket event JSON format | Only endpoint and behavior specified. | Define and document event contract. |
| Exact API path names | Reference endpoints provided; alternatives allowed if consistent. | Keep names consistent and documented. |
| Error JSON object structure | JSON consistency required; shape not specified. | Define one shared format. |
| Same-business, cross-customer denial status | Access must be blocked; precise status not given. | Prefer 404 as a documented security decision. |
| Same-status updates and skipping lifecycle stages | Diagram shows normal progression and resolved-to-open only. | Implement the documented transitions; clarify or document edge cases. |
| Concurrency, retries, and connection recovery | Not described in detail. | Use a small, reliable approach without expanding scope. |
| Deployment, scaling, caching | Deployment bonus; scaling not prescribed. | Exclude from P0 scope. |

If these choices conflict with `ARCHITECTURE.md`, update the decision documentation without weakening a **MUST** requirement.

## 17. Milestone Mapping for Harness Engineering

| Milestone | Requirements covered | Completion evidence |
|---|---|---|
| M0 - Foundation | TECH, source documentation, project structure | Repo structure, documented decisions, runnable scaffolding as planned. |
| M1 - Database | DB requirements | Alembic migration creates required entities and indexes. |
| M2 - Authentication | AUTH, ROLE user creation | Registration, login, refresh, `/me`, Admin user management verified. |
| M3 - Tenant authorization | SEC, ROLE | Cross-business/customer access and permission checks pass. |
| M4 - Tickets | TICK, ticket APIs | Ticket, assignment, filter, and lifecycle flows verified. |
| M5 - WebSocket | CHAT, WS security | Two-client live chat, persistence, status broadcasts, and access rejection verified. |
| M6 - Frontend | UI requirements | Mandatory routes and role-aware flows verified. |
| M7 - Final verification | DEL, rubric, critical end-to-end flows | Seed, README, video, commits, safety review, final demo. |

Milestones are an **implementation plan**, not a required project-management method in the assessment. Do not advance automatically without validation of the active milestone.

## 18. Definition of Done

The MVP is ready for submission when:

- [ ] All mandatory technology and functional requirements are implemented.
- [ ] Backend tenant isolation and role access are verified, including WebSocket access.
- [ ] No automatic-failure condition is present.
- [ ] Chat messages and status updates work in real time and persist as required.
- [ ] Every mandatory frontend page functions on desktop and mobile with loading/error handling.
- [ ] Migrations, seed data, and documented demo accounts work on a fresh setup.
- [ ] README includes setup, environment variables, technical decisions, trade-offs, and honest limitations.
- [ ] The required 3-5 minute demo video and GitHub repository are ready.
- [ ] The candidate can explain the implementation and perform a small change during review.

**Scope rule:** Do not substitute bonus features or extra infrastructure for incomplete mandatory features.
