import asyncio
import os
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

import app.api.routes.tickets as ticket_routes
import app.api.routes.websocket as websocket_routes
from app.core.config import get_settings
from app.core.errors import AppError
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
from app.services import messages as message_service
from app.services.messages import create_message
from app.websocket.manager import connection_manager


@dataclass(frozen=True)
class ChatScenario:
    business: Business
    other_business: Business
    owner: User
    other_customer: User
    agent: User
    admin: User
    external_agent: User
    external_customer: User
    open_ticket: Ticket
    resolved_ticket: Ticket
    closed_ticket: Ticket
    external_ticket: Ticket


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
    external_customer = _user(
        other_business, UserRole.CUSTOMER, suffix, "external-customer"
    )
    open_ticket = _ticket(business, owner, TicketStatus.OPEN, "Open ticket")
    resolved_ticket = _ticket(business, owner, TicketStatus.RESOLVED, "Resolved ticket")
    closed_ticket = _ticket(business, owner, TicketStatus.CLOSED, "Closed ticket")
    external_ticket = _ticket(
        other_business, external_customer, TicketStatus.OPEN, "External ticket"
    )
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
                external_customer,
                open_ticket,
                resolved_ticket,
                closed_ticket,
                external_ticket,
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
        external_customer=external_customer,
        open_ticket=open_ticket,
        resolved_ticket=resolved_ticket,
        closed_ticket=closed_ticket,
        external_ticket=external_ticket,
    )
    yield result

    ticket_ids = [
        open_ticket.id,
        resolved_ticket.id,
        closed_ticket.id,
        external_ticket.id,
    ]
    user_ids = [
        owner.id,
        other_customer.id,
        agent.id,
        admin.id,
        external_agent.id,
        external_customer.id,
    ]
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


def _expired_access(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "business_id": str(user.business_id),
            "role": user.role,
            "type": "access",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


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


def test_history_supports_admin_closed_ticket_and_deterministic_equal_timestamps(
    client: TestClient,
    session_factory: sessionmaker[Session],
    scenario: ChatScenario,
) -> None:
    created_at = datetime.now(UTC) - timedelta(seconds=10)
    messages = [
        Message(
            id=uuid.uuid4(),
            ticket_id=scenario.closed_ticket.id,
            sender_id=scenario.owner.id,
            body="Equal timestamp A",
            created_at=created_at,
        ),
        Message(
            id=uuid.uuid4(),
            ticket_id=scenario.closed_ticket.id,
            sender_id=scenario.agent.id,
            body="Equal timestamp B",
            created_at=created_at,
        ),
    ]
    with session_factory() as db:
        db.add_all(messages)
        db.commit()

    response = client.get(
        f"/tickets/{scenario.closed_ticket.id}/messages",
        headers={"Authorization": f"Bearer {_access(scenario.admin)}"},
    )
    missing = client.get(
        f"/tickets/{uuid.uuid4()}/messages",
        headers={"Authorization": f"Bearer {_access(scenario.owner)}"},
    )
    unauthenticated = client.get(f"/tickets/{scenario.closed_ticket.id}/messages")

    expected = [item.body for item in sorted(messages, key=lambda item: item.id)]
    assert response.status_code == 200
    assert [item["body"] for item in response.json()["data"]] == expected
    assert all(
        datetime.fromisoformat(item["created_at"]).tzinfo is not None
        for item in response.json()["data"]
    )
    assert missing.status_code == 404
    assert unauthenticated.status_code == 401


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


def test_handshake_rejects_expired_and_deleted_user_tokens(
    client: TestClient,
    session_factory: sessionmaker[Session],
    scenario: ChatScenario,
) -> None:
    deleted = _user(
        scenario.business,
        UserRole.CUSTOMER,
        uuid.uuid4(),
        "deleted",
    )
    with session_factory() as db:
        db.add(deleted)
        db.commit()
    deleted_token = _access(deleted)
    with session_factory() as db:
        stored = db.get(User, deleted.id)
        assert stored is not None
        db.delete(stored)
        db.commit()

    for token in (_expired_access(scenario.owner), deleted_token):
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                f"/ws/tickets/{scenario.open_ticket.id}?token={token}",
                headers={"origin": _origin()},
            ):
                pass
        assert error.value.code == 1008

    assert scenario.open_ticket.id not in connection_manager._rooms


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


def test_agent_message_survives_disconnect_and_is_returned_by_history(
    client: TestClient, scenario: ChatScenario
) -> None:
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.agent),
        headers={"origin": _origin()},
    ) as websocket:
        websocket.send_json({"type": "message.send", "body": "Agent persisted"})
        created = websocket.receive_json()

    history = client.get(
        f"/tickets/{scenario.open_ticket.id}/messages",
        headers={"Authorization": f"Bearer {_access(scenario.owner)}"},
    )

    assert created["type"] == "message.created"
    assert created["data"]["sender_id"] == str(scenario.agent.id)
    assert created["data"]["sender_name"] == scenario.agent.name
    assert created["data"]["sender_role"] == "agent"
    assert history.status_code == 200
    assert created["data"] in history.json()["data"]


def test_malformed_events_are_sanitized_and_connection_can_continue(
    client: TestClient, scenario: ChatScenario
) -> None:
    invalid_payloads: list[object] = [
        [],
        "scalar",
        {"type": "unsupported", "body": "hello"},
        {"type": "message.send"},
        {"type": "message.send", "body": 42},
        {"type": "message.send", "body": "   "},
        {"type": "message.send", "body": "x" * 5001},
    ]
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.owner),
        headers={"origin": _origin()},
    ) as websocket:
        websocket.send_text("{not-json")
        malformed_json = websocket.receive_json()
        for payload in invalid_payloads:
            websocket.send_json(payload)
            event = websocket.receive_json()
            assert event["type"] == "error"
            assert event["data"]["code"] == "VALIDATION_ERROR"

        websocket.send_json({"type": "message.send", "body": "Still connected"})
        created = websocket.receive_json()

    assert malformed_json["type"] == "error"
    assert malformed_json["data"]["code"] == "VALIDATION_ERROR"
    assert created["type"] == "message.created"
    assert created["data"]["body"] == "Still connected"


def test_broadcast_is_ticket_scoped_with_two_live_rooms(
    client: TestClient, scenario: ChatScenario
) -> None:
    headers = {"origin": _origin()}
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.owner), headers=headers
    ) as open_socket:
        with client.websocket_connect(
            _ws_url(scenario.resolved_ticket, scenario.owner), headers=headers
        ) as other_room_socket:
            with client.websocket_connect(
                _ws_url(scenario.external_ticket, scenario.external_agent),
                headers=headers,
            ) as external_room_socket:
                open_socket.send_json(
                    {"type": "message.send", "body": "Open room only"}
                )
                event = open_socket.receive_json()
                assert event["type"] == "message.created"
                assert event["data"]["ticket_id"] == str(scenario.open_ticket.id)
                for isolated_socket in (other_room_socket, external_room_socket):
                    transport = getattr(isolated_socket, "_send_rx")
                    assert transport.statistics().current_buffer_used == 0


def test_current_database_role_is_enforced_on_each_send(
    client: TestClient,
    session_factory: sessionmaker[Session],
    scenario: ChatScenario,
) -> None:
    try:
        with client.websocket_connect(
            _ws_url(scenario.open_ticket, scenario.agent),
            headers={"origin": _origin()},
        ) as websocket:
            with session_factory() as db:
                stored = db.get(User, scenario.agent.id)
                assert stored is not None
                stored.role = UserRole.ADMIN
                db.commit()
            websocket.send_json({"type": "message.send", "body": "Revoked role"})
            event = websocket.receive_json()
            assert event["type"] == "error"
            assert event["data"]["code"] == "FORBIDDEN"
    finally:
        with session_factory() as db:
            stored = db.get(User, scenario.agent.id)
            assert stored is not None
            stored.role = UserRole.AGENT
            db.commit()


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


def test_status_event_is_not_scheduled_for_noop_assignment_rejection_or_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    scenario: ChatScenario,
) -> None:
    broadcaster = AsyncMock()
    monkeypatch.setattr(ticket_routes, "broadcast_ticket_status_changed", broadcaster)
    agent_auth = {"Authorization": f"Bearer {_access(scenario.agent)}"}

    no_op = client.patch(
        f"/tickets/{scenario.open_ticket.id}",
        headers=agent_auth,
        json={"status": "open"},
    )
    assignment = client.patch(
        f"/tickets/{scenario.open_ticket.id}",
        headers=agent_auth,
        json={"assigned_agent_id": str(scenario.agent.id)},
    )
    invalid = client.patch(
        f"/tickets/{scenario.open_ticket.id}",
        headers=agent_auth,
        json={"status": "resolved"},
    )
    unauthorized = client.patch(
        f"/tickets/{scenario.open_ticket.id}",
        headers={"Authorization": f"Bearer {_access(scenario.other_customer)}"},
        json={"status": "open"},
    )

    def fail_before_commit(*args: object, **kwargs: object) -> object:
        raise RuntimeError("forced update failure")

    monkeypatch.setattr(ticket_routes, "update_ticket_with_result", fail_before_commit)
    with pytest.raises(RuntimeError, match="forced update failure"):
        client.patch(
            f"/tickets/{scenario.open_ticket.id}",
            headers=agent_auth,
            json={"status": "in_progress"},
        )

    assert no_op.status_code == 200
    assert assignment.status_code == 200
    assert invalid.status_code == 409
    assert unauthorized.status_code == 404
    broadcaster.assert_not_awaited()


def test_internal_message_failure_is_sanitized_and_never_broadcast(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    scenario: ChatScenario,
) -> None:
    broadcaster = AsyncMock()
    body = "Rolled back message"

    def fail_persistence(
        factory: sessionmaker[Session],
        token: str,
        ticket_id: uuid.UUID,
        message_body: str,
    ) -> object:
        del factory, token
        with session_factory() as db:
            current_user = db.get(User, scenario.owner.id)
            assert current_user is not None

            def fail_commit() -> None:
                db.flush()
                raise RuntimeError("database-secret-detail")

            monkeypatch.setattr(db, "commit", fail_commit)
            return create_message(db, ticket_id, current_user, message_body)

    monkeypatch.setattr(websocket_routes, "_persist_message", fail_persistence)
    monkeypatch.setattr(connection_manager, "broadcast", broadcaster)
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.owner),
        headers={"origin": _origin()},
    ) as websocket:
        websocket.send_json({"type": "message.send", "body": body})
        event = websocket.receive_json()
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_json()

    with session_factory() as db:
        stored_count = db.scalar(
            select(func.count(Message.id)).where(
                Message.ticket_id == scenario.open_ticket.id,
                Message.body == body,
            )
        )

    assert event == {
        "type": "error",
        "data": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred.",
        },
    }
    assert "database-secret-detail" not in str(event)
    assert error.value.code == 1011
    assert stored_count == 0
    broadcaster.assert_not_awaited()


def test_concurrent_messages_remain_consistent_in_postgresql(
    session_factory: sessionmaker[Session], scenario: ChatScenario
) -> None:
    bodies = {"Concurrent A", "Concurrent B"}

    def persist(body: str) -> uuid.UUID:
        with session_factory() as db:
            user = db.get(User, scenario.agent.id)
            assert user is not None
            return create_message(db, scenario.open_ticket.id, user, body).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = set(executor.map(persist, bodies))

    with session_factory() as db:
        stored = db.scalars(
            select(Message).where(
                Message.ticket_id == scenario.open_ticket.id,
                Message.body.in_(bodies),
            )
        ).all()

    assert len(ids) == 2
    assert {item.id for item in stored} == ids
    assert {item.body for item in stored} == bodies


def test_ticket_lock_prevents_message_commit_after_concurrent_close(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    scenario: ChatScenario,
) -> None:
    attempted_lock = threading.Event()
    original_authorize: Any = getattr(message_service, "get_authorized_ticket")

    def observed_authorize(
        db: Session,
        ticket_id: uuid.UUID,
        current_user: User,
        *,
        for_update: bool = False,
    ) -> Ticket:
        attempted_lock.set()
        return cast(
            Ticket,
            original_authorize(
                db,
                ticket_id,
                current_user,
                for_update=for_update,
            ),
        )

    monkeypatch.setattr(message_service, "get_authorized_ticket", observed_authorize)

    def persist() -> None:
        with session_factory() as worker_db:
            user = worker_db.get(User, scenario.owner.id)
            assert user is not None
            create_message(
                worker_db,
                scenario.resolved_ticket.id,
                user,
                "Raced with close",
            )

    with session_factory() as closing_db:
        locked = closing_db.scalar(
            select(Ticket)
            .where(Ticket.id == scenario.resolved_ticket.id)
            .with_for_update()
        )
        assert locked is not None
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(persist)
            assert attempted_lock.wait(timeout=5)
            locked.status = TicketStatus.CLOSED
            closing_db.commit()
            with pytest.raises(AppError) as error:
                future.result(timeout=5)

    with session_factory() as db:
        count = db.scalar(
            select(func.count(Message.id)).where(
                Message.ticket_id == scenario.resolved_ticket.id,
                Message.body == "Raced with close",
            )
        )
    assert error.value.code == "TICKET_CLOSED"
    assert count == 0


def test_disconnect_removes_live_room_membership(
    client: TestClient, scenario: ChatScenario
) -> None:
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.owner),
        headers={"origin": _origin()},
    ):
        assert (
            asyncio.run(connection_manager.connection_count(scenario.open_ticket.id))
            == 1
        )

    assert (
        asyncio.run(connection_manager.connection_count(scenario.open_ticket.id)) == 0
    )
