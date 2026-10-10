"""Reusable authentication and authorization dependencies."""

from collections.abc import Collection
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.core.security import TokenValidationError, decode_token
from app.db.session import get_db
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def _token_error(error: TokenValidationError) -> AppError:
    messages = {
        "AUTH_TOKEN_EXPIRED": "Authentication token has expired.",
        "AUTH_TOKEN_WRONG_TYPE": "Authentication token has the wrong type.",
        "AUTH_TOKEN_INVALID": "Authentication token is invalid.",
    }
    return AppError(
        status_code=401,
        code=error.code,
        message=messages.get(error.code, messages["AUTH_TOKEN_INVALID"]),
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve an access token to the current database user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            status_code=401,
            code="AUTH_TOKEN_INVALID",
            message="Authentication credentials are required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return resolve_current_user(credentials.credentials, db)


def resolve_current_user(token: str, db: Session) -> User:
    """Resolve a raw access token for HTTP or WebSocket authentication."""
    try:
        identity = decode_token(token, expected_type="access")
    except TokenValidationError as error:
        raise _token_error(error) from error

    user = db.scalar(
        select(User)
        .options(joinedload(User.business))
        .where(User.id == identity.user_id)
    )
    if user is None:
        raise AppError(
            status_code=401,
            code="AUTH_TOKEN_INVALID",
            message="Authentication token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the authenticated user to have the admin role."""
    return require_roles(
        current_user,
        {UserRole.ADMIN},
        forbidden_message="Administrator access is required.",
    )


def require_roles(
    current_user: User,
    allowed_roles: Collection[UserRole],
    *,
    forbidden_message: str = "You are not allowed to perform this action.",
) -> User:
    """Return the trusted current user when their database role is permitted."""
    if current_user.role not in allowed_roles:
        raise AppError(
            status_code=403,
            code="FORBIDDEN",
            message=forbidden_message,
        )
    return current_user
