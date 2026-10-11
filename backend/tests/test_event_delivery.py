"""Delivery-time authorization regressions (no database or network)."""

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.security import create_access_token, create_refresh_token
from app.models import TicketStatus, UserRole
from app.schemas.message import MessagePublic
from app.websocket import events
from app.websocket.manager import ConnectionManager
from tests.test_websocket_manager import FakeWebSocket


@pytest.mark.parametrize("event_type", ["status", "message"])
def test_room_events_revalidate_and_remove_stale_recipients(monkeypatch, event_type):
    async def run():
        manager = ConnectionManager()
        monkeypatch.setattr(events, "connection_manager", manager)
        ticket_id = uuid.uuid4()
        allowed, stale = FakeWebSocket(), FakeWebSocket()
        await manager.connect(ticket_id, allowed, "valid")
        await manager.connect(ticket_id, stale, "revoked")
        calls = []

        def authorize(factory, subscriptions, room_id, audience, excluded):
            calls.append((subscriptions, room_id))
            return {allowed}, {stale}

        monkeypatch.setattr(events, "_room_recipients", authorize)
        now = datetime.now(UTC)
        if event_type == "status":
            await events.broadcast_ticket_status_changed(
                object(),
                ticket_id,
                TicketStatus.RESOLVED,
                now,
            )
        else:
            await events.broadcast_message_created(
                object(),
                MessagePublic(
                    id=uuid.uuid4(),
                    sequence="1",
                    ticket_id=ticket_id,
                    sender_id=uuid.uuid4(),
                    sender_name="Agent",
                    sender_role="agent",
                    body="Private",
                    created_at=now,
                    read_by=[],
                    attachment=None,
                ),
            )
        assert calls and calls[0][1] == ticket_id
        assert len(allowed.events) == 1
        assert stale.events == []
        assert stale.closed == 1008
        assert await manager.connection_count(ticket_id) == 1
        await manager.disconnect(ticket_id, allowed)

    asyncio.run(run())


@pytest.mark.parametrize(
    "change", ["role", "business", "owner", "deleted", "refresh", "invalid"]
)
def test_room_authorization_uses_current_database_state(monkeypatch, change):
    business_id, user_id, ticket_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=user_id, business_id=business_id, role=UserRole.AGENT)
    ticket = SimpleNamespace(business_id=business_id, customer_id=uuid.uuid4())
    token = create_access_token(user_id, business_id, UserRole.AGENT)
    if change == "role":
        user.role = UserRole.CUSTOMER
    elif change == "business":
        user.business_id = uuid.uuid4()
    elif change == "owner":
        user.role = UserRole.CUSTOMER
        token = create_access_token(user_id, business_id, UserRole.CUSTOMER)
    elif change == "refresh":
        token = create_refresh_token(user_id, business_id, UserRole.AGENT)
    elif change == "invalid":
        token = "invalid"
    db = MagicMock()
    db.__enter__.return_value = db
    db.get.return_value = ticket
    db.scalars.return_value = [] if change == "deleted" else [user]
    socket = FakeWebSocket()
    recipients, invalid = events._room_recipients(
        lambda: db, {socket: token}, ticket_id, None, None
    )
    assert recipients == set()
    assert invalid == {socket}


def test_typing_excludes_sender_and_receipts_only_reach_selected_authors():
    business_id, ticket_id = uuid.uuid4(), uuid.uuid4()
    owner = SimpleNamespace(
        id=uuid.uuid4(), business_id=business_id, role=UserRole.CUSTOMER
    )
    agent = SimpleNamespace(
        id=uuid.uuid4(), business_id=business_id, role=UserRole.AGENT
    )
    admin = SimpleNamespace(
        id=uuid.uuid4(), business_id=business_id, role=UserRole.ADMIN
    )
    users = [owner, agent, admin]
    sockets = [FakeWebSocket() for _ in users]
    db = MagicMock()
    db.__enter__.return_value = db
    db.get.return_value = SimpleNamespace(business_id=business_id, customer_id=owner.id)
    db.scalars.return_value = users
    tokens = {
        socket: create_access_token(user.id, user.business_id, user.role)
        for user, socket in zip(users, sockets)
    }
    recipients, invalid = events._room_recipients(
        lambda: db, tokens, ticket_id, None, owner.id
    )
    assert recipients == {sockets[1], sockets[2]}
    assert invalid == set()
    recipients, invalid = events._room_recipients(
        lambda: db, tokens, ticket_id, {agent.id}, None
    )
    assert recipients == {sockets[1]}
    assert invalid == set()


def test_list_delivery_uses_current_ticket_ownership(monkeypatch):
    """A delayed committed event must not use its old ownership snapshot."""

    async def run():
        manager = ConnectionManager()
        monkeypatch.setattr(events, "connection_manager", manager)
        socket = FakeWebSocket()
        await manager.subscribe(socket, "valid")
        ticket_id = uuid.uuid4()
        current = SimpleNamespace(business_id=uuid.uuid4(), customer_id=uuid.uuid4())
        db = MagicMock()
        db.__enter__.return_value = db
        db.get.return_value = current
        factory = MagicMock(return_value=db)
        observed = []

        def recipients(factory, subscriptions, business_id, customer_id, recipient):
            observed.append((business_id, customer_id))
            return {socket}, set()

        monkeypatch.setattr(events, "_list_recipients", recipients)
        await events.broadcast_ticket_list_event(
            factory,
            "ticket.message_created",
            ticket_id,
            uuid.uuid4(),
            uuid.uuid4(),
            datetime.now(UTC),
        )
        assert observed == [(current.business_id, current.customer_id)]
        assert len(socket.events) == 1
        await manager.unsubscribe(socket)

    asyncio.run(run())
