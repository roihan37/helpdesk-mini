"""Tenant-scoped user management workflows."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password
from app.models import User
from app.schemas.user import UserCreateRequest


def list_business_users(db: Session, business_id: uuid.UUID) -> list[User]:
    """List users only from the administrator's business."""
    return list(
        db.scalars(
            select(User)
            .where(User.business_id == business_id)
            .order_by(User.created_at, User.id)
        ).all()
    )


def create_business_user(
    db: Session, business_id: uuid.UUID, payload: UserCreateRequest
) -> User:
    """Create an agent or customer within the administrator's business."""
    user = User(
        business_id=business_id,
        name=payload.name,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise AppError(
            status_code=409,
            code="CONFLICT",
            message="User email already exists.",
        ) from error
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user
