# HelpDesk Mini

HelpDesk Mini is a planned multi-tenant support-ticket application where Customers create tickets and communicate with business staff through persistent, real-time chat. It is being built for the SVO Connect Junior Developer technical assessment.

## Implementation Status

**Harness stabilization only.** Requirements and architecture are documented, but the frontend and backend have not yet been scaffolded or verified as runnable. Follow the active [M0 foundation plan](exec-plans/active/M0-foundation.md) for the next implementation milestone.

## Technology Stack

- Frontend: Next.js App Router, TypeScript, Tailwind CSS, and TanStack Query.
- Backend: Python 3.11+, FastAPI, Pydantic, SQLAlchemy, and Alembic.
- Data and real time: PostgreSQL and native FastAPI WebSocket.
- Security: JWT access/refresh tokens and Argon2 password hashing.

## Planned Repository Structure

```text
helpdesk-mini/
├── frontend/              # Next.js application (planned in M0)
├── backend/               # FastAPI application (planned in M0)
├── docs/                  # Requirements, API, and security contracts
└── exec-plans/            # Active and completed milestone plans
```

## Architecture and Security

The system is a modular monolith: the Next.js client communicates with one FastAPI backend, which is the authority for authentication, RBAC, tenant isolation, ticket rules, and WebSocket authorization. PostgreSQL is the source of truth. Every protected resource is scoped to the authenticated user's business; Customers are additionally restricted to their own tickets. Cross-business ticket access returns 404, refresh tokens cannot authorize ordinary endpoints, and closed tickets cannot receive messages.

See [ARCHITECTURE.md](ARCHITECTURE.md), [requirements](docs/REQUIREMENTS.md), [security](docs/SECURITY.md), and the [API contract](docs/API_CONTRACT.md).

## Development Prerequisites

M0 will establish and verify exact versions and setup commands. The planned prerequisites are Node.js with a compatible package manager, Python 3.11 or later, and PostgreSQL. No runnable setup is claimed yet.

## Environment Configuration

Root [`.env.example`](.env.example) documents all planned variables without real secrets. During M0, backend values will be copied to `backend/.env` and frontend values to `frontend/.env.local`; both local files are ignored by Git. Access tokens expire after 15 minutes and refresh tokens after 7 days by default.

## Milestone Roadmap

| Milestone | Scope |
|---|---|
| M0 | Runnable frontend/backend foundation, PostgreSQL, Alembic, and verified setup |
| M1 | Database models and migrations |
| M2 | JWT authentication and securely scoped business user management |
| M3 | Comprehensive tenant-authorization audit and isolation tests |
| M4 | Ticket management |
| M5 | WebSocket chat |
| M6 | Required frontend flows |
| M7 | Final tests, seed data, documentation, and demo preparation |

## Planned Demo Requirements

The final demo must show Customer and Agent chat updating in two browsers, an Agent updating ticket status, and a Business A user being denied access to a Business B ticket.

## Technical Decisions and Trade-offs

- A modular monolith keeps the assessment implementation explainable and maintainable.
- Shared-schema tenancy is simple, but every protected query must enforce `business_id` and applicable ownership checks.
- Refresh tokens use an HttpOnly cookie for browser refresh; access tokens remain in memory.
- The MVP uses a single-process in-memory WebSocket manager, avoiding premature broker infrastructure.
- Mandatory security and functional flows take priority over optional bonuses and UI polish.

## Known Limitations

- Application scaffolding and verified setup commands do not exist yet.
- Stateless refresh tokens do not support immediate server-side revocation or rotation.
- In-memory WebSocket broadcasting does not span multiple backend processes.
- Deployment, rate limiting, and other bonus features are outside the current scope.

This README will be expanded with verified setup steps, seed/demo accounts, a **Catatan** section, and final limitations as milestones progress.
