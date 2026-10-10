import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.errors import AppError
from app.models import Business, Ticket, TicketPriority, TicketStatus, User, UserRole
from app.services.authorization import (
    authorize_ticket_status_update,
    get_authorized_assignment_agent,
    get_authorized_ticket,
)


@pytest.fixture(scope="session")
def authorization_engine() -> Iterator[Engine]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.fail("TEST_DATABASE_URL must point to a disposable PostgreSQL database")

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail(
            "M3 authorization tests require a PostgreSQL database whose "
            "name ends with '_test'"
        )

    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(authorization_engine: Engine) -> Iterator[Session]:
    connection = authorization_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def add_business(db: Session) -> Business:
    business = Business(name="Authorization Test", slug=f"auth-{uuid.uuid4()}")
    db.add(business)
    db.flush()
    return business


def add_user(db: Session, business: Business, role: UserRole) -> User:
    user = User(
        business=business,
        name=f"{role.value.title()} User",
        email=f"{role.value}-{uuid.uuid4()}@example.test",
        password_hash="not-a-plaintext-password",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def add_ticket(
    db: Session,
    business: Business,
    customer: User,
    *,
    status: TicketStatus = TicketStatus.OPEN,
) -> Ticket:
    ticket = Ticket(
        business=business,
        customer=customer,
        subject="Authorization boundary",
        category="security",
        priority=TicketPriority.HIGH,
        status=status,
    )
    db.add(ticket)
    db.flush()
    return ticket


def error_signature(error: AppError) -> tuple[int, str, str, object]:
    return error.status_code, error.code, error.message, error.details


def test_role_policy_returns_allowed_user_and_rejects_other_roles() -> None:
    admin = User(role=UserRole.ADMIN)
    assert require_roles(admin, {UserRole.ADMIN, UserRole.AGENT}) is admin

    with pytest.raises(AppError) as denied:
        require_roles(User(role=UserRole.CUSTOMER), {UserRole.ADMIN, UserRole.AGENT})

    assert error_signature(denied.value) == (
        403,
        "FORBIDDEN",
        "You are not allowed to perform this action.",
        None,
    )


def test_same_business_staff_and_owning_customer_can_resolve_ticket(
    db: Session,
) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)

    for current_user in (admin, agent, customer):
        assert get_authorized_ticket(db, ticket.id, current_user) is ticket


def test_inaccessible_and_missing_tickets_have_identical_not_found_errors(
    db: Session,
) -> None:
    business_a = add_business(db)
    customer_a = add_user(db, business_a, UserRole.CUSTOMER)
    other_customer_a = add_user(db, business_a, UserRole.CUSTOMER)
    business_b = add_business(db)
    admin_b = add_user(db, business_b, UserRole.ADMIN)
    ticket = add_ticket(db, business_a, customer_a)

    errors: list[tuple[int, str, str, object]] = []
    for ticket_id, current_user in (
        (ticket.id, admin_b),
        (ticket.id, other_customer_a),
        (uuid.uuid4(), customer_a),
    ):
        with pytest.raises(AppError) as denied:
            get_authorized_ticket(db, ticket_id, current_user)
        errors.append(error_signature(denied.value))

    assert (
        errors
        == [
            (404, "TICKET_NOT_FOUND", "Ticket not found.", None),
        ]
        * 3
    )


def test_ticket_resolver_rejects_unsupported_database_role(db: Session) -> None:
    business = add_business(db)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)
    customer.role = "unsupported"

    with pytest.raises(AppError) as denied:
        get_authorized_ticket(db, ticket.id, customer)

    assert denied.value.status_code == 403
    assert denied.value.code == "FORBIDDEN"


def test_assignment_policy_allows_admin_and_agent_self_assignment(
    db: Session,
) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)

    assert get_authorized_assignment_agent(db, ticket, admin, agent.id) is agent
    assert get_authorized_assignment_agent(db, ticket, agent, agent.id) is agent


def test_assignment_policy_rejects_cross_business_and_non_agent_targets(
    db: Session,
) -> None:
    business_a = add_business(db)
    admin_a = add_user(db, business_a, UserRole.ADMIN)
    customer_a = add_user(db, business_a, UserRole.CUSTOMER)
    ticket = add_ticket(db, business_a, customer_a)
    business_b = add_business(db)
    agent_b = add_user(db, business_b, UserRole.AGENT)

    errors: list[tuple[int, str, str, object]] = []
    for target_id in (agent_b.id, customer_a.id):
        with pytest.raises(AppError) as denied:
            get_authorized_assignment_agent(db, ticket, admin_a, target_id)
        errors.append(error_signature(denied.value))

    assert (
        errors
        == [
            (404, "RESOURCE_NOT_FOUND", "Resource not found.", None),
        ]
        * 2
    )


def test_assignment_policy_rejects_agent_assigning_other_and_customer(
    db: Session,
) -> None:
    business = add_business(db)
    first_agent = add_user(db, business, UserRole.AGENT)
    second_agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)

    for actor in (first_agent, customer):
        with pytest.raises(AppError) as denied:
            get_authorized_assignment_agent(db, ticket, actor, second_agent.id)
        assert denied.value.status_code == 403
        assert denied.value.code == "FORBIDDEN"


def test_assignment_and_status_policies_hide_ticket_from_cross_tenant_staff(
    db: Session,
) -> None:
    business_a = add_business(db)
    customer_a = add_user(db, business_a, UserRole.CUSTOMER)
    ticket_a = add_ticket(db, business_a, customer_a)
    business_b = add_business(db)
    admin_b = add_user(db, business_b, UserRole.ADMIN)
    agent_b = add_user(db, business_b, UserRole.AGENT)

    with pytest.raises(AppError) as assignment_denied:
        get_authorized_assignment_agent(db, ticket_a, admin_b, agent_b.id)
    with pytest.raises(AppError) as status_denied:
        authorize_ticket_status_update(ticket_a, admin_b, TicketStatus.IN_PROGRESS)

    assert error_signature(assignment_denied.value) == (
        404,
        "TICKET_NOT_FOUND",
        "Ticket not found.",
        None,
    )
    assert error_signature(status_denied.value) == error_signature(
        assignment_denied.value
    )


def test_status_policy_allows_staff_and_only_customer_reopen(db: Session) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer, status=TicketStatus.RESOLVED)

    authorize_ticket_status_update(ticket, admin, TicketStatus.CLOSED)
    authorize_ticket_status_update(ticket, agent, TicketStatus.CLOSED)
    authorize_ticket_status_update(ticket, customer, TicketStatus.OPEN)

    with pytest.raises(AppError) as denied:
        authorize_ticket_status_update(ticket, customer, TicketStatus.CLOSED)
    assert denied.value.status_code == 403
    assert denied.value.code == "FORBIDDEN"


def test_status_policy_rejects_other_customer_and_closed_ticket(db: Session) -> None:
    business = add_business(db)
    owner = add_user(db, business, UserRole.CUSTOMER)
    other_customer = add_user(db, business, UserRole.CUSTOMER)
    resolved = add_ticket(db, business, owner, status=TicketStatus.RESOLVED)
    closed = add_ticket(db, business, owner, status=TicketStatus.CLOSED)

    with pytest.raises(AppError) as hidden:
        authorize_ticket_status_update(resolved, other_customer, TicketStatus.OPEN)
    assert hidden.value.status_code == 404
    assert hidden.value.code == "TICKET_NOT_FOUND"

    with pytest.raises(AppError) as terminal:
        authorize_ticket_status_update(closed, owner, TicketStatus.OPEN)
    assert terminal.value.status_code == 409
    assert terminal.value.code == "TICKET_CLOSED"
