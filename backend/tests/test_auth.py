import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.security import (
    TokenPair as SecurityTokenPair,
)
from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.schemas.auth import LoginRequest

client = TestClient(app)


def test_password_is_argon2_hashed_and_verifiable() -> None:
    password = "correct-horse-battery-staple"
    encoded = hash_password(password)

    assert encoded != password
    assert encoded.startswith("$argon2")
    assert verify_password(password, encoded)
    assert not verify_password("wrong-password", encoded)
    assert not verify_password(password, "not-an-argon2-hash")


def test_access_and_refresh_tokens_are_type_separated() -> None:
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    access = create_access_token(user_id, business_id, "admin")
    refresh = create_refresh_token(user_id, business_id, "admin")

    assert decode_token(access, "access").user_id == user_id
    assert decode_token(refresh, "refresh").user_id == user_id
    with pytest.raises(TokenValidationError) as error:
        decode_token(refresh, "access")
    assert error.value.code == "AUTH_TOKEN_WRONG_TYPE"


def test_expired_and_tampered_tokens_are_rejected() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(TokenValidationError) as error:
        decode_token(expired, "access")
    assert error.value.code == "AUTH_TOKEN_EXPIRED"

    token = create_access_token(uuid.uuid4(), uuid.uuid4(), "admin")
    replacement = "a" if token[-1] != "a" else "b"
    with pytest.raises(TokenValidationError) as error:
        decode_token(f"{token[:-1]}{replacement}", "access")
    assert error.value.code == "AUTH_TOKEN_INVALID"


def test_login_schema_normalizes_email_and_forbids_extra_fields() -> None:
    payload = LoginRequest(email="  ADMIN@EXAMPLE.COM ", password="password123")
    assert str(payload.email) == "admin@example.com"

    with pytest.raises(ValidationError):
        LoginRequest.model_validate(
            {
                "email": "admin@example.com",
                "password": "password123",
                "business_id": str(uuid.uuid4()),
            }
        )


def test_login_returns_tokens_and_sets_scoped_httponly_cookie() -> None:
    tokens = SecurityTokenPair(access_token="access.jwt", refresh_token="refresh.jwt")
    with patch("app.api.routes.auth.authenticate_user", return_value=tokens):
        response = client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "access_token": "access.jwt",
            "refresh_token": "refresh.jwt",
            "token_type": "bearer",
            "expires_in": 900,
        }
    }
    cookie = response.headers["set-cookie"]
    assert "refresh_token=refresh.jwt" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/auth/refresh" in cookie
    assert "SameSite=lax" in cookie


def test_refresh_requires_cookie_and_rejects_disallowed_origin() -> None:
    missing = client.post("/auth/refresh")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTH_TOKEN_INVALID"

    with TestClient(app) as cookie_client:
        cookie_client.cookies.set("refresh_token", "refresh.jwt")
        disallowed = cookie_client.post(
            "/auth/refresh",
            headers={"Origin": "https://attacker.example"},
        )
    assert disallowed.status_code == 403
    assert disallowed.json()["error"]["code"] == "FORBIDDEN"


def test_protected_routes_use_standard_unauthenticated_error() -> None:
    for path in ("/auth/me", "/users"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
        assert response.headers["www-authenticate"] == "Bearer"


def test_validation_error_uses_standard_envelope() -> None:
    response = client.post(
        "/auth/login",
        json={"email": "not-an-email", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_openapi_exposes_m2_routes_and_bearer_security() -> None:
    schema = app.openapi()
    expected = {
        "/auth/register-business",
        "/auth/login",
        "/auth/refresh",
        "/auth/me",
        "/users",
    }
    assert expected <= schema["paths"].keys()
    assert schema["paths"]["/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
