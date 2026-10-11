"""Single-process ticket-room and user-scoped subscription manager."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, set[WebSocket]] = {}
        self._room_locks: dict[uuid.UUID, asyncio.Lock] = {}
        self._state_lock = asyncio.Lock()
        self._subscriptions: dict[WebSocket, str] = {}
        self._subscription_lock = asyncio.Lock()

    async def subscribe(self, websocket: WebSocket, token: str) -> None:
        await websocket.accept()
        async with self._state_lock:
            self._subscriptions[websocket] = token

    async def unsubscribe(self, websocket: WebSocket) -> None:
        async with self._state_lock:
            self._subscriptions.pop(websocket, None)

    async def broadcast_list(
        self,
        event: dict[str, Any],
        authorize: Callable[
            [dict[WebSocket, str]],
            Awaitable[tuple[set[WebSocket], set[WebSocket]]],
        ],
    ) -> None:
        # Serialize list deliveries, with one batched authorization check per event.
        async with self._subscription_lock:
            async with self._state_lock:
                subscriptions = self._subscriptions.copy()
            if not subscriptions:
                return
            recipients, invalid = await authorize(subscriptions)
            for websocket in invalid:
                await self.unsubscribe(websocket)
                try:
                    await websocket.close(code=1008)
                except Exception:
                    pass
            for websocket in recipients:
                try:
                    await asyncio.wait_for(websocket.send_json(event), timeout=5)
                except Exception:
                    await self.unsubscribe(websocket)
                    try:
                        await websocket.close(code=1011)
                    except Exception:
                        pass

    async def connect(self, ticket_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._state_lock:
            self._rooms.setdefault(ticket_id, set()).add(websocket)
            self._room_locks.setdefault(ticket_id, asyncio.Lock())

    async def disconnect(self, ticket_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._state_lock:
            room = self._rooms.get(ticket_id)
            if room is None:
                return
            room.discard(websocket)
            if not room:
                self._rooms.pop(ticket_id, None)
                room_lock = self._room_locks.get(ticket_id)
                if room_lock is not None and not room_lock.locked():
                    self._room_locks.pop(ticket_id, None)

    async def broadcast(self, ticket_id: uuid.UUID, event: dict[str, Any]) -> None:
        room_lock = await self._room_lock(ticket_id)
        async with room_lock:
            async with self._state_lock:
                connections = tuple(self._rooms.get(ticket_id, ()))

            failed: list[WebSocket] = []
            for websocket in connections:
                try:
                    await websocket.send_json(event)
                except Exception:
                    failed.append(websocket)

            for websocket in failed:
                await self.disconnect(ticket_id, websocket)

        async with self._state_lock:
            if (
                ticket_id not in self._rooms
                and self._room_locks.get(ticket_id) is room_lock
            ):
                self._room_locks.pop(ticket_id, None)

    async def connection_count(self, ticket_id: uuid.UUID) -> int:
        async with self._state_lock:
            return len(self._rooms.get(ticket_id, ()))

    async def _room_lock(self, ticket_id: uuid.UUID) -> asyncio.Lock:
        async with self._state_lock:
            return self._room_locks.setdefault(ticket_id, asyncio.Lock())


connection_manager = ConnectionManager()
