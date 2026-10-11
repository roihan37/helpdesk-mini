import asyncio
import uuid
from typing import Any

from fastapi import WebSocket

from app.websocket.manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.accepted = False
        self.fail_send = fail_send
        self.events: list[dict[str, Any]] = []
        self.closed: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, event: dict[str, Any]) -> None:
        if self.fail_send:
            raise RuntimeError("peer disconnected")
        self.events.append(event)

    async def close(self, code: int) -> None:
        self.closed = code


def test_manager_isolates_rooms_and_cleans_empty_room_state() -> None:
    async def scenario() -> None:
        manager = ConnectionManager()
        ticket_a = uuid.uuid4()
        ticket_b = uuid.uuid4()
        first = FakeWebSocket()
        second = FakeWebSocket()

        await manager.connect(ticket_a, first)  # type: ignore[arg-type]
        await manager.connect(ticket_b, second)  # type: ignore[arg-type]
        await manager.broadcast(ticket_a, {"type": "message.created"})

        assert first.accepted is True
        assert first.events == [{"type": "message.created"}]
        assert second.events == []

        await manager.disconnect(ticket_a, first)  # type: ignore[arg-type]
        await manager.disconnect(ticket_b, second)  # type: ignore[arg-type]
        assert await manager.connection_count(ticket_a) == 0
        assert await manager.connection_count(ticket_b) == 0
        assert manager._rooms == {}
        assert manager._room_locks == {}

    asyncio.run(scenario())


def test_manager_removes_failed_peer_without_interrupting_broadcast() -> None:
    async def scenario() -> None:
        manager = ConnectionManager()
        ticket_id = uuid.uuid4()
        healthy = FakeWebSocket()
        failed = FakeWebSocket(fail_send=True)

        await manager.connect(ticket_id, healthy)  # type: ignore[arg-type]
        await manager.connect(ticket_id, failed)  # type: ignore[arg-type]
        await manager.broadcast(ticket_id, {"type": "ticket.status_changed"})

        assert healthy.events == [{"type": "ticket.status_changed"}]
        assert await manager.connection_count(ticket_id) == 1

        await manager.disconnect(ticket_id, healthy)  # type: ignore[arg-type]
        assert manager._rooms == {}
        assert manager._room_locks == {}

    asyncio.run(scenario())


def test_list_delivery_serializes_and_removes_failed_or_invalid_peers() -> None:
    async def scenario() -> None:
        manager = ConnectionManager()
        healthy = FakeWebSocket()
        failed = FakeWebSocket(fail_send=True)
        invalid = FakeWebSocket()
        for peer in [healthy, failed, invalid]:
            await manager.subscribe(peer, "private-access-token")  # type: ignore[arg-type]

        async def authorize(
            subscriptions: dict[WebSocket, str],
        ) -> tuple[set[WebSocket], set[WebSocket]]:
            await asyncio.sleep(0)
            return (
                {peer for peer in subscriptions if peer is not invalid},
                {peer for peer in subscriptions if peer is invalid},
            )

        await asyncio.gather(
            manager.broadcast_list({"sequence": 1}, authorize),
            manager.broadcast_list({"sequence": 2}, authorize),
        )
        assert healthy.events == [{"sequence": 1}, {"sequence": 2}]
        assert failed.closed == 1011
        assert invalid.closed == 1008
        assert invalid.events == []
        assert len(manager._subscriptions) == 1
        await manager.unsubscribe(healthy)  # type: ignore[arg-type]
        assert manager._subscriptions == {}

    asyncio.run(scenario())
