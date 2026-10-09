import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

from app.schemas.common import StrictRequest

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserCreateRequest(StrictRequest):
    name: Name
    email: EmailStr
    password: Password
    role: Literal["agent", "customer"]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    email: EmailStr
    role: Literal["admin", "agent", "customer"]
    created_at: datetime


class UserDataResponse(BaseModel):
    data: UserPublic


class UserListResponse(BaseModel):
    data: list[UserPublic]
