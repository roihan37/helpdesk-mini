import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

from app.schemas.common import StrictRequest
from app.schemas.user import Name, Password, UserPublic

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]


class BusinessRegisterRequest(StrictRequest):
    name: Name
    slug: Slug


class AdminRegisterRequest(StrictRequest):
    name: Name
    email: EmailStr
    password: Password

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class RegisterBusinessRequest(StrictRequest):
    business: BusinessRegisterRequest
    admin: AdminRegisterRequest


class LoginRequest(StrictRequest):
    email: EmailStr
    password: Password

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class BusinessPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class BusinessSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class RegistrationData(BaseModel):
    business: BusinessPublic
    admin: UserPublic


class RegistrationResponse(BaseModel):
    data: RegistrationData


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class TokenPairResponse(BaseModel):
    data: TokenPair


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AccessTokenResponse(BaseModel):
    data: AccessToken


class CurrentUser(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: Literal["admin", "agent", "customer"]
    business: BusinessSummary


class CurrentUserResponse(BaseModel):
    data: CurrentUser
