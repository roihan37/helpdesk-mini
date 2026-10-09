import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class TokenIdentity:
    user_id: uuid.UUID
    token_type: TokenType


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class TokenValidationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def dummy_verify_password(password: str) -> None:
    verify_password(password, _dummy_password_hash)


def _create_token(
    user_id: uuid.UUID,
    business_id: uuid.UUID,
    role: str,
    token_type: TokenType,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_expire_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_expire_days)
    )
    return jwt.encode(
        {
            "sub": str(user_id),
            "business_id": str(business_id),
            "role": role,
            "type": token_type,
            "iat": now,
            "exp": now + lifetime,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(user_id: uuid.UUID, business_id: uuid.UUID, role: str) -> str:
    return _create_token(user_id, business_id, role, "access")


def create_refresh_token(user_id: uuid.UUID, business_id: uuid.UUID, role: str) -> str:
    return _create_token(user_id, business_id, role, "refresh")


def create_token_pair(
    user_id: uuid.UUID, business_id: uuid.UUID, role: str
) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id, business_id, role),
        refresh_token=create_refresh_token(user_id, business_id, role),
    )


def decode_token(token: str, expected_type: TokenType) -> TokenIdentity:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenValidationError("AUTH_TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise TokenValidationError("AUTH_TOKEN_INVALID") from exc

    if payload.get("type") != expected_type:
        raise TokenValidationError("AUTH_TOKEN_WRONG_TYPE")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (AttributeError, TypeError, ValueError) as exc:
        raise TokenValidationError("AUTH_TOKEN_INVALID") from exc
    return TokenIdentity(user_id=user_id, token_type=expected_type)
