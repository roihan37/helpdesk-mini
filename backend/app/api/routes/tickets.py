import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
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
    TicketPublic,
    TicketUpdateRequest,
)
from app.services.messages import list_messages
from app.services.tickets import (
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_with_result,
)
from app.websocket.events import broadcast_ticket_status_changed

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
) -> TicketListResponse:
    tickets = list_tickets(db, current_user, ticket_status)
    return TicketListResponse(
        data=[TicketListItem.model_validate(ticket) for ticket in tickets]
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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TicketDataResponse:
    ticket = create_ticket(db, current_user, payload)
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
    return TicketDetailResponse(data=TicketDetail.model_validate(ticket))
