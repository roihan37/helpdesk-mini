"""Authorized message history and persistence workflows."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_roles
from app.core.errors import AppError
from app.models import Message, TicketStatus, User, UserRole
from app.schemas.message import MessagePublic
from app.services.authorization import get_authorized_ticket


def list_messages(
    db: Session, ticket_id: uuid.UUID, current_user: User
) -> list[MessagePublic]:
    """Return deterministic history after enforcing ticket viewer authorization."""
    get_authorized_ticket(db, ticket_id, current_user)
    messages = db.scalars(
        select(Message)
        .options(joinedload(Message.sender))
        .where(Message.ticket_id == ticket_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    ).all()
    return [_message_public(message) for message in messages]


def create_message(
    db: Session,
    ticket_id: uuid.UUID,
    current_user: User,
    body: str,
) -> MessagePublic:
    """Persist one authorized message and activity timestamp atomically."""
    try:
        ticket = get_authorized_ticket(db, ticket_id, current_user, for_update=True)
        require_roles(current_user, {UserRole.AGENT, UserRole.CUSTOMER})
        if ticket.status == TicketStatus.CLOSED:
            raise AppError(
                status_code=409,
                code="TICKET_CLOSED",
                message="This ticket no longer accepts messages.",
            )

        message = Message(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            body=body,
        )
        ticket.updated_at = datetime.now(UTC)
        db.add(message)
        db.commit()
        db.refresh(message)
        return MessagePublic(
            id=message.id,
            ticket_id=message.ticket_id,
            sender_id=message.sender_id,
            sender_name=current_user.name,
            sender_role=UserRole(current_user.role),
            body=message.body,
            created_at=message.created_at,
        )
    except Exception:
        db.rollback()
        raise


def _message_public(message: Message) -> MessagePublic:
    return MessagePublic(
        id=message.id,
        ticket_id=message.ticket_id,
        sender_id=message.sender_id,
        sender_name=message.sender.name,
        sender_role=UserRole(message.sender.role),
        body=message.body,
        created_at=message.created_at,
    )
