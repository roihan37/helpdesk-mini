import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import TicketStatus, UserRole
from app.schemas.common import StrictRequest
from app.schemas.ticket import MessageBody


class MessageSendEvent(StrictRequest):
    type: Literal["message.send"]
    body: MessageBody


class TypingEvent(StrictRequest):
    type: Literal["typing.start", "typing.stop"]


class MessageReader(BaseModel):
    user_id: uuid.UUID
    name: str
    role: UserRole


class TypingData(MessageReader):
    ticket_id: uuid.UUID


class TypingBroadcast(BaseModel):
    type: Literal["typing.start", "typing.stop"]
    data: TypingData


class MessageReadData(MessageReader):
    ticket_id: uuid.UUID
    last_read_sequence: str


class MessageReadEvent(BaseModel):
    type: Literal["message.read"] = "message.read"
    data: MessageReadData


class MessagePublic(BaseModel):
    id: uuid.UUID
    # Decimal string preserves PostgreSQL BIGINT precision in JavaScript clients.
    sequence: str
    ticket_id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    sender_role: UserRole
    body: str
    created_at: datetime
    # Populated only for the requesting sender's outgoing history.
    read_by: list[MessageReader] = Field(default_factory=list)


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


TicketListEventType = Literal[
    "ticket.created",
    "ticket.message_created",
    "ticket.status_changed",
    "ticket.assignment_changed",
    "ticket.read",
]


class TicketListEventData(BaseModel):
    ticket_id: uuid.UUID
    updated_at: datetime


class TicketListEvent(BaseModel):
    type: TicketListEventType
    data: TicketListEventData


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
