"""Trusted server event broadcasting helpers."""

import logging
import uuid
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core.security import TokenValidationError, decode_token
from app.models import TicketStatus, User, UserRole
from app.schemas.message import (
    TicketListEvent,
    TicketListEventData,
    TicketListEventType,
    TicketStatusChangedData,
    TicketStatusChangedEvent,
)
from app.websocket.manager import connection_manager

logger = logging.getLogger(__name__)


async def broadcast_ticket_list_event(
    session_factory: sessionmaker[Session],
    event_type: TicketListEventType,
    ticket_id: uuid.UUID,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    updated_at: datetime,
) -> None:
    """Publish committed activity; scope comes only from the persisted Ticket."""
    event = TicketListEvent(
        type=event_type,
        data=TicketListEventData(ticket_id=ticket_id, updated_at=updated_at),
    )

    async def authorize(
        subscriptions: dict[WebSocket, str],
    ) -> tuple[set[WebSocket], set[WebSocket]]:
        return await run_in_threadpool(
            _list_recipients, session_factory, subscriptions, business_id, customer_id
        )

    try:
        await connection_manager.broadcast_list(
            event.model_dump(mode="json"), authorize
        )
    except Exception:
        # The committed operation remains successful; reconnect refetch recovers gaps.
        logger.exception("Ticket-list notification delivery failed")


def _list_recipients(
    session_factory: sessionmaker[Session],
    subscriptions: dict[WebSocket, str],
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> tuple[set[WebSocket], set[WebSocket]]:
    identities: dict[WebSocket, uuid.UUID] = {}
    invalid: set[WebSocket] = set()
    for websocket, token in subscriptions.items():
        try:
            identities[websocket] = decode_token(token, expected_type="access").user_id
        except TokenValidationError:
            invalid.add(websocket)
    if not identities:
        return set(), invalid
    with session_factory() as db:
        # Re-read current business and role, never trust stale claims/handshake state.
        users = {
            user.id: user
            for user in db.scalars(
                select(User).where(User.id.in_(set(identities.values())))
            )
        }
        recipients: set[WebSocket] = set()
        for websocket, user_id in identities.items():
            user = users.get(user_id)
            if user is None or user.role not in set(UserRole):
                invalid.add(websocket)
            elif user.business_id == business_id and (
                user.role in {UserRole.ADMIN, UserRole.AGENT}
                or (user.role == UserRole.CUSTOMER and user.id == customer_id)
            ):
                recipients.add(websocket)
    return recipients, invalid


async def broadcast_ticket_status_changed(
    ticket_id: uuid.UUID,
    status: TicketStatus,
    updated_at: datetime,
) -> None:
    event = TicketStatusChangedEvent(
        data=TicketStatusChangedData(
            ticket_id=ticket_id,
            status=status,
            updated_at=updated_at,
        )
    )
    await connection_manager.broadcast(ticket_id, event.model_dump(mode="json"))
