import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import (
    Business,
    Message,
    Ticket,
    TicketPriority,
    TicketStatus,
    User,
    UserRole,
)
from app.schemas.ticket import TicketCreateRequest, TicketUpdateRequest
from app.services.tickets import create_ticket, update_ticket


@pytest.fixture(scope="session")
def ticket_engine() -> Iterator[Engine]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.fail("TEST_DATABASE_URL must point to a disposable PostgreSQL database")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail(
            "M4 tests require a PostgreSQL database whose name ends with '_test'"
        )
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(ticket_engine: Engine) -> Iterator[Session]:
    connection = ticket_engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_business(db: Session, name: str = "Ticket Business") -> Business:
    business = Business(name=name, slug=f"ticket-{uuid.uuid4()}")
    db.add(business)
    db.commit()
    db.refresh(business)
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
    db.commit()
    db.refresh(user)
    return user


def add_ticket(
    db: Session,
    business: Business,
    customer: User,
    *,
    status: TicketStatus = TicketStatus.OPEN,
    assigned_agent: User | None = None,
    subject: str = "Need support",
    updated_at: datetime | None = None,
) -> Ticket:
    ticket = Ticket(
        business=business,
        customer=customer,
        assigned_agent=assigned_agent,
        subject=subject,
        category="account",
        priority=TicketPriority.HIGH,
        status=status,
    )
    if updated_at is not None:
        ticket.updated_at = updated_at
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def bearer(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.business_id, user.role)
    return {"Authorization": f"Bearer {token}"}


def error_signature(response: object) -> tuple[int, str, object]:
    payload = getattr(response, "json")()
    return (
        getattr(response, "status_code"),
        payload["error"]["code"],
        payload["error"]["details"],
    )


def test_openapi_contains_only_the_four_m4_ticket_operations(
    client: TestClient,
) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/tickets"]) == {"get", "post"}
    assert set(paths["/tickets/{ticket_id}"]) == {"get", "patch"}
    for path in ("/tickets", "/tickets/{ticket_id}"):
        for operation in paths[path].values():
            assert operation["security"] == [{"HTTPBearer": []}]


def test_create_ticket_derives_identity_and_persists_first_message(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    customer = add_user(db, business, UserRole.CUSTOMER)

    response = client.post(
        "/tickets",
        headers=bearer(customer),
        json={
            "subject": "  Cannot sign in  ",
            "category": " account ",
            "priority": "high",
            "message": "  Please help me  ",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["business_id"] == str(business.id)
    assert data["customer_id"] == str(customer.id)
    assert data["assigned_agent_id"] is None
    assert data["status"] == "open"
    assert data["subject"] == "Cannot sign in"
    message = db.scalar(
        select(Message).where(Message.ticket_id == uuid.UUID(data["id"]))
    )
    assert message is not None
    assert message.sender_id == customer.id
    assert message.body == "Please help me"
    assert "password" not in response.text.lower()


def test_create_ticket_rejects_staff_and_client_controlled_fields(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    payload = {
        "subject": "Issue",
        "category": "account",
        "priority": "low",
        "message": "Help",
    }

    forbidden = [
        client.post("/tickets", headers=bearer(staff), json=payload)
        for staff in (admin, agent)
    ]
    forged = client.post(
        "/tickets",
        headers=bearer(customer),
        json={**payload, "business_id": str(uuid.uuid4())},
    )
    invalid_priority = client.post(
        "/tickets",
        headers=bearer(customer),
        json={**payload, "priority": "urgent"},
    )

    assert [error_signature(response)[:2] for response in forbidden] == [
        (403, "FORBIDDEN")
    ] * 2
    assert error_signature(forged)[:2] == (422, "VALIDATION_ERROR")
    assert error_signature(invalid_priority)[:2] == (422, "VALIDATION_ERROR")


def test_create_ticket_rolls_back_ticket_and_message_on_commit_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    business = add_business(db)
    customer = add_user(db, business, UserRole.CUSTOMER)

    def fail_after_flush() -> None:
        db.flush()
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(db, "commit", fail_after_flush)

    with pytest.raises(RuntimeError, match="forced commit failure"):
        create_ticket(
            db,
            customer,
            TicketCreateRequest(
                subject="Atomic creation",
                category="account",
                priority=TicketPriority.HIGH,
                message="Neither row may remain.",
            ),
        )

    assert (
        db.scalars(select(Ticket).where(Ticket.subject == "Atomic creation")).all()
        == []
    )
    assert (
        db.scalars(
            select(Message).where(Message.body == "Neither row may remain.")
        ).all()
        == []
    )


def test_list_tickets_enforces_tenant_owner_filter_and_order(
    client: TestClient, db: Session
) -> None:
    business_a = add_business(db, "Alpha")
    admin_a = add_user(db, business_a, UserRole.ADMIN)
    agent_a = add_user(db, business_a, UserRole.AGENT)
    owner = add_user(db, business_a, UserRole.CUSTOMER)
    other_customer = add_user(db, business_a, UserRole.CUSTOMER)
    customer_without_tickets = add_user(db, business_a, UserRole.CUSTOMER)
    business_b = add_business(db, "Beta")
    owner_b = add_user(db, business_b, UserRole.CUSTOMER)
    now = datetime.now(UTC)
    older = add_ticket(
        db,
        business_a,
        owner,
        subject="Older",
        updated_at=now - timedelta(minutes=1),
    )
    newer = add_ticket(
        db,
        business_a,
        other_customer,
        status=TicketStatus.RESOLVED,
        subject="Newer",
        updated_at=now,
    )
    add_ticket(db, business_b, owner_b, subject="Foreign")

    admin_response = client.get("/tickets", headers=bearer(admin_a))
    agent_response = client.get("/tickets", headers=bearer(agent_a))
    customer_response = client.get("/tickets", headers=bearer(owner))
    empty_response = client.get("/tickets", headers=bearer(customer_without_tickets))
    filtered = client.get("/tickets?status=resolved", headers=bearer(admin_a))

    assert [item["id"] for item in admin_response.json()["data"]] == [
        str(newer.id),
        str(older.id),
    ]
    assert agent_response.json()["data"] == admin_response.json()["data"]
    assert [item["id"] for item in customer_response.json()["data"]] == [str(older.id)]
    assert empty_response.json() == {"data": []}
    assert [item["id"] for item in filtered.json()["data"]] == [str(newer.id)]
    invalid = client.get("/tickets?status=unknown", headers=bearer(admin_a))
    assert error_signature(invalid)[:2] == (422, "VALIDATION_ERROR")


def test_detail_hides_foreign_and_other_customer_tickets(
    client: TestClient, db: Session
) -> None:
    business_a = add_business(db, "Alpha")
    admin_a = add_user(db, business_a, UserRole.ADMIN)
    agent_a = add_user(db, business_a, UserRole.AGENT)
    owner = add_user(db, business_a, UserRole.CUSTOMER)
    other_customer = add_user(db, business_a, UserRole.CUSTOMER)
    business_b = add_business(db, "Beta")
    admin_b = add_user(db, business_b, UserRole.ADMIN)
    ticket = add_ticket(db, business_a, owner)

    owner_response = client.get(f"/tickets/{ticket.id}", headers=bearer(owner))
    staff_responses = [
        client.get(f"/tickets/{ticket.id}", headers=bearer(staff))
        for staff in (admin_a, agent_a)
    ]
    hidden = [
        client.get(f"/tickets/{ticket.id}", headers=bearer(other_customer)),
        client.get(f"/tickets/{ticket.id}", headers=bearer(admin_b)),
        client.get(f"/tickets/{uuid.uuid4()}", headers=bearer(owner)),
    ]

    assert owner_response.status_code == 200
    assert [response.status_code for response in staff_responses] == [200, 200]
    assert owner_response.json()["data"]["customer"]["id"] == str(owner.id)
    assert [error_signature(response) for response in hidden] == [
        (404, "TICKET_NOT_FOUND", None)
    ] * 3


def test_staff_status_lifecycle_and_customer_reopen(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)

    for actor, requested in (
        (admin, TicketStatus.IN_PROGRESS),
        (admin, TicketStatus.RESOLVED),
        (customer, TicketStatus.OPEN),
    ):
        response = client.patch(
            f"/tickets/{ticket.id}",
            headers=bearer(actor),
            json={"status": requested.value},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == requested

    skipped = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(admin),
        json={"status": "resolved"},
    )
    assert error_signature(skipped)[:2] == (409, "INVALID_STATUS_TRANSITION")


def test_closed_same_status_is_noop_but_closed_is_terminal(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer, status=TicketStatus.CLOSED)
    original_updated_at = ticket.updated_at

    no_op = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(admin),
        json={"status": "closed"},
    )
    terminal = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(admin),
        json={"status": "open"},
    )

    assert no_op.status_code == 200
    assert (
        datetime.fromisoformat(no_op.json()["data"]["updated_at"])
        == original_updated_at
    )
    assert error_signature(terminal)[:2] == (409, "TICKET_CLOSED")


def test_admin_assignment_agent_claim_and_conflict(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    first_agent = add_user(db, business, UserRole.AGENT)
    second_agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)

    assigned = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(admin),
        json={"assigned_agent_id": str(first_agent.id)},
    )
    conflict = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(second_agent),
        json={"assigned_agent_id": str(second_agent.id)},
    )
    reassigned = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(admin),
        json={"assigned_agent_id": str(second_agent.id)},
    )

    assert assigned.status_code == 200
    assert assigned.json()["data"]["assigned_agent"]["id"] == str(first_agent.id)
    assert error_signature(conflict)[:2] == (409, "ASSIGNMENT_CONFLICT")
    assert reassigned.status_code == 200
    assert reassigned.json()["data"]["assigned_agent_id"] == str(second_agent.id)


def test_agent_self_claim_and_assignment_role_denials(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    first_agent = add_user(db, business, UserRole.AGENT)
    second_agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)

    assign_other = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(first_agent),
        json={"assigned_agent_id": str(second_agent.id)},
    )
    customer_assignment = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(customer),
        json={"assigned_agent_id": str(first_agent.id)},
    )
    self_claim = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(first_agent),
        json={"assigned_agent_id": str(first_agent.id)},
    )
    keep_self = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(first_agent),
        json={"assigned_agent_id": str(first_agent.id)},
    )

    assert error_signature(assign_other)[:2] == (403, "FORBIDDEN")
    assert error_signature(customer_assignment)[:2] == (403, "FORBIDDEN")
    assert self_claim.status_code == 200
    assert self_claim.json()["data"]["assigned_agent_id"] == str(first_agent.id)
    assert keep_self.status_code == 200


def test_simultaneous_agent_claims_have_one_winner(
    ticket_engine: Engine,
) -> None:
    setup = Session(ticket_engine, expire_on_commit=False)
    business = add_business(setup, "Concurrent Claims")
    first_agent = add_user(setup, business, UserRole.AGENT)
    second_agent = add_user(setup, business, UserRole.AGENT)
    customer = add_user(setup, business, UserRole.CUSTOMER)
    ticket = add_ticket(setup, business, customer)
    business_id = business.id
    ticket_id = ticket.id
    agent_ids = (first_agent.id, second_agent.id)
    setup.close()
    barrier = Barrier(2)

    def claim(agent_id: uuid.UUID) -> tuple[str, uuid.UUID | int, str | None]:
        with Session(ticket_engine, expire_on_commit=False) as session:
            agent = session.get(User, agent_id)
            assert agent is not None
            barrier.wait()
            try:
                updated = update_ticket(
                    session,
                    ticket_id,
                    agent,
                    TicketUpdateRequest(assigned_agent_id=agent_id),
                )
                assert updated.assigned_agent_id is not None
                return ("success", updated.assigned_agent_id, None)
            except AppError as exc:
                return ("error", exc.status_code, exc.code)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, agent_ids))

        successes = [result for result in results if result[0] == "success"]
        conflicts = [result for result in results if result[0] == "error"]
        assert len(successes) == 1
        assert conflicts == [("error", 409, "ASSIGNMENT_CONFLICT")]

        with Session(ticket_engine) as verification:
            persisted = verification.get(Ticket, ticket_id)
            assert persisted is not None
            assert persisted.assigned_agent_id == successes[0][1]
    finally:
        with Session(ticket_engine) as cleanup:
            cleanup.execute(delete(Ticket).where(Ticket.id == ticket_id))
            cleanup.execute(delete(User).where(User.business_id == business_id))
            cleanup.execute(delete(Business).where(Business.id == business_id))
            cleanup.commit()


def test_assignment_target_is_tenant_and_role_scoped(
    client: TestClient, db: Session
) -> None:
    business_a = add_business(db, "Alpha")
    admin_a = add_user(db, business_a, UserRole.ADMIN)
    customer_a = add_user(db, business_a, UserRole.CUSTOMER)
    ticket = add_ticket(db, business_a, customer_a)
    business_b = add_business(db, "Beta")
    agent_b = add_user(db, business_b, UserRole.AGENT)

    responses = [
        client.patch(
            f"/tickets/{ticket.id}",
            headers=bearer(admin_a),
            json={"assigned_agent_id": str(target_id)},
        )
        for target_id in (customer_a.id, agent_b.id)
    ]

    assert [error_signature(response) for response in responses] == [
        (404, "RESOURCE_NOT_FOUND", None)
    ] * 2


def test_combined_patch_is_atomic_and_request_shape_is_strict(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    admin = add_user(db, business, UserRole.ADMIN)
    agent = add_user(db, business, UserRole.AGENT)
    customer = add_user(db, business, UserRole.CUSTOMER)
    ticket = add_ticket(db, business, customer)

    invalid = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(admin),
        json={
            "assigned_agent_id": str(agent.id),
            "status": "resolved",
        },
    )
    db.refresh(ticket)
    empty = client.patch(f"/tickets/{ticket.id}", headers=bearer(admin), json={})
    null_assignment = client.patch(
        f"/tickets/{ticket.id}",
        headers=bearer(admin),
        json={"assigned_agent_id": None},
    )

    assert error_signature(invalid)[:2] == (409, "INVALID_STATUS_TRANSITION")
    assert ticket.assigned_agent_id is None
    assert ticket.status == TicketStatus.OPEN
    assert error_signature(empty)[:2] == (422, "VALIDATION_ERROR")
    assert error_signature(null_assignment)[:2] == (422, "VALIDATION_ERROR")


def test_customer_status_permissions_and_cross_customer_reopen(
    client: TestClient, db: Session
) -> None:
    business = add_business(db)
    owner = add_user(db, business, UserRole.CUSTOMER)
    other_customer = add_user(db, business, UserRole.CUSTOMER)
    open_ticket = add_ticket(db, business, owner)
    resolved_ticket = add_ticket(
        db,
        business,
        owner,
        status=TicketStatus.RESOLVED,
    )

    normal_transition = client.patch(
        f"/tickets/{open_ticket.id}",
        headers=bearer(owner),
        json={"status": "in_progress"},
    )
    cross_customer_reopen = client.patch(
        f"/tickets/{resolved_ticket.id}",
        headers=bearer(other_customer),
        json={"status": "open"},
    )

    assert error_signature(normal_transition)[:2] == (403, "FORBIDDEN")
    assert error_signature(cross_customer_reopen)[:2] == (
        404,
        "TICKET_NOT_FOUND",
    )
