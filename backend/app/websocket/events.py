"""Trusted server event broadcasting helpers."""

import logging
import uuid
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError
from app.core.security import TokenValidationError, decode_token
from app.models import Message, Ticket, TicketReadState, TicketStatus, User, UserRole
from app.schemas.message import (
    MessageReadData,
    MessageReadEvent,
    TicketListEvent,
    TicketListEventData,
    TicketListEventType,
    TicketStatusChangedData,
    TicketStatusChangedEvent,
    TypingBroadcast,
    TypingData,
)
from app.services.authorization import get_authorized_ticket
from app.websocket.manager import connection_manager

logger = logging.getLogger(__name__)


async def broadcast_ticket_list_event(
    session_factory: sessionmaker[Session],
    event_type: TicketListEventType,
    ticket_id: uuid.UUID,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    updated_at: datetime,
    recipient_user_id: uuid.UUID | None = None,
) -> None:
    """Publish committed activity; scope comes only from the persisted Ticket."""
    if event_type == "ticket.read" and recipient_user_id is None:
        # List unread synchronization stays private; B6 uses a separate room event.
        raise ValueError("Read events require an explicit recipient")
    event = TicketListEvent(
        type=event_type,
        data=TicketListEventData(ticket_id=ticket_id, updated_at=updated_at),
    )

    async def authorize(
        subscriptions: dict[WebSocket, str],
    ) -> tuple[set[WebSocket], set[WebSocket]]:
        return await run_in_threadpool(
            _list_recipients,
            session_factory,
            subscriptions,
            business_id,
            customer_id,
            recipient_user_id,
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
    recipient_user_id: uuid.UUID | None = None,
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
            elif (
                recipient_user_id is None or user.id == recipient_user_id
            ) and user.business_id == business_id and (
                user.role in {UserRole.ADMIN, UserRole.AGENT}
                or (user.role == UserRole.CUSTOMER and user.id == customer_id)
            ):
                recipients.add(websocket)
    return recipients, invalid


def _room_recipients(
    session_factory: sessionmaker[Session],
    subscriptions: dict[WebSocket, str],
    ticket_id: uuid.UUID,
    audience: set[uuid.UUID] | None,
    excluded_user_id: uuid.UUID | None,
) -> tuple[set[WebSocket], set[WebSocket]]:
    # ticket_id is trusted server room context, never a client-supplied scope.
    with session_factory() as db:
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            return set(), set(subscriptions)
        business_id, customer_id = ticket.business_id, ticket.customer_id
    eligible, invalid = _list_recipients(
        session_factory, subscriptions, business_id, customer_id
    )
    invalid |= set(subscriptions) - eligible
    recipients = set()
    for websocket in eligible:
        try:
            user_id = decode_token(subscriptions[websocket], expected_type="access").user_id
        except TokenValidationError:
            invalid.add(websocket)
            continue
        if user_id != excluded_user_id and (audience is None or user_id in audience):
            recipients.add(websocket)
    return recipients, invalid


async def _broadcast_room_event(
    session_factory: sessionmaker[Session], ticket_id: uuid.UUID,
    event: dict, audience: set[uuid.UUID] | None = None,
    excluded_user_id: uuid.UUID | None = None,
) -> None:
    async def authorize(subscriptions: dict[WebSocket, str]):
        return await run_in_threadpool(
            _room_recipients, session_factory, subscriptions, ticket_id,
            audience, excluded_user_id,
        )
    try:
        await connection_manager.broadcast(ticket_id, event, authorize)
    except Exception:
        logger.exception("Chat presence/receipt delivery failed")


async def broadcast_typing(
    session_factory: sessionmaker[Session], event_type: str, data: TypingData,
) -> None:
    # Identity is obtained from an authorized server-side DB lookup at ingestion.
    event = TypingBroadcast.model_validate({"type": event_type, "data": data})

    async def authorize(subscriptions: dict[WebSocket, str]):
        recipients, invalid = await run_in_threadpool(
            _room_recipients, session_factory, subscriptions, data.ticket_id,
            None, data.user_id,
        )
        # Serial room delivery discards obsolete start/stop events from racing
        # sessions/expiry tasks. Check state after the authorization await.
        if event_type == "typing.start" and not await run_in_threadpool(
            _typing_source_allowed, session_factory, data,
        ):
            return set(), invalid
        active = await connection_manager.is_typing(data.ticket_id, data.user_id)
        if active != (event_type == "typing.start"):
            return set(), invalid
        return recipients, invalid

    try:
        await connection_manager.broadcast(
            data.ticket_id, event.model_dump(mode="json"), authorize,
        )
    except Exception:
        logger.exception("Typing notification delivery failed")


def _typing_source_allowed(session_factory: sessionmaker[Session], data: TypingData) -> bool:
    with session_factory() as db:
        user = db.get(User, data.user_id)
        if user is None or user.role not in {UserRole.AGENT, UserRole.CUSTOMER}:
            return False
        try:
            ticket = get_authorized_ticket(db, data.ticket_id, user)
        except AppError:
            return False
        return ticket.status != TicketStatus.CLOSED


def _read_receipt(
    session_factory: sessionmaker[Session], ticket_id: uuid.UUID, reader_id: uuid.UUID,
) -> tuple[MessageReadEvent, set[uuid.UUID]] | None:
    with session_factory() as db:
        reader = db.get(User, reader_id)
        if reader is None or reader.role not in {UserRole.AGENT, UserRole.CUSTOMER}:
            return None
        try:
            get_authorized_ticket(db, ticket_id, reader)
        except AppError:
            return None
        sequence = db.scalar(select(TicketReadState.last_read_sequence).where(
            TicketReadState.ticket_id == ticket_id, TicketReadState.user_id == reader.id,
        ))
        if sequence is None:
            return None
        senders = set(db.scalars(select(Message.sender_id).where(
            Message.ticket_id == ticket_id, Message.sequence <= sequence,
            Message.sender_id != reader.id,
        ).distinct()))
        return MessageReadEvent(data=MessageReadData(
            ticket_id=ticket_id, user_id=reader.id, name=reader.name, role=reader.role,
            last_read_sequence=str(sequence),
        )), senders


async def broadcast_message_read(
    session_factory: sessionmaker[Session], ticket_id: uuid.UUID, reader_id: uuid.UUID,
) -> None:
    # Called only after a changed, committed read cursor. Re-read persistent state;
    # client-supplied reader identities/cursors are never accepted over WebSocket.
    try:
        receipt = await run_in_threadpool(_read_receipt, session_factory, ticket_id, reader_id)
        if receipt is not None:
            event, senders = receipt
            await _broadcast_room_event(
                session_factory, ticket_id, event.model_dump(mode="json"), audience=senders,
            )
    except Exception:
        logger.exception("Read-receipt delivery failed")


async def broadcast_ticket_status_changed(
    ticket_id: uuid.UUID,
    status: TicketStatus,
    updated_at: datetime,
) -> None:
    if status == TicketStatus.CLOSED:
        await connection_manager.clear_typing(ticket_id)
    event = TicketStatusChangedEvent(
        data=TicketStatusChangedData(
            ticket_id=ticket_id,
            status=status,
            updated_at=updated_at,
        )
    )
    await connection_manager.broadcast(ticket_id, event.model_dump(mode="json"))
