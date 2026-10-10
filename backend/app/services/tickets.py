"""Tenant-scoped ticket workflows."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_roles
from app.core.errors import AppError
from app.models import Message, Ticket, TicketStatus, User, UserRole
from app.schemas.ticket import TicketCreateRequest, TicketUpdateRequest
from app.services.authorization import (
    authorize_ticket_status_update,
    get_authorized_assignment_agent,
    get_authorized_ticket,
)

NORMAL_STATUS_TRANSITIONS = {
    TicketStatus.OPEN: TicketStatus.IN_PROGRESS,
    TicketStatus.IN_PROGRESS: TicketStatus.RESOLVED,
    TicketStatus.RESOLVED: TicketStatus.CLOSED,
}


@dataclass(frozen=True)
class TicketUpdateResult:
    ticket: Ticket
    status_changed: bool


def list_tickets(
    db: Session,
    current_user: User,
    status: TicketStatus | None = None,
) -> list[Ticket]:
    """List tickets in the authenticated user's permitted scope."""
    require_roles(
        current_user,
        {UserRole.ADMIN, UserRole.AGENT, UserRole.CUSTOMER},
    )
    predicates = [Ticket.business_id == current_user.business_id]
    if current_user.role == UserRole.CUSTOMER:
        predicates.append(Ticket.customer_id == current_user.id)
    if status is not None:
        predicates.append(Ticket.status == status)

    statement = (
        select(Ticket)
        .options(selectinload(Ticket.assigned_agent))
        .where(*predicates)
        .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    )
    return list(db.scalars(statement).all())


def create_ticket(
    db: Session, current_user: User, payload: TicketCreateRequest
) -> Ticket:
    """Create a customer-owned ticket and its first message atomically."""
    require_roles(current_user, {UserRole.CUSTOMER})
    ticket = Ticket(
        business_id=current_user.business_id,
        customer_id=current_user.id,
        assigned_agent_id=None,
        subject=payload.subject,
        category=payload.category,
        priority=payload.priority,
        status=TicketStatus.OPEN,
    )
    first_message = Message(
        ticket=ticket,
        sender_id=current_user.id,
        body=payload.message,
    )
    db.add_all([ticket, first_message])
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(ticket)
    return ticket


def get_ticket(db: Session, ticket_id: uuid.UUID, current_user: User) -> Ticket:
    """Return an authorized ticket with its public related identities loaded."""
    ticket = get_authorized_ticket(db, ticket_id, current_user)
    _load_ticket_identities(ticket)
    return ticket


def update_ticket(
    db: Session,
    ticket_id: uuid.UUID,
    current_user: User,
    payload: TicketUpdateRequest,
) -> Ticket:
    """Compatibility wrapper returning the updated Ticket."""
    return update_ticket_with_result(db, ticket_id, current_user, payload).ticket


def update_ticket_with_result(
    db: Session,
    ticket_id: uuid.UUID,
    current_user: User,
    payload: TicketUpdateRequest,
) -> TicketUpdateResult:
    """Apply authorized assignment/status operations in one locked transaction."""
    try:
        ticket = get_authorized_ticket(
            db,
            ticket_id,
            current_user,
            for_update=True,
        )
        target_agent: User | None = None
        requested_status = payload.status

        if "assigned_agent_id" in payload.model_fields_set:
            assigned_agent_id = payload.assigned_agent_id
            if assigned_agent_id is None:  # guarded by request validation
                raise AssertionError("validated assigned_agent_id cannot be null")
            target_agent = get_authorized_assignment_agent(
                db,
                ticket,
                current_user,
                assigned_agent_id,
            )
            if current_user.role == UserRole.AGENT and ticket.assigned_agent_id not in {
                None,
                current_user.id,
            }:
                raise AppError(
                    status_code=409,
                    code="ASSIGNMENT_CONFLICT",
                    message="Ticket is already assigned to another agent.",
                )

        status_changes = (
            "status" in payload.model_fields_set
            and requested_status is not None
            and requested_status != ticket.status
        )
        if status_changes:
            assert requested_status is not None
            authorize_ticket_status_update(ticket, current_user, requested_status)
            if current_user.role in {UserRole.ADMIN, UserRole.AGENT}:
                allowed_status = NORMAL_STATUS_TRANSITIONS.get(
                    TicketStatus(ticket.status)
                )
                if requested_status != allowed_status:
                    raise _invalid_status_transition()
            elif not (
                ticket.status == TicketStatus.RESOLVED
                and requested_status == TicketStatus.OPEN
            ):
                raise _invalid_status_transition()

        assignment_changes = (
            target_agent is not None and target_agent.id != ticket.assigned_agent_id
        )
        if assignment_changes:
            ticket.assigned_agent = target_agent
        if status_changes and requested_status is not None:
            ticket.status = requested_status

        # A no-op commit releases the row lock without issuing an UPDATE.
        db.commit()
        db.refresh(ticket)
        _load_ticket_identities(ticket)
        return TicketUpdateResult(ticket=ticket, status_changed=status_changes)
    except Exception:
        db.rollback()
        raise


def _invalid_status_transition() -> AppError:
    return AppError(
        status_code=409,
        code="INVALID_STATUS_TRANSITION",
        message="The requested ticket status transition is not allowed.",
    )


def _load_ticket_identities(ticket: Ticket) -> None:
    # Load relationships only after the parent passed tenant/owner scope.
    _ = ticket.customer
    _ = ticket.assigned_agent
