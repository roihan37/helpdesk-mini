import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models import TicketStatus, UserRole
from app.schemas.common import StrictRequest
from app.schemas.ticket import MessageBody


class MessageSendEvent(StrictRequest):
    type: Literal["message.send"]
    body: MessageBody


class MessagePublic(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    sender_role: UserRole
    body: str
    created_at: datetime


class MessageListResponse(BaseModel):
    data: list[MessagePublic]


class MessageCreatedEvent(BaseModel):
    type: Literal["message.created"] = "message.created"
    data: MessagePublic


class TicketStatusChangedData(BaseModel):
    ticket_id: uuid.UUID
    status: TicketStatus
    updated_at: datetime


class TicketStatusChangedEvent(BaseModel):
    type: Literal["ticket.status_changed"] = "ticket.status_changed"
    data: TicketStatusChangedData


class WebSocketErrorData(BaseModel):
    code: Literal[
        "FORBIDDEN",
        "VALIDATION_ERROR",
        "TICKET_CLOSED",
        "INTERNAL_SERVER_ERROR",
    ]
    message: str


class WebSocketErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    data: WebSocketErrorData
