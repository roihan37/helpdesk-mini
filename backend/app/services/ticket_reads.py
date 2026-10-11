"""Authorized unread aggregation and monotonic, private read acknowledgements."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.errors import AppError
from app.models import Message, Ticket, TicketReadState, User, UserRole
from app.services.authorization import get_authorized_ticket


@dataclass(frozen=True)
class TicketReadResult:
    ticket_id: uuid.UUID
    business_id: uuid.UUID
    customer_id: uuid.UUID
    unread_count: int
    changed: bool
    read_at: datetime


def get_unread_counts(
    db: Session, current_user: User, ticket_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """One grouped query for the authorized page, never one query per ticket."""
    require_roles(current_user, {UserRole.ADMIN, UserRole.AGENT, UserRole.CUSTOMER})
    if not ticket_ids:
        return {}
    predicates = [
        Ticket.business_id == current_user.business_id,
        Ticket.id.in_(ticket_ids),
        Message.sender_id != current_user.id,
        Message.sequence > func.coalesce(TicketReadState.last_read_sequence, 0),
    ]
    if current_user.role == UserRole.CUSTOMER:
        predicates.append(Ticket.customer_id == current_user.id)
    statement = (
        select(Message.ticket_id, func.count(Message.id))
        .join(Ticket, Ticket.id == Message.ticket_id)
        .outerjoin(
            TicketReadState,
            and_(
                TicketReadState.ticket_id == Ticket.id,
                TicketReadState.user_id == current_user.id,
            ),
        )
        .where(*predicates)
        .group_by(Message.ticket_id)
    )
    return {ticket_id: count for ticket_id, count in db.execute(statement)}


def mark_ticket_read(
    db: Session,
    ticket_id: uuid.UUID,
    current_user: User,
    last_message_id: uuid.UUID,
) -> TicketReadResult:
    """Acknowledge only the observed boundary, never unseen concurrent messages.

    Message writers and readers serialize on the same ticket row. PostgreSQL
    upsert prevents stale/out-of-order acknowledgements from moving backwards.
    """
    try:
        ticket = get_authorized_ticket(db, ticket_id, current_user, for_update=True)
        sequence = db.scalar(
            select(Message.sequence).where(
                Message.ticket_id == ticket.id, Message.id == last_message_id
            )
        )
        if sequence is None:
            raise AppError(
                status_code=404,
                code="MESSAGE_NOT_FOUND",
                message="Message not found.",
            )
        statement = (
            insert(TicketReadState)
            .values(
                user_id=current_user.id,
                ticket_id=ticket.id,
                last_read_sequence=sequence,
            )
            .on_conflict_do_update(
                index_elements=[TicketReadState.user_id, TicketReadState.ticket_id],
                set_={"last_read_sequence": sequence},
                where=TicketReadState.last_read_sequence < sequence,
            )
            .returning(TicketReadState.last_read_sequence)
        )
        changed = db.execute(statement).scalar_one_or_none() is not None
        business_id, customer_id = ticket.business_id, ticket.customer_id
        db.commit()
        read_at = datetime.now(UTC)
        # A new message may have committed since acknowledgement: do not assume zero.
        unread_count = get_unread_counts(db, current_user, [ticket_id]).get(ticket_id, 0)
        return TicketReadResult(
            ticket_id=ticket_id,
            business_id=business_id,
            customer_id=customer_id,
            unread_count=unread_count,
            changed=changed,
            read_at=read_at,
        )
    except Exception:
        db.rollback()
        raise
