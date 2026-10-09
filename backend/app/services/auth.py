"""Authentication and registration workflows."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.core.security import (
    TokenPair,
    TokenValidationError,
    create_access_token,
    create_token_pair,
    decode_token,
    dummy_verify_password,
    hash_password,
    verify_password,
)
from app.models import Business, User, UserRole
from app.schemas.auth import RegisterBusinessRequest


def register_business(
    db: Session, payload: RegisterBusinessRequest
) -> tuple[Business, User]:
    """Atomically create a business and its first administrator."""
    business = Business(name=payload.business.name, slug=payload.business.slug)
    admin = User(
        business=business,
        name=payload.admin.name,
        email=str(payload.admin.email),
        password_hash=hash_password(payload.admin.password),
        role=UserRole.ADMIN,
    )
    db.add_all((business, admin))
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise AppError(
            status_code=409,
            code="CONFLICT",
            message="Business slug or user email already exists.",
        ) from error
    except Exception:
        db.rollback()
        raise

    db.refresh(business)
    db.refresh(admin)
    return business, admin


def authenticate_user(db: Session, email: str, password: str) -> TokenPair:
    """Authenticate without revealing whether an email exists."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        dummy_verify_password(password)
        raise AppError(
            status_code=401,
            code="AUTH_INVALID_CREDENTIALS",
            message="Invalid email or password.",
        )
    if not verify_password(password, user.password_hash):
        raise AppError(
            status_code=401,
            code="AUTH_INVALID_CREDENTIALS",
            message="Invalid email or password.",
        )
    return create_token_pair(user.id, user.business_id, user.role)


def refresh_access_token(db: Session, refresh_token: str) -> str:
    """Validate a refresh token and issue a new access token."""
    try:
        identity = decode_token(refresh_token, expected_type="refresh")
    except TokenValidationError as error:
        messages = {
            "AUTH_TOKEN_EXPIRED": "Refresh token has expired.",
            "AUTH_TOKEN_WRONG_TYPE": "Refresh token has the wrong type.",
            "AUTH_TOKEN_INVALID": "Refresh token is invalid.",
        }
        raise AppError(
            status_code=401,
            code=error.code,
            message=messages.get(error.code, messages["AUTH_TOKEN_INVALID"]),
        ) from error

    user = db.scalar(
        select(User)
        .options(joinedload(User.business))
        .where(User.id == identity.user_id)
    )
    if user is None:
        raise AppError(
            status_code=401,
            code="AUTH_TOKEN_INVALID",
            message="Refresh token is invalid.",
        )
    return create_access_token(user.id, user.business_id, user.role)
