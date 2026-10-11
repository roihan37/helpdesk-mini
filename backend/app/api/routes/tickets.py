import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.db.session import get_db, get_session_factory
from app.models import TicketStatus, User
from app.schemas.common import ErrorResponse
from app.schemas.message import MessageListResponse
from app.schemas.ticket import (
    TicketCreateRequest,
    TicketDataResponse,
    TicketDetail,
    TicketDetailResponse,
    TicketListItem,
    TicketListResponse,
    TicketPagination,
    TicketPublic,
    TicketReadData,
    TicketReadRequest,
    TicketReadResponse,
    TicketUpdateRequest,
)
from app.services.messages import list_messages
from app.services.ticket_reads import mark_ticket_read
from app.services.tickets import (
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_with_result,
)
from app.websocket.events import (
    broadcast_message_read,
    broadcast_ticket_list_event,
    broadcast_ticket_status_changed,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get(
    "",
    response_model=TicketListResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def list_ticket_records(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ticket_status: Annotated[TicketStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1, le=2_147_483_647)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=150)] = None,
) -> TicketListResponse:
    tickets = list_tickets(
        db, current_user, ticket_status, page=page, page_size=page_size, search=search
    )
    return TicketListResponse(
        data=[
            TicketListItem.model_validate(ticket).model_copy(
                update={"unread_count": tickets.unread_counts.get(ticket.id, 0)}
            )
            for ticket in tickets.items
        ],
        pagination=TicketPagination(
            page=page,
            page_size=page_size,
            total_items=tickets.total_items,
            total_pages=(tickets.total_items + page_size - 1) // page_size,
        ),
    )


@router.post(
    "",
    response_model=TicketDataResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def create_ticket_record(
    payload: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> TicketDataResponse:
    ticket = create_ticket(db, current_user, payload)
    background_tasks.add_task(
        broadcast_ticket_list_event,
        session_factory,
        "ticket.created",
        ticket.id,
        ticket.business_id,
        ticket.customer_id,
        ticket.updated_at,
    )
    return TicketDataResponse(data=TicketPublic.model_validate(ticket))


@router.get(
    "/{ticket_id}",
    response_model=TicketDetailResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_ticket_record(
    ticket_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TicketDetailResponse:
    ticket = get_ticket(db, ticket_id, current_user)
    return TicketDetailResponse(data=TicketDetail.model_validate(ticket))


@router.get(
    "/{ticket_id}/messages",
    response_model=MessageListResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_ticket_messages(
    ticket_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageListResponse:
    return MessageListResponse(data=list_messages(db, ticket_id, current_user))


@router.post(
    "/{ticket_id}/read",
    response_model=TicketReadResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def mark_ticket_conversation_read(
    ticket_id: uuid.UUID,
    payload: TicketReadRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> TicketReadResponse:
    result = mark_ticket_read(db, ticket_id, current_user, payload.last_message_id)
    if result.changed:
        background_tasks.add_task(
            broadcast_message_read, session_factory, result.ticket_id, current_user.id,
        )
        background_tasks.add_task(
            broadcast_ticket_list_event,
            session_factory,
            "ticket.read",
            result.ticket_id,
            result.business_id,
            result.customer_id,
            result.read_at,
            recipient_user_id=current_user.id,
        )
    return TicketReadResponse(
        data=TicketReadData(ticket_id=result.ticket_id, unread_count=result.unread_count)
    )


@router.patch(
    "/{ticket_id}",
    response_model=TicketDetailResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def update_ticket_record(
    ticket_id: uuid.UUID,
    payload: TicketUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> TicketDetailResponse:
    result = update_ticket_with_result(db, ticket_id, current_user, payload)
    ticket = result.ticket
    if result.status_changed:
        background_tasks.add_task(
            broadcast_ticket_status_changed,
            ticket.id,
            TicketStatus(ticket.status),
            ticket.updated_at,
        )
        background_tasks.add_task(
            broadcast_ticket_list_event,
            session_factory,
            "ticket.status_changed",
            ticket.id,
            ticket.business_id,
            ticket.customer_id,
            ticket.updated_at,
        )
    if result.assignment_changed:
        background_tasks.add_task(
            broadcast_ticket_list_event,
            session_factory,
            "ticket.assignment_changed",
            ticket.id,
            ticket.business_id,
            ticket.customer_id,
            ticket.updated_at,
        )
    return TicketDetailResponse(data=TicketDetail.model_validate(ticket))
