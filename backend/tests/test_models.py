import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Business, Message, Ticket, User
from app.models.enums import TicketPriority, TicketStatus, UserRole


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    database_url = os.environ.get("M1_TEST_DATABASE_URL")
    if database_url is None:
        pytest.fail(
            "M1_TEST_DATABASE_URL must point to a disposable PostgreSQL database"
        )

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail(
            "M1 tests require a PostgreSQL database whose name ends with '_test'"
        )

    test_engine = create_engine(database_url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    test_session = Session(bind=connection, expire_on_commit=False)
    try:
        yield test_session
    finally:
        test_session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def add_business(session: Session, *, slug: str | None = None) -> Business:
    business = Business(name="Test Business", slug=slug or f"business-{uuid.uuid4()}")
    session.add(business)
    session.flush()
    return business


def add_user(
    session: Session,
    business: Business,
    *,
    email: str | None = None,
    role: UserRole = UserRole.CUSTOMER,
) -> User:
    user = User(
        business=business,
        name="Test User",
        email=email or f"user-{uuid.uuid4()}@example.test",
        password_hash="not-a-plaintext-password",
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def add_ticket(
    session: Session,
    business: Business,
    customer: User,
    *,
    assigned_agent: User | None = None,
) -> Ticket:
    ticket = Ticket(
        business=business,
        customer=customer,
        assigned_agent=assigned_agent,
        subject="Cannot sign in",
        category="account",
        priority=TicketPriority.HIGH,
    )
    session.add(ticket)
    session.flush()
    return ticket


def test_required_schema_columns_and_nullability(engine: Engine) -> None:
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "businesses",
        "messages",
        "tickets",
        "users",
    }

    expected_nullability = {
        "businesses": {"id": False, "name": False, "slug": False, "created_at": False},
        "users": {
            "id": False,
            "business_id": False,
            "name": False,
            "email": False,
            "password_hash": False,
            "role": False,
            "created_at": False,
        },
        "tickets": {
            "id": False,
            "business_id": False,
            "customer_id": False,
            "assigned_agent_id": True,
            "subject": False,
            "category": False,
            "priority": False,
            "status": False,
            "created_at": False,
            "updated_at": False,
        },
        "messages": {
            "id": False,
            "ticket_id": False,
            "sender_id": False,
            "body": False,
            "created_at": False,
        },
    }
    for table_name, expected in expected_nullability.items():
        actual = {
            column["name"]: column["nullable"]
            for column in inspector.get_columns(table_name)
        }
        assert actual == expected


def test_business_creation_and_relationship(session: Session) -> None:
    business = add_business(session)
    user = add_user(session, business)

    assert user.business is business
    assert user in business.users
    assert business.created_at is not None


def test_duplicate_business_slug_is_rejected(session: Session) -> None:
    slug = f"duplicate-{uuid.uuid4()}"
    add_business(session, slug=slug)
    session.add(Business(name="Duplicate", slug=slug))

    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_email_is_rejected_globally(session: Session) -> None:
    email = f"duplicate-{uuid.uuid4()}@example.test"
    add_user(session, add_business(session), email=email)
    other_business = add_business(session)
    session.add(
        User(
            business=other_business,
            name="Duplicate Email",
            email=email,
            password_hash="hash",
            role=UserRole.CUSTOMER,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_ticket_relationships_and_nullable_assignment(session: Session) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    ticket = add_ticket(session, business, customer)

    assert ticket.assigned_agent is None
    assert ticket.business is business
    assert ticket.customer is customer
    assert ticket in business.tickets
    assert ticket in customer.customer_tickets
    assert ticket.status == TicketStatus.OPEN
    assert ticket.created_at is not None
    assert ticket.updated_at is not None


def test_ticket_agent_relationship(session: Session) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    agent = add_user(session, business, role=UserRole.AGENT)
    ticket = add_ticket(session, business, customer, assigned_agent=agent)

    assert ticket.assigned_agent is agent
    assert ticket in agent.assigned_tickets


def test_message_relationships(session: Session) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    ticket = add_ticket(session, business, customer)
    message = Message(ticket=ticket, sender=customer, body="Please help")
    session.add(message)
    session.flush()

    assert message.ticket is ticket
    assert message.sender is customer
    assert message in ticket.messages
    assert message in customer.sent_messages
    assert message.created_at is not None


def test_foreign_keys_are_present(engine: Engine) -> None:
    inspector = inspect(engine)
    actual = {
        foreign_key["name"]
        for table in ("users", "tickets", "messages")
        for foreign_key in inspector.get_foreign_keys(table)
    }
    assert actual == {
        "fk_users_business_id_businesses",
        "fk_tickets_business_id_businesses",
        "fk_tickets_customer_id_users",
        "fk_tickets_assigned_agent_id_users",
        "fk_messages_ticket_id_tickets",
        "fk_messages_sender_id_users",
    }


def test_user_requires_existing_business(session: Session) -> None:
    session.add(
        User(
            business_id=uuid.uuid4(),
            name="Orphan User",
            email=f"orphan-{uuid.uuid4()}@example.test",
            password_hash="hash",
            role=UserRole.CUSTOMER,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_ticket_requires_existing_customer(session: Session) -> None:
    business = add_business(session)
    session.add(
        Ticket(
            business=business,
            customer_id=uuid.uuid4(),
            subject="Orphan Ticket",
            category="account",
            priority=TicketPriority.LOW,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_message_requires_existing_ticket_and_sender(session: Session) -> None:
    session.add(
        Message(
            ticket_id=uuid.uuid4(),
            sender_id=uuid.uuid4(),
            body="Orphan message",
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_required_indexes_are_present(engine: Engine) -> None:
    inspector = inspect(engine)
    ticket_indexes = {
        index["name"]: index["column_names"]
        for index in inspector.get_indexes("tickets")
    }
    message_indexes = {
        index["name"]: index["column_names"]
        for index in inspector.get_indexes("messages")
    }

    assert ticket_indexes["ix_tickets_business_id_status"] == [
        "business_id",
        "status",
    ]
    assert message_indexes["ix_messages_ticket_id_created_at_id"] == [
        "ticket_id",
        "created_at",
        "id",
    ]


@pytest.mark.parametrize("role", list(UserRole))
def test_allowed_roles_persist(session: Session, role: UserRole) -> None:
    user = add_user(session, add_business(session), role=role)
    session.expire(user, ["role"])

    assert user.role == role.value


def test_invalid_role_is_rejected(session: Session) -> None:
    business = add_business(session)
    session.add(
        User(
            business=business,
            name="Invalid Role",
            email=f"invalid-{uuid.uuid4()}@example.test",
            password_hash="hash",
            role="owner",
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("priority", list(TicketPriority))
def test_allowed_priorities_persist(session: Session, priority: TicketPriority) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    ticket = add_ticket(session, business, customer)
    ticket.priority = priority
    session.flush()
    session.expire(ticket, ["priority"])

    assert ticket.priority == priority.value


def test_invalid_priority_is_rejected(session: Session) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    ticket = add_ticket(session, business, customer)
    ticket.priority = "urgent"

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("status", list(TicketStatus))
def test_allowed_statuses_persist(session: Session, status: TicketStatus) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    ticket = add_ticket(session, business, customer)
    ticket.status = status
    session.flush()
    session.expire(ticket, ["status"])

    assert ticket.status == status.value


def test_invalid_status_is_rejected(session: Session) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    ticket = add_ticket(session, business, customer)
    ticket.status = "waiting"

    with pytest.raises(IntegrityError):
        session.flush()


def test_rows_can_be_loaded_through_relationships(session: Session) -> None:
    business = add_business(session)
    customer = add_user(session, business)
    ticket = add_ticket(session, business, customer)
    message = Message(ticket=ticket, sender=customer, body="Persisted message")
    session.add(message)
    session.flush()
    message_id = message.id
    session.expire_all()

    loaded = session.scalar(select(Message).where(Message.id == message_id))
    assert loaded is not None
    assert loaded.ticket.customer.business.slug == business.slug
    assert loaded.sender.email == customer.email
