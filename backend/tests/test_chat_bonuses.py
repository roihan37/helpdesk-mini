"""B5–B7 real FastAPI/WebSocket/PostgreSQL checks on guarded disposable fixtures."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier

import pytest
from PIL import Image
from sqlalchemy import func, select
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.core.storage import LocalStorage
from app.models import Message, MessageAttachment, TicketReadState, User, UserRole
from app.services import attachments
from app.services.messages import create_message
from app.services.ticket_reads import get_unread_counts, mark_ticket_read
from tests import test_websocket_chat as chat_tests
from tests.test_websocket_chat import _access, _origin, _ws_url

# Reuse the existing database guards, overrides and scoped cleanup unchanged.
chat_engine = chat_tests.chat_engine
client = chat_tests.client
scenario = chat_tests.scenario
session_factory = chat_tests.session_factory


def headers(user):
    return {"Authorization": f"Bearer {_access(user)}"}


def history(client, ticket, user):
    response = client.get(f"/tickets/{ticket.id}/messages", headers=headers(user))
    assert response.status_code == 200
    return response.json()["data"]


def counts(client, user, **params):
    response = client.get("/tickets", headers=headers(user), params=params)
    assert response.status_code == 200
    return response.json()


def image_bytes(image_format="PNG"):
    output = BytesIO()
    Image.new("RGB", (8, 6), "blue").save(output, format=image_format)
    return output.getvalue()


@pytest.fixture
def private_storage(monkeypatch, tmp_path):
    storage = LocalStorage(tmp_path / "private")
    monkeypatch.setattr(attachments, "get_storage", lambda provider: storage)
    monkeypatch.setattr(get_settings(), "storage_provider", "local")
    return storage


def test_unread_is_private_persistent_and_paginated(client, scenario, session_factory):
    ticket = scenario.open_ticket
    for user in (scenario.owner, scenario.agent, scenario.admin):
        result = counts(client, user, search="Open ticket", page_size=1)
        assert result["pagination"]["total_items"] == 1
        assert result["data"][0]["unread_count"] == (2 if user == scenario.admin else 1)
    for user in (scenario.other_customer, scenario.external_agent):
        result = counts(client, user, search="Open ticket", page_size=1)
        assert result["pagination"]["total_items"] == 0
        assert result["data"] == []
    messages = history(client, ticket, scenario.owner)
    for boundary in (messages[-1]["id"], messages[-1]["id"], messages[0]["id"]):
        response = client.post(
            f"/tickets/{ticket.id}/read",
            headers=headers(scenario.owner),
            json={"last_message_id": boundary},
        )
        assert response.status_code == 200
        assert response.json()["data"]["unread_count"] == 0
    # A separate session and a fresh REST load preserve only this user's cursor.
    with session_factory() as db:
        state = db.get(TicketReadState, (scenario.owner.id, ticket.id))
        assert state.last_read_sequence == int(messages[-1]["sequence"])
        assert get_unread_counts(db, scenario.agent, [ticket.id])[ticket.id] == 1
    assert (
        counts(client, scenario.owner, search="Open ticket")["data"][0]["unread_count"]
        == 0
    )


@pytest.mark.parametrize("viewer", ["other_customer", "external_agent"])
def test_mark_read_inaccessible_ticket_is_404(client, scenario, viewer):
    boundary = history(client, scenario.open_ticket, scenario.owner)[-1]["id"]
    response = client.post(
        f"/tickets/{scenario.open_ticket.id}/read",
        headers=headers(getattr(scenario, viewer)),
        json={"last_message_id": boundary},
    )
    assert response.status_code == 404


def test_mark_read_auth_and_message_boundary_validation(
    client, scenario, session_factory
):
    path = f"/tickets/{scenario.open_ticket.id}/read"
    assert (
        client.post(path, json={"last_message_id": str(uuid.uuid4())}).status_code
        == 401
    )
    assert (
        client.post(
            path, headers=headers(scenario.owner), json={"last_message_id": "invalid"}
        ).status_code
        == 422
    )
    with session_factory() as db:
        external = create_message(
            db, scenario.external_ticket.id, scenario.external_agent, "Private"
        )
    assert (
        client.post(
            path,
            headers=headers(scenario.owner),
            json={"last_message_id": str(external.id)},
        ).status_code
        == 404
    )


def test_unread_counts_follow_multiple_pages_search_status_and_ownership(
    client, scenario, session_factory
):
    expected = {}
    for index in range(3):
        response = client.post(
            "/tickets",
            headers=headers(scenario.owner),
            json={
                "subject": f"Unread page {index}",
                "category": "support",
                "priority": "medium",
                "message": "Own first message",
            },
        )
        assert response.status_code == 201
        ticket_id = uuid.UUID(response.json()["data"]["id"])
        with session_factory() as db:
            for _ in range(index + 1):
                create_message(db, ticket_id, scenario.agent, "Unread reply")
        expected[str(ticket_id)] = index + 1
    private_ticket = client.post(
        "/tickets",
        headers=headers(scenario.other_customer),
        json={
            "subject": "Unread page private",
            "category": "support",
            "priority": "medium",
            "message": "Other customer",
        },
    )
    assert private_ticket.status_code == 201
    result = {}
    for page in range(1, 4):
        response = counts(
            client, scenario.owner, search="UNREAD PAGE", page=page, page_size=1
        )
        assert response["pagination"] == {
            "page": page,
            "page_size": 1,
            "total_items": 3,
            "total_pages": 3,
        }
        row = response["data"][0]
        result[row["id"]] = row["unread_count"]
    assert result == expected
    changed_id = next(iter(expected))
    assert (
        client.patch(
            f"/tickets/{changed_id}",
            headers=headers(scenario.admin),
            json={"status": "in_progress"},
        ).status_code
        == 200
    )
    filtered = counts(
        client, scenario.owner, search="unread page", status="in_progress"
    )
    assert filtered["pagination"]["total_items"] == 1
    assert filtered["data"][0]["id"] == changed_id
    assert filtered["data"][0]["unread_count"] == expected[changed_id]
    assert counts(client, scenario.external_agent, search="Unread page")["data"] == []


def test_concurrent_read_cursors_do_not_move_backwards_or_read_unseen_messages(
    client,
    scenario,
    session_factory,
):
    messages = history(client, scenario.open_ticket, scenario.owner)

    def acknowledge(boundary):
        with session_factory() as db:
            return mark_ticket_read(
                db, scenario.open_ticket.id, scenario.owner, uuid.UUID(boundary)
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(acknowledge, [messages[-1]["id"], messages[0]["id"]] * 4)
        )
    assert sum(result.changed for result in results) <= 2
    with session_factory() as db:
        state = db.get(TicketReadState, (scenario.owner.id, scenario.open_ticket.id))
        assert state.last_read_sequence == int(messages[-1]["sequence"])
        create_message(
            db,
            scenario.open_ticket.id,
            scenario.agent,
            "Arrived after observed boundary",
        )
    acknowledge(messages[-1]["id"])
    assert (
        counts(client, scenario.owner, search="Open ticket")["data"][0]["unread_count"]
        == 1
    )


def test_message_commit_racing_with_read_keeps_unobserved_message_unread(
    client, scenario, session_factory
):
    boundary = history(client, scenario.open_ticket, scenario.owner)[-1]
    barrier = Barrier(2)

    def write():
        barrier.wait(timeout=10)
        with session_factory() as db:
            return create_message(
                db, scenario.open_ticket.id, scenario.agent, "Concurrent unseen message"
            ).id

    def read():
        barrier.wait(timeout=10)
        with session_factory() as db:
            return mark_ticket_read(
                db, scenario.open_ticket.id, scenario.owner, uuid.UUID(boundary["id"])
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        written, acknowledged = pool.submit(write), pool.submit(read)
        message_id, result = written.result(timeout=15), acknowledged.result(timeout=15)
    assert result.changed
    with session_factory() as db:
        state = db.get(TicketReadState, (scenario.owner.id, scenario.open_ticket.id))
        assert state.last_read_sequence == int(boundary["sequence"])
        assert db.get(Message, message_id).sequence > state.last_read_sequence
        assert (
            get_unread_counts(db, scenario.owner, [scenario.open_ticket.id])[
                scenario.open_ticket.id
            ]
            == 1
        )


def test_receipts_are_recipient_specific_persisted_and_recovered_after_reconnect(
    client, scenario
):
    ticket, owner, agent = scenario.open_ticket, scenario.owner, scenario.agent
    messages = history(client, ticket, owner)
    with client.websocket_connect(
        _ws_url(ticket, owner), headers={"Origin": _origin()}
    ) as socket:
        response = client.post(
            f"/tickets/{ticket.id}/read",
            headers=headers(agent),
            json={"last_message_id": messages[-1]["id"]},
        )
        assert response.status_code == 200
        receipt = socket.receive_json()
        assert receipt["type"] == "message.read"
        assert receipt["data"]["user_id"] == str(agent.id)
    restored = history(client, ticket, owner)
    assert restored[0]["read_by"] == [
        {"user_id": str(agent.id), "name": agent.name, "role": "agent"}
    ]
    assert restored[1]["read_by"] == []  # Never expose another author's reader state.
    with client.websocket_connect(
        _ws_url(ticket, owner), headers={"Origin": _origin()}
    ) as socket:
        socket.send_json({"type": "message.send", "body": "Reconnect sentinel"})
        assert socket.receive_json()["type"] == "message.created"
    client.post(
        f"/tickets/{ticket.id}/read",
        headers=headers(scenario.admin),
        json={"last_message_id": messages[-1]["id"]},
    )
    assert history(client, ticket, owner)[0]["read_by"] == restored[0]["read_by"]


def test_typing_round_trip_identity_and_no_self_echo(client, scenario):
    ticket = scenario.open_ticket
    with client.websocket_connect(
        _ws_url(ticket, scenario.owner), headers={"Origin": _origin()}
    ) as owner:
        with client.websocket_connect(
            _ws_url(ticket, scenario.agent), headers={"Origin": _origin()}
        ) as agent:
            owner.send_json({"type": "typing.start"})
            event = agent.receive_json()
            assert event["type"] == "typing.start"
            assert event["data"]["user_id"] == str(scenario.owner.id)
            owner.send_json({"type": "typing.stop"})
            assert agent.receive_json()["type"] == "typing.stop"
            # The next own event must be the message, not an echoed typing event.
            owner.send_json({"type": "message.send", "body": "Typing sentinel"})
            assert owner.receive_json()["type"] == "message.created"
            assert agent.receive_json()["type"] == "message.created"


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "typing.start", "user_id": "spoof"},
        {"type": "message.read", "last_read_sequence": "999999"},
        {"type": "typing.start", "extra": True},
    ],
)
def test_spoofed_presence_and_receipt_events_are_rejected(client, scenario, payload):
    with client.websocket_connect(
        _ws_url(scenario.open_ticket, scenario.owner), headers={"Origin": _origin()}
    ) as socket:
        socket.send_json(payload)
        assert socket.receive_json()["data"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "ticket_name,user_name,code",
    [
        ("open_ticket", "admin", "FORBIDDEN"),
        ("closed_ticket", "owner", "TICKET_CLOSED"),
    ],
)
def test_typing_is_disabled_for_read_only_and_closed_tickets(
    client, scenario, ticket_name, user_name, code
):
    with client.websocket_connect(
        _ws_url(getattr(scenario, ticket_name), getattr(scenario, user_name)),
        headers={"Origin": _origin()},
    ) as socket:
        socket.send_json({"type": "typing.start"})
        assert socket.receive_json()["data"]["code"] == code


@pytest.mark.parametrize(
    "event_type", ["message", "attachment", "status", "typing", "read"]
)
def test_every_delivery_evicts_connection_after_database_role_change(
    client,
    scenario,
    session_factory,
    private_storage,
    event_type,
):
    ticket = scenario.open_ticket
    with client.websocket_connect(
        _ws_url(ticket, scenario.owner), headers={"Origin": _origin()}
    ) as owner:
        with client.websocket_connect(
            _ws_url(ticket, scenario.agent), headers={"Origin": _origin()}
        ) as stale:
            with session_factory() as db:
                db.get(User, scenario.agent.id).role = UserRole.CUSTOMER
                db.commit()
            if event_type == "message":
                owner.send_json(
                    {"type": "message.send", "body": "Private after revocation"}
                )
            elif event_type == "typing":
                owner.send_json({"type": "typing.start"})
            elif event_type == "attachment":
                response = client.post(
                    f"/tickets/{ticket.id}/messages/attachment",
                    headers=headers(scenario.owner),
                    files={"image": ("image.png", image_bytes(), "image/png")},
                )
                assert response.status_code == 201
            elif event_type == "status":
                response = client.patch(
                    f"/tickets/{ticket.id}",
                    headers=headers(scenario.admin),
                    json={"status": "in_progress"},
                )
                assert response.status_code == 200
            else:
                boundary = history(client, ticket, scenario.owner)[-1]["id"]
                response = client.post(
                    f"/tickets/{ticket.id}/read",
                    headers=headers(scenario.owner),
                    json={"last_message_id": boundary},
                )
                assert response.status_code == 200
            with pytest.raises(WebSocketDisconnect) as disconnected:
                stale.receive_json()
            assert disconnected.value.code == 1008


@pytest.mark.parametrize(
    "image_format,mime",
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_attachment_local_persistence_private_download_and_broadcast(
    client,
    scenario,
    session_factory,
    private_storage,
    image_format,
    mime,
):
    ticket = scenario.open_ticket
    with client.websocket_connect(
        _ws_url(ticket, scenario.agent), headers={"Origin": _origin()}
    ) as socket:
        response = client.post(
            f"/tickets/{ticket.id}/messages/attachment",
            headers=headers(scenario.owner),
            files={"image": ("image", image_bytes(image_format), mime)},
            data={"caption": "Screenshot"},
        )
        assert response.status_code == 201
        message = response.json()["data"]
        event = socket.receive_json()
        assert event["type"] == "message.created"
        assert event["data"]["attachment"] == message["attachment"]
        assert "storage_key" not in str(event) and "password" not in str(event)
    attachment_id = message["attachment"]["id"]
    path = f"/tickets/{ticket.id}/attachments/{attachment_id}"
    downloaded = client.get(path, headers=headers(scenario.agent))
    assert downloaded.status_code == 200
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert downloaded.headers["content-type"] == mime
    with session_factory() as db:
        attachment = db.get(MessageAttachment, uuid.UUID(attachment_id))
        assert attachment.message_id == uuid.UUID(message["id"])
        assert attachment.storage_provider == "local"
        assert attachment.byte_size == len(downloaded.content)
        assert private_storage.get(attachment.storage_key) == downloaded.content
    for user in (scenario.other_customer, scenario.external_agent):
        assert client.get(path, headers=headers(user)).status_code == 404
    assert client.get(path).status_code == 401
    assert (
        history(client, ticket, scenario.owner)[-1]["attachment"]
        == message["attachment"]
    )


@pytest.mark.parametrize(
    "viewer,ticket_name,code",
    [
        (None, "open_ticket", 401),
        ("admin", "open_ticket", 403),
        ("other_customer", "open_ticket", 404),
        ("external_agent", "open_ticket", 404),
        ("owner", "closed_ticket", 409),
    ],
)
def test_unauthorized_upload_never_creates_object_or_message(
    client,
    scenario,
    session_factory,
    private_storage,
    viewer,
    ticket_name,
    code,
):
    ticket = getattr(scenario, ticket_name)
    with session_factory() as db:
        before = db.scalar(
            select(func.count(Message.id)).where(Message.ticket_id == ticket.id)
        )
    response = client.post(
        f"/tickets/{ticket.id}/messages/attachment",
        headers=headers(getattr(scenario, viewer)) if viewer else {},
        files={"image": ("image.png", image_bytes(), "image/png")},
    )
    assert response.status_code == code
    assert not private_storage.root.exists()
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count(Message.id)).where(Message.ticket_id == ticket.id)
            )
            == before
        )


@pytest.mark.parametrize("token_type", ["expired", "refresh", "invalid"])
def test_attachment_upload_and_download_require_current_access_token(
    client, scenario, private_storage, token_type
):
    ticket, owner = scenario.open_ticket, scenario.owner
    response = client.post(
        f"/tickets/{ticket.id}/messages/attachment",
        headers=headers(owner),
        files={"image": ("image.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 201
    attachment_id = response.json()["data"]["attachment"]["id"]
    token = {
        "expired": lambda: chat_tests._expired_access(owner),
        "refresh": lambda: chat_tests._refresh(owner),
        "invalid": lambda: "invalid",
    }[token_type]()
    authorization = {"Authorization": f"Bearer {token}"}
    assert (
        client.post(
            f"/tickets/{ticket.id}/messages/attachment",
            headers=authorization,
            files={"image": ("image.png", image_bytes(), "image/png")},
        ).status_code
        == 401
    )
    denied = client.get(
        f"/tickets/{ticket.id}/attachments/{attachment_id}", headers=authorization
    )
    assert denied.status_code == 401
    assert denied.headers.get("content-type", "").startswith("application/json")


@pytest.mark.parametrize(
    "content,mime,expected",
    [
        (b"malformed", "image/png", 422),
        (b"<svg />", "image/svg+xml", 422),
        (image_bytes(), "image/jpeg", 422),
        (b"x" * (5 * 1024 * 1024 + 1), "image/png", 413),
    ],
)
def test_invalid_upload_http_leaves_database_and_private_storage_unchanged(
    client, scenario, session_factory, private_storage, content, mime, expected
):
    ticket = scenario.open_ticket
    with session_factory() as db:
        before = db.scalar(
            select(func.count(Message.id)).where(Message.ticket_id == ticket.id)
        )
    response = client.post(
        f"/tickets/{ticket.id}/messages/attachment",
        headers=headers(scenario.owner),
        files={"image": ("unsafe", content, mime)},
    )
    assert response.status_code == expected
    assert not private_storage.root.exists()
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count(Message.id)).where(Message.ticket_id == ticket.id)
            )
            == before
        )
