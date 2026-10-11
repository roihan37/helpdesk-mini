"""Single-process ticket-room and user-scoped subscription manager."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass
class TypingPresence:
    user_id: uuid.UUID
    publish: Callable[[str], Awaitable[None]]
    expiry: asyncio.Task[None] | None = None


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, set[WebSocket]] = {}
        self._room_locks: dict[uuid.UUID, asyncio.Lock] = {}
        self._state_lock = asyncio.Lock()
        self._subscriptions: dict[WebSocket, str] = {}
        self._subscription_lock = asyncio.Lock()
        self._room_tokens: dict[WebSocket, str] = {}
        self._typing: dict[uuid.UUID, dict[WebSocket, TypingPresence]] = {}

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

    async def connect(
        self, ticket_id: uuid.UUID, websocket: WebSocket, token: str | None = None
    ) -> None:
        await websocket.accept()
        async with self._state_lock:
            self._rooms.setdefault(ticket_id, set()).add(websocket)
            self._room_locks.setdefault(ticket_id, asyncio.Lock())
            if token is not None:
                self._room_tokens[websocket] = token

    async def disconnect(self, ticket_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._state_lock:
            self._room_tokens.pop(websocket, None)
            room = self._rooms.get(ticket_id)
            if room is not None:
                room.discard(websocket)
            if room is not None and not room:
                self._rooms.pop(ticket_id, None)
                room_lock = self._room_locks.get(ticket_id)
                if room_lock is not None and not room_lock.locked():
                    self._room_locks.pop(ticket_id, None)
        await self.stop_typing(ticket_id, websocket)

    async def broadcast(
        self,
        ticket_id: uuid.UUID,
        event: dict[str, Any],
        authorize: Callable[
            [dict[WebSocket, str]],
            Awaitable[tuple[set[WebSocket], set[WebSocket]]],
        ] | None = None,
    ) -> None:
        room_lock = await self._room_lock(ticket_id)
        async with room_lock:
            async with self._state_lock:
                connections = tuple(self._rooms.get(ticket_id, ()))
                tokens = {ws: self._room_tokens.get(ws, "") for ws in connections}

            recipients, invalid = (
                await authorize(tokens) if authorize is not None
                else (set(connections), set())
            )

            failed: list[WebSocket] = []
            for websocket in invalid:
                try:
                    await websocket.close(code=1008)
                except Exception:
                    pass
            for websocket in recipients:
                try:
                    await asyncio.wait_for(websocket.send_json(event), timeout=5)
                except Exception:
                    failed.append(websocket)
        # Disconnect may emit typing.stop; never recurse into a held room lock.
        for websocket in set(failed) | invalid:
            await self.disconnect(ticket_id, websocket)

        async with self._state_lock:
            if (
                ticket_id not in self._rooms
                and self._room_locks.get(ticket_id) is room_lock
            ):
                self._room_locks.pop(ticket_id, None)

    async def start_typing(
        self,
        ticket_id: uuid.UUID,
        websocket: WebSocket,
        user_id: uuid.UUID,
        publish: Callable[[str], Awaitable[None]],
    ) -> None:
        async with self._state_lock:
            if websocket not in self._rooms.get(ticket_id, ()):
                return
            room = self._typing.setdefault(ticket_id, {})
            old = room.get(websocket)
            if old and old.expiry:
                old.expiry.cancel()
            presence = TypingPresence(user_id=user_id, publish=publish)
            room[websocket] = presence
            presence.expiry = asyncio.create_task(
                self._expire_typing(ticket_id, websocket, presence)
            )
        # Throttled heartbeats also refresh other clients' fallback expiry.
        await publish("typing.start")

    async def _expire_typing(
        self, ticket_id: uuid.UUID, websocket: WebSocket, presence: TypingPresence
    ) -> None:
        await asyncio.sleep(5)
        await self.stop_typing(ticket_id, websocket, expected=presence)

    async def stop_typing(
        self, ticket_id: uuid.UUID, websocket: WebSocket,
        expected: TypingPresence | None = None,
    ) -> None:
        async with self._state_lock:
            room = self._typing.get(ticket_id, {})
            presence = room.get(websocket)
            if presence is None or (expected is not None and presence is not expected):
                return
            room.pop(websocket)
            if presence.expiry and presence.expiry is not asyncio.current_task():
                presence.expiry.cancel()
            still_typing = any(item.user_id == presence.user_id for item in room.values())
            if not room:
                self._typing.pop(ticket_id, None)
        if not still_typing:
            await presence.publish("typing.stop")

    async def clear_typing(self, ticket_id: uuid.UUID) -> None:
        async with self._state_lock:
            connections = tuple(self._typing.get(ticket_id, {}))
        for websocket in connections:
            await self.stop_typing(ticket_id, websocket)

    async def is_typing(self, ticket_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        async with self._state_lock:
            return any(
                presence.user_id == user_id
                for presence in self._typing.get(ticket_id, {}).values()
            )

    async def connection_count(self, ticket_id: uuid.UUID) -> int:
        async with self._state_lock:
            return len(self._rooms.get(ticket_id, ()))

    async def _room_lock(self, ticket_id: uuid.UUID) -> asyncio.Lock:
        async with self._state_lock:
            return self._room_locks.setdefault(ticket_id, asyncio.Lock())


connection_manager = ConnectionManager()
