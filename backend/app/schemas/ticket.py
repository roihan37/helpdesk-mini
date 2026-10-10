import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models import TicketPriority, TicketStatus
from app.schemas.common import StrictRequest

Subject = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
Category = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
MessageBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class TicketCreateRequest(StrictRequest):
    subject: Subject
    category: Category
    priority: TicketPriority
    message: MessageBody


class TicketUpdateRequest(StrictRequest):
    status: TicketStatus | None = None
    assigned_agent_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_operations(self) -> "TicketUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one ticket update is required.")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be null.")
        if (
            "assigned_agent_id" in self.model_fields_set
            and self.assigned_agent_id is None
        ):
            raise ValueError("Assigned agent cannot be null.")
        return self


class TicketUserIdentity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class TicketPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    customer_id: uuid.UUID
    assigned_agent_id: uuid.UUID | None
    subject: str
    category: str
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime


class TicketListItem(TicketPublic):
    assigned_agent: TicketUserIdentity | None


class TicketDetail(TicketPublic):
    customer: TicketUserIdentity
    assigned_agent: TicketUserIdentity | None


class TicketDataResponse(BaseModel):
    data: TicketPublic


class TicketDetailResponse(BaseModel):
    data: TicketDetail


class TicketListResponse(BaseModel):
    data: list[TicketListItem]
