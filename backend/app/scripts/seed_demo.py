"""Create deterministic, tenant-safe demo data without deleting existing rows."""

from __future__ import annotations

import argparse
import os
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import Business, Message, Ticket, User
from app.models.enums import TicketPriority, TicketStatus, UserRole

DEMO_PASSWORD_ENV = "DEMO_SEED_PASSWORD"


class DemoSeedError(RuntimeError):
    """Raised when demo data cannot be created safely."""


@dataclass(frozen=True)
class BusinessSpec:
    id: uuid.UUID
    name: str
    slug: str


@dataclass(frozen=True)
class UserSpec:
    id: uuid.UUID
    business_slug: str
    name: str
    email: str
    role: UserRole


@dataclass(frozen=True)
class TicketSpec:
    id: uuid.UUID
    business_slug: str
    customer_email: str
    assigned_agent_email: str | None
    subject: str
    category: str
    priority: TicketPriority
    status: TicketStatus


@dataclass(frozen=True)
class MessageSpec:
    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_email: str
    body: str


@dataclass(frozen=True)
class SeedResult:
    businesses: int
    users: int
    tickets: int
    messages: int


BUSINESS_SPECS = (
    BusinessSpec(
        id=uuid.UUID("10000000-0000-4000-8000-000000000001"),
        name="Northstar Support",
        slug="demo-northstar",
    ),
    BusinessSpec(
        id=uuid.UUID("10000000-0000-4000-8000-000000000002"),
        name="Orbit Services",
        slug="demo-orbit",
    ),
)

USER_SPECS = (
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000001"),
        "demo-northstar",
        "Nadia Admin",
        "admin@northstar.demo.test",
        UserRole.ADMIN,
    ),
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000002"),
        "demo-northstar",
        "Andi Agent",
        "agent@northstar.demo.test",
        UserRole.AGENT,
    ),
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000003"),
        "demo-northstar",
        "Citra Customer",
        "customer1@northstar.demo.test",
        UserRole.CUSTOMER,
    ),
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000004"),
        "demo-northstar",
        "Dimas Customer",
        "customer2@northstar.demo.test",
        UserRole.CUSTOMER,
    ),
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000005"),
        "demo-orbit",
        "Olivia Admin",
        "admin@orbit.demo.test",
        UserRole.ADMIN,
    ),
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000006"),
        "demo-orbit",
        "Raka Agent",
        "agent@orbit.demo.test",
        UserRole.AGENT,
    ),
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000007"),
        "demo-orbit",
        "Sari Customer",
        "customer1@orbit.demo.test",
        UserRole.CUSTOMER,
    ),
    UserSpec(
        uuid.UUID("20000000-0000-4000-8000-000000000008"),
        "demo-orbit",
        "Tono Customer",
        "customer2@orbit.demo.test",
        UserRole.CUSTOMER,
    ),
)

TICKET_SPECS = (
    TicketSpec(
        uuid.UUID("30000000-0000-4000-8000-000000000001"),
        "demo-northstar",
        "customer1@northstar.demo.test",
        None,
        "Cannot access billing portal",
        "billing",
        TicketPriority.HIGH,
        TicketStatus.OPEN,
    ),
    TicketSpec(
        uuid.UUID("30000000-0000-4000-8000-000000000002"),
        "demo-northstar",
        "customer2@northstar.demo.test",
        "agent@northstar.demo.test",
        "Invoice amount needs clarification",
        "billing",
        TicketPriority.MEDIUM,
        TicketStatus.IN_PROGRESS,
    ),
    TicketSpec(
        uuid.UUID("30000000-0000-4000-8000-000000000003"),
        "demo-northstar",
        "customer1@northstar.demo.test",
        "agent@northstar.demo.test",
        "Reset notification preferences",
        "account",
        TicketPriority.LOW,
        TicketStatus.RESOLVED,
    ),
    TicketSpec(
        uuid.UUID("30000000-0000-4000-8000-000000000004"),
        "demo-northstar",
        "customer2@northstar.demo.test",
        "agent@northstar.demo.test",
        "Archived access request",
        "account",
        TicketPriority.LOW,
        TicketStatus.CLOSED,
    ),
    TicketSpec(
        uuid.UUID("30000000-0000-4000-8000-000000000005"),
        "demo-orbit",
        "customer1@orbit.demo.test",
        None,
        "Orbit workspace invitation missing",
        "account",
        TicketPriority.HIGH,
        TicketStatus.OPEN,
    ),
)

MESSAGE_SPECS = (
    MessageSpec(
        uuid.UUID("40000000-0000-4000-8000-000000000001"),
        uuid.UUID("30000000-0000-4000-8000-000000000001"),
        "customer1@northstar.demo.test",
        "The billing portal returns an access denied message.",
    ),
    MessageSpec(
        uuid.UUID("40000000-0000-4000-8000-000000000002"),
        uuid.UUID("30000000-0000-4000-8000-000000000002"),
        "customer2@northstar.demo.test",
        "Could you explain the additional line item on this invoice?",
    ),
    MessageSpec(
        uuid.UUID("40000000-0000-4000-8000-000000000003"),
        uuid.UUID("30000000-0000-4000-8000-000000000002"),
        "agent@northstar.demo.test",
        "I am reviewing the invoice and will update you shortly.",
    ),
    MessageSpec(
        uuid.UUID("40000000-0000-4000-8000-000000000004"),
        uuid.UUID("30000000-0000-4000-8000-000000000003"),
        "customer1@northstar.demo.test",
        "Please restore the default notification settings.",
    ),
    MessageSpec(
        uuid.UUID("40000000-0000-4000-8000-000000000005"),
        uuid.UUID("30000000-0000-4000-8000-000000000003"),
        "agent@northstar.demo.test",
        "The notification settings have been restored.",
    ),
    MessageSpec(
        uuid.UUID("40000000-0000-4000-8000-000000000006"),
        uuid.UUID("30000000-0000-4000-8000-000000000004"),
        "customer2@northstar.demo.test",
        "This old request can remain closed.",
    ),
    MessageSpec(
        uuid.UUID("40000000-0000-4000-8000-000000000007"),
        uuid.UUID("30000000-0000-4000-8000-000000000005"),
        "customer1@orbit.demo.test",
        "I did not receive an invitation to the Orbit workspace.",
    ),
)


def _conflict(label: str) -> DemoSeedError:
    return DemoSeedError(
        f"Demo seed conflict for {label}; no demo changes were committed."
    )


def validate_demo_password(password: str | None) -> str:
    if password is None or len(password) < 12:
        raise DemoSeedError(f"{DEMO_PASSWORD_ENV} must contain at least 12 characters.")
    if "replace" in password.casefold() or "changeme" in password.casefold():
        raise DemoSeedError(f"{DEMO_PASSWORD_ENV} must not be a placeholder value.")
    return password


def validate_database_target(database_url: str, *, confirmed: bool) -> str:
    if not confirmed:
        raise DemoSeedError(
            "Pass --confirm-demo-data to acknowledge the demo-data write."
        )
    try:
        url = make_url(database_url)
    except Exception as error:
        raise DemoSeedError("DATABASE_URL is not a valid database URL.") from error
    database_name = url.database or ""
    if url.get_backend_name() != "postgresql" or not database_name:
        raise DemoSeedError("Demo seed requires a named PostgreSQL database.")
    target_label = " ".join((database_name, url.host or "")).casefold()
    production_name = re.search(
        r"(?:^|[.\s_-])(prod|production)(?:$|[.\s_-])", target_label
    )
    if production_name or database_name.casefold() in {
        "postgres",
        "template0",
        "template1",
    }:
        raise DemoSeedError(
            "Refusing to seed an obviously protected/production target."
        )
    return database_name


def _ensure_business(db: Session, spec: BusinessSpec) -> Business:
    by_id = db.get(Business, spec.id)
    by_slug = db.scalar(select(Business).where(Business.slug == spec.slug))
    if by_id is not None and by_slug is not None and by_id.id != by_slug.id:
        raise _conflict(f"business {spec.slug}")
    business = by_id or by_slug
    if business is None:
        business = Business(id=spec.id, name=spec.name, slug=spec.slug)
        db.add(business)
        db.flush()
        return business
    if (
        business.id != spec.id
        or business.name != spec.name
        or business.slug != spec.slug
    ):
        raise _conflict(f"business {spec.slug}")
    return business


def _ensure_user(
    db: Session,
    spec: UserSpec,
    businesses: dict[str, Business],
    password: str,
) -> User:
    by_id = db.get(User, spec.id)
    by_email = db.scalar(select(User).where(User.email == spec.email))
    if by_id is not None and by_email is not None and by_id.id != by_email.id:
        raise _conflict(f"user {spec.email}")
    user = by_id or by_email
    business = businesses[spec.business_slug]
    if user is None:
        user = User(
            id=spec.id,
            business=business,
            name=spec.name,
            email=spec.email,
            password_hash=hash_password(password),
            role=spec.role,
        )
        db.add(user)
        db.flush()
        return user
    expected = (
        user.id == spec.id
        and user.business_id == business.id
        and user.name == spec.name
        and user.email == spec.email
        and user.role == spec.role
        and verify_password(password, user.password_hash)
    )
    if not expected:
        raise _conflict(f"user {spec.email}")
    return user


def _ensure_ticket(
    db: Session,
    spec: TicketSpec,
    businesses: dict[str, Business],
    users: dict[str, User],
) -> Ticket:
    ticket = db.get(Ticket, spec.id)
    business = businesses[spec.business_slug]
    customer = users[spec.customer_email]
    agent = users[spec.assigned_agent_email] if spec.assigned_agent_email else None
    if customer.business_id != business.id or customer.role != UserRole.CUSTOMER:
        raise _conflict(f"ticket {spec.id} customer relationship")
    if agent is not None and (
        agent.business_id != business.id or agent.role != UserRole.AGENT
    ):
        raise _conflict(f"ticket {spec.id} agent relationship")
    if ticket is None:
        ticket = Ticket(
            id=spec.id,
            business=business,
            customer=customer,
            assigned_agent=agent,
            subject=spec.subject,
            category=spec.category,
            priority=spec.priority,
            status=spec.status,
        )
        db.add(ticket)
        db.flush()
        return ticket
    expected = (
        ticket.business_id == business.id
        and ticket.customer_id == customer.id
        and ticket.assigned_agent_id == (agent.id if agent else None)
        and ticket.subject == spec.subject
        and ticket.category == spec.category
        and ticket.priority == spec.priority
        and ticket.status == spec.status
    )
    if not expected:
        raise _conflict(f"ticket {spec.id}")
    return ticket


def _ensure_message(
    db: Session,
    spec: MessageSpec,
    tickets: dict[uuid.UUID, Ticket],
    users: dict[str, User],
) -> Message:
    message = db.get(Message, spec.id)
    ticket = tickets[spec.ticket_id]
    sender = users[spec.sender_email]
    if sender.business_id != ticket.business_id:
        raise _conflict(f"message {spec.id} tenant relationship")
    if sender.role == UserRole.ADMIN or (
        sender.role == UserRole.CUSTOMER and sender.id != ticket.customer_id
    ):
        raise _conflict(f"message {spec.id} sender authorization")
    if message is None:
        message = Message(
            id=spec.id,
            ticket=ticket,
            sender=sender,
            body=spec.body,
        )
        db.add(message)
        db.flush()
        return message
    expected = (
        message.ticket_id == ticket.id
        and message.sender_id == sender.id
        and message.body == spec.body
    )
    if not expected:
        raise _conflict(f"message {spec.id}")
    return message


def seed_demo(db: Session, password: str) -> SeedResult:
    """Create or verify the complete demo dataset in one transaction."""
    password = validate_demo_password(password)
    try:
        with db.begin():
            businesses = {
                spec.slug: _ensure_business(db, spec) for spec in BUSINESS_SPECS
            }
            users = {
                spec.email: _ensure_user(db, spec, businesses, password)
                for spec in USER_SPECS
            }
            tickets = {
                spec.id: _ensure_ticket(db, spec, businesses, users)
                for spec in TICKET_SPECS
            }
            for spec in MESSAGE_SPECS:
                _ensure_message(db, spec, tickets, users)
    except IntegrityError as error:
        raise DemoSeedError(
            "Database constraint rejected demo data; no demo changes were committed."
        ) from error
    return SeedResult(
        businesses=len(BUSINESS_SPECS),
        users=len(USER_SPECS),
        tickets=len(TICKET_SPECS),
        messages=len(MESSAGE_SPECS),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create idempotent HelpDesk Mini demo data."
    )
    parser.add_argument(
        "--confirm-demo-data",
        action="store_true",
        help="acknowledge that demo records will be written to DATABASE_URL",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        from app.core.config import get_settings
        from app.db.session import get_session_factory

        settings = get_settings()
        database_name = validate_database_target(
            settings.database_url,
            confirmed=args.confirm_demo_data,
        )
        password = validate_demo_password(os.environ.get(DEMO_PASSWORD_ENV))
        with get_session_factory()() as db:
            result = seed_demo(db, password)
    except DemoSeedError as error:
        print(f"Demo seed refused: {error}")
        return 2

    print(
        "Demo seed ready on database "
        f"{database_name!r}: {result.businesses} businesses, {result.users} users, "
        f"{result.tickets} tickets, {result.messages} messages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
