"""Reusable resource authorization policies for tickets."""

import uuid

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.errors import AppError
from app.models import Ticket, TicketStatus, User, UserRole


def _ticket_not_found() -> AppError:
    return AppError(
        status_code=404,
        code="TICKET_NOT_FOUND",
        message="Ticket not found.",
    )


def _assignment_target_not_found() -> AppError:
    return AppError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Resource not found.",
    )


def _require_ticket_scope(ticket: Ticket, current_user: User) -> None:
    if ticket.business_id != current_user.business_id:
        raise _ticket_not_found()
    if current_user.role == UserRole.CUSTOMER and ticket.customer_id != current_user.id:
        raise _ticket_not_found()


def get_authorized_ticket(
    db: Session,
    ticket_id: uuid.UUID,
    current_user: User,
    *,
    for_update: bool = False,
) -> Ticket:
    """Resolve a ticket inside the trusted user's tenant and ownership scope."""
    require_roles(
        current_user,
        {UserRole.ADMIN, UserRole.AGENT, UserRole.CUSTOMER},
    )
    predicates: list[ColumnElement[bool]] = [
        Ticket.id == ticket_id,
        Ticket.business_id == current_user.business_id,
    ]
    if current_user.role == UserRole.CUSTOMER:
        predicates.append(Ticket.customer_id == current_user.id)

    statement = select(Ticket).where(*predicates)
    if for_update:
        statement = statement.with_for_update()
    ticket = db.scalar(statement)
    if ticket is None:
        raise _ticket_not_found()
    return ticket


def get_authorized_assignment_agent(
    db: Session,
    ticket: Ticket,
    current_user: User,
    assigned_agent_id: uuid.UUID,
) -> User:
    """Resolve an allowed assignment target without mutating the ticket."""
    _require_ticket_scope(ticket, current_user)
    require_roles(current_user, {UserRole.ADMIN, UserRole.AGENT})
    if current_user.role == UserRole.AGENT and assigned_agent_id != current_user.id:
        raise AppError(
            status_code=403,
            code="FORBIDDEN",
            message="You are not allowed to perform this action.",
        )

    agent = db.scalar(
        select(User).where(
            User.id == assigned_agent_id,
            User.business_id == ticket.business_id,
            User.role == UserRole.AGENT,
        )
    )
    if agent is None:
        raise _assignment_target_not_found()
    return agent


def authorize_ticket_status_update(
    ticket: Ticket,
    current_user: User,
    requested_status: TicketStatus,
) -> None:
    """Authorize the actor; M4 remains responsible for normal transitions."""
    _require_ticket_scope(ticket, current_user)
    require_roles(
        current_user,
        {UserRole.ADMIN, UserRole.AGENT, UserRole.CUSTOMER},
    )
    if ticket.status == TicketStatus.CLOSED:
        raise AppError(
            status_code=409,
            code="TICKET_CLOSED",
            message="This ticket is closed.",
        )
    if current_user.role in {UserRole.ADMIN, UserRole.AGENT}:
        return
    if ticket.status == TicketStatus.RESOLVED and requested_status == TicketStatus.OPEN:
        return
    raise AppError(
        status_code=403,
        code="FORBIDDEN",
        message="You are not allowed to perform this action.",
    )
