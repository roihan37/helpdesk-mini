import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db, get_session_factory
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


@dataclass(frozen=True)
class ChatScenario:
    business: Business
    other_business: Business
    owner: User
    other_customer: User
    agent: User
    admin: User
    external_agent: User
    open_ticket: Ticket
    resolved_ticket: Ticket
    closed_ticket: Ticket


@pytest.fixture(scope="module")
def chat_engine() -> Iterator[Engine]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.fail("TEST_DATABASE_URL must point to a disposable PostgreSQL database")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail("M5 tests require a PostgreSQL database ending with '_test'")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(chat_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=chat_engine, expire_on_commit=False)


@pytest.fixture
def scenario(session_factory: sessionmaker[Session]) -> Iterator[ChatScenario]:
    suffix = uuid.uuid4()
    business = Business(name="M5 Business", slug=f"m5-{suffix}")
    other_business = Business(name="M5 Other", slug=f"m5-other-{suffix}")
    owner = _user(business, UserRole.CUSTOMER, suffix, "owner")
    other_customer = _user(business, UserRole.CUSTOMER, suffix, "other")
    agent = _user(business, UserRole.AGENT, suffix, "agent")
    admin = _user(business, UserRole.ADMIN, suffix, "admin")
    external_agent = _user(other_business, UserRole.AGENT, suffix, "external")
    open_ticket = _ticket(business, owner, TicketStatus.OPEN, "Open ticket")
    resolved_ticket = _ticket(business, owner, TicketStatus.RESOLVED, "Resolved ticket")
    closed_ticket = _ticket(business, owner, TicketStatus.CLOSED, "Closed ticket")
    first_created_at = datetime.now(UTC) - timedelta(minutes=1)
    first = Message(
        ticket=open_ticket,
        sender=owner,
        body="First message",
        created_at=first_created_at,
    )
    second = Message(
        ticket=open_ticket,
        sender=agent,
        body="Second message",
        created_at=first_created_at + timedelta(seconds=1),
    )
    with session_factory() as db:
        db.add_all(
            [
                business,
                other_business,
                owner,
                other_customer,
                agent,
                admin,
                external_agent,
                open_ticket,
                resolved_ticket,
                closed_ticket,
                first,
                second,
            ]
        )
        db.commit()

    result = ChatScenario(
        business=business,
        other_business=other_business,
        owner=owner,
        other_customer=other_customer,
        agent=agent,
        admin=admin,
        external_agent=external_agent,
        open_ticket=open_ticket,
        resolved_ticket=resolved_ticket,
        closed_ticket=closed_ticket,
    )
    yield result

    ticket_ids = [open_ticket.id, resolved_ticket.id, closed_ticket.id]
    user_ids = [owner.id, other_customer.id, agent.id, admin.id, external_agent.id]
    with session_factory() as db:
        db.execute(delete(Message).where(Message.ticket_id.in_(ticket_ids)))
        db.execute(delete(Ticket).where(Ticket.id.in_(ticket_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.execute(
            delete(Business).where(Business.id.in_([business.id, other_business.id]))
        )
        db.commit()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(business: Business, role: UserRole, suffix: uuid.UUID, label: str) -> User:
    return User(
        business=business,
        name=f"M5 {label.title()}",
        email=f"m5-{label}-{suffix}@example.test",
        password_hash="not-a-plaintext-password",
        role=role,
    )


def _ticket(
    business: Business, owner: User, status: TicketStatus, subject: str
) -> Ticket:
    return Ticket(
        business=business,
        customer=owner,
        subject=subject,
        category="support",
        priority=TicketPriority.HIGH,
        status=status,
    )


def _access(user: User) -> str:
    return create_access_token(user.id, user.business_id, user.role)


def _refresh(user: User) -> str:
    return create_refresh_token(user.id, user.business_id, user.role)


def _origin() -> str:
    return str(get_settings().cors_origins[0]).rstrip("/")


def _ws_url(ticket: Ticket, user: User) -> str:
    return f"/ws/tickets/{ticket.id}?token={_access(user)}"


def test_history_is_ordered_and_enforces_viewer_scope(
    client: TestClient, scenario: ChatScenario
) -> None:
    owner_response = client.get(
        f"/tickets/{scenario.open_ticket.id}/messages",
        headers={"Authorization": f"Bearer {_access(scenario.owner)}"},
    )
    agent_response = client.get(
        f"/tickets/{scenario.open_ticket.id}/messages",
        headers={"Authorization": f"Bearer {_access(scenario.agent)}"},
    )
    other_customer_response = client.get(
        f"/tickets/{scenario.open_ticket.id}/messages",
        headers={"Authorization": f"Bearer {_access(scenario.other_customer)}"},
    )
    cross_tenant_response = client.get(
        f"/tickets/{scenario.open_ticket.id}/messages",
        headers={"Authorization": f"Bearer {_access(scenario.external_agent)}"},
    )
    refresh_response = client.get(
        f"/tickets/{scenario.open_ticket.id}/messages",
        headers={"Authorization": f"Bearer {_refresh(scenario.owner)}"},
    )

    assert owner_response.status_code == 200
    assert agent_response.status_code == 200
    assert [item["body"] for item in owner_response.json()["data"]] == [
        "First message",
        "Second message",
    ]
    assert set(owner_response.json()["data"][0]) == {
        "id",
        "ticket_id",
        "sender_id",
        "sender_name",
        "sender_role",
        "body",
        "created_at",
    }
    assert other_customer_response.status_code == 404
    assert cross_tenant_response.status_code == 404
    assert refresh_response.status_code == 401


@pytest.mark.parametrize("token_kind", ["missing", "invalid", "refresh"])
def test_handshake_rejects_missing_invalid_and_refresh_tokens(
    client: TestClient, scenario: ChatScenario, token_kind: str
) -> None:
    token = {
        "missing": "",
        "invalid": "not-a-jwt",
        "refresh": _refresh(scenario.owner),
    }[token_kind]
    separator = "?token=" if token_kind != "missing" else ""
    url = f"/ws/tickets/{scenario.open_ticket.id}{separator}{token}"

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(url, headers={"origin": _origin()}):
            pass
    assert error.value.code == 1008


def test_handshake_requires_allowed_origin_and_ticket_scope(
    client: TestClient, scenario: ChatScenario
) -> None:
    attempts = [
        (_ws_url(scenario.open_ticket, scenario.owner), {}),
        (
            _ws_url(scenario.open_ticket, scenario.owner),
            {"origin": "https://attacker.example"},
        ),
        (
            _ws_url(scenario.open_ticket, scenario.other_customer),
            {"origin": _origin()},
        ),
        (
            _ws_url(scenario.open_ticket, scenario.external_agent),
            {"origin": _origin()},
        ),
    ]

    for url, headers in attempts:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(url, headers=headers):
                pass
        assert error.value.code == 1008


def test_customer_message_commits_then_broadcasts_to_same_room_participants(
    client: TestClient,
    session_factory: sessionmaker[Session],
    scenario: ChatScenario,
) -> None:
    headers = {"origin": _origin()}
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.owner), headers=headers
    ) as customer_socket:
        with client.websocket_connect(
            _ws_url(scenario.open_ticket, scenario.agent), headers=headers
        ) as agent_socket:
            customer_socket.send_json(
                {"type": "message.send", "body": "  Live reply  "}
            )
            customer_event = customer_socket.receive_json()
            agent_event = agent_socket.receive_json()

    assert customer_event == agent_event
    assert customer_event["type"] == "message.created"
    assert customer_event["data"]["sender_id"] == str(scenario.owner.id)
    assert customer_event["data"]["sender_role"] == "customer"
    assert customer_event["data"]["body"] == "Live reply"
    with session_factory() as db:
        stored = db.scalar(
            select(Message).where(Message.id == uuid.UUID(customer_event["data"]["id"]))
        )
        ticket = db.get(Ticket, scenario.open_ticket.id)
        assert stored is not None
        assert stored.body == "Live reply"
        assert ticket is not None
        assert ticket.updated_at >= stored.created_at


def test_admin_is_read_only_and_payload_cannot_spoof_identity(
    client: TestClient, scenario: ChatScenario
) -> None:
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.admin),
        headers={"origin": _origin()},
    ) as websocket:
        websocket.send_json({"type": "message.send", "body": "Not allowed"})
        forbidden = websocket.receive_json()
        websocket.send_json(
            {
                "type": "message.send",
                "body": "Forged",
                "sender_id": str(scenario.agent.id),
            }
        )
        validation = websocket.receive_json()

    assert forbidden == {
        "type": "error",
        "data": {
            "code": "FORBIDDEN",
            "message": "You are not allowed to send messages to this ticket.",
        },
    }
    assert validation["type"] == "error"
    assert validation["data"]["code"] == "VALIDATION_ERROR"


def test_status_change_is_broadcast_and_new_message_uses_current_closed_state(
    client: TestClient, scenario: ChatScenario
) -> None:
    headers = {"origin": _origin()}
    auth = {"Authorization": f"Bearer {_access(scenario.agent)}"}
    with client.websocket_connect(
        _ws_url(scenario.resolved_ticket, scenario.owner), headers=headers
    ) as websocket:
        response = client.patch(
            f"/tickets/{scenario.resolved_ticket.id}",
            headers=auth,
            json={"status": "closed"},
        )
        status_event = websocket.receive_json()
        websocket.send_json({"type": "message.send", "body": "Too late"})
        closed_event = websocket.receive_json()

    assert response.status_code == 200
    assert status_event["type"] == "ticket.status_changed"
    assert status_event["data"]["ticket_id"] == str(scenario.resolved_ticket.id)
    assert status_event["data"]["status"] == "closed"
    assert closed_event["type"] == "error"
    assert closed_event["data"]["code"] == "TICKET_CLOSED"
