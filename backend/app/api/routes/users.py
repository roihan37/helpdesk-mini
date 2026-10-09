"""Administrator user-management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.session import get_db
from app.models import User
from app.schemas.common import ErrorResponse
from app.schemas.user import (
    UserCreateRequest,
    UserDataResponse,
    UserListResponse,
    UserPublic,
)
from app.services.users import create_business_user, list_business_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=UserListResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_users(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserListResponse:
    users = list_business_users(db, admin.business_id)
    return UserListResponse(data=[UserPublic.model_validate(user) for user in users])


@router.post(
    "",
    response_model=UserDataResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def create_user(
    payload: UserCreateRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserDataResponse:
    user = create_business_user(db, admin.business_id, payload)
    return UserDataResponse(data=UserPublic.model_validate(user))
