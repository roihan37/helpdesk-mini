import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.routes import auth as auth_routes
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.main import app
from app.models import Business, User, UserRole

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(scope="session")
def integration_engine() -> Iterator[Engine]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.fail("TEST_DATABASE_URL must point to a disposable PostgreSQL database")

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail(
            "M2 integration tests require a PostgreSQL database whose "
            "name ends with '_test'"
        )

    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(integration_engine: Engine) -> Iterator[Session]:
    connection = integration_engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_business(db: Session, name: str) -> Business:
    slug_prefix = "-".join(name.lower().split())
    business = Business(name=name, slug=f"{slug_prefix}-{uuid.uuid4()}")
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


def create_user(
    db: Session,
    business: Business,
    role: UserRole,
    *,
    email: str | None = None,
    password: str = PASSWORD,
) -> User:
    user = User(
        business=business,
        name=f"{role.value.title()} User",
        email=email or f"{role.value}-{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def bearer(
    user: User, *, business_id: uuid.UUID | None = None, role: str | None = None
) -> dict[str, str]:
    token = create_access_token(
        user.id,
        business_id or user.business_id,
        role or user.role,
    )
    return {"Authorization": f"Bearer {token}"}


def assert_standard_error(response: object, status_code: int, code: str) -> None:
    assert getattr(response, "status_code") == status_code
    payload = getattr(response, "json")()
    assert payload == {
        "error": {
            "code": code,
            "message": payload["error"]["message"],
            "details": payload["error"]["details"],
        }
    }


def test_registration_creates_business_and_hashed_admin_atomically(
    client: TestClient, db: Session
) -> None:
    email = f"owner-{uuid.uuid4()}@example.com"
    response = client.post(
        "/auth/register-business",
        json={
            "business": {"name": "Acme Support", "slug": f"acme-{uuid.uuid4()}"},
            "admin": {"name": "Owner", "email": email, "password": PASSWORD},
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["admin"]["role"] == "admin"
    assert payload["admin"]["business_id"] == payload["business"]["id"]
    assert "password" not in response.text.lower()

    admin = db.scalar(select(User).where(User.email == email))
    assert admin is not None
    assert admin.business_id == uuid.UUID(payload["business"]["id"])
    assert admin.password_hash != PASSWORD
    assert admin.password_hash.startswith("$argon2")
    assert verify_password(PASSWORD, admin.password_hash)


def test_registration_conflicts_are_safe_and_roll_back_both_records(
    client: TestClient, db: Session
) -> None:
    existing_business = create_business(db, "Existing")
    existing_email = f"existing-{uuid.uuid4()}@example.com"
    create_user(db, existing_business, UserRole.ADMIN, email=existing_email)
    duplicate_slug = existing_business.slug

    slug_response = client.post(
        "/auth/register-business",
        json={
            "business": {"name": "Duplicate", "slug": duplicate_slug},
            "admin": {
                "name": "New Owner",
                "email": f"new-{uuid.uuid4()}@example.com",
                "password": PASSWORD,
            },
        },
    )
    assert_standard_error(slug_response, 409, "CONFLICT")
    assert (
        db.scalar(
            select(func.count())
            .select_from(Business)
            .where(Business.slug == duplicate_slug)
        )
        == 1
    )

    rolled_back_slug = f"rolled-back-{uuid.uuid4()}"
    email_response = client.post(
        "/auth/register-business",
        json={
            "business": {"name": "Must Roll Back", "slug": rolled_back_slug},
            "admin": {
                "name": "Duplicate Email",
                "email": existing_email,
                "password": PASSWORD,
            },
        },
    )
    assert_standard_error(email_response, 409, "CONFLICT")
    assert (
        db.scalar(
            select(func.count())
            .select_from(Business)
            .where(Business.slug == rolled_back_slug)
        )
        == 0
    )
    assert "unique" not in email_response.text.lower()


def test_login_returns_valid_typed_tokens_and_refresh_cookie(
    client: TestClient, db: Session
) -> None:
    business = create_business(db, "Login")
    email = f"login-{uuid.uuid4()}@example.com"
    user = create_user(db, business, UserRole.ADMIN, email=email)

    response = client.post(
        "/auth/login", json={"email": email.upper(), "password": PASSWORD}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    settings = get_settings()
    access_claims = jwt.decode(
        data["access_token"], settings.jwt_secret, algorithms=["HS256"]
    )
    refresh_claims = jwt.decode(
        data["refresh_token"], settings.jwt_secret, algorithms=["HS256"]
    )
    assert access_claims["sub"] == refresh_claims["sub"] == str(user.id)
    assert access_claims["business_id"] == str(business.id)
    assert access_claims["role"] == "admin"
    assert access_claims["type"] == "access"
    assert refresh_claims["type"] == "refresh"
    assert data["expires_in"] == settings.access_token_expire_minutes * 60
    assert "password" not in response.text.lower()

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Path=/auth/refresh" in cookie
    assert "SameSite=lax" in cookie
    assert ("Secure" in cookie) is settings.refresh_cookie_secure


def test_login_uses_same_safe_error_for_wrong_password_and_unknown_email(
    client: TestClient, db: Session
) -> None:
    business = create_business(db, "Credentials")
    email = f"known-{uuid.uuid4()}@example.com"
    create_user(db, business, UserRole.CUSTOMER, email=email)

    wrong_password = client.post(
        "/auth/login", json={"email": email, "password": "incorrect-password"}
    )
    unknown_email = client.post(
        "/auth/login",
        json={
            "email": f"unknown-{uuid.uuid4()}@example.com",
            "password": "incorrect-password",
        },
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


def test_refresh_issues_access_token_for_current_database_identity(
    client: TestClient, db: Session
) -> None:
    business = create_business(db, "Refresh")
    user = create_user(db, business, UserRole.AGENT)
    token = create_refresh_token(user.id, uuid.uuid4(), UserRole.ADMIN)
    client.cookies.set("refresh_token", token, path="/auth/refresh")

    response = client.post("/auth/refresh")

    assert response.status_code == 200
    data = response.json()["data"]
    claims = jwt.decode(
        data["access_token"], get_settings().jwt_secret, algorithms=["HS256"]
    )
    assert claims["type"] == "access"
    assert claims["business_id"] == str(business.id)
    assert claims["role"] == "agent"
    assert "refresh_token" not in data


@pytest.mark.parametrize("kind", ["expired", "invalid_signature", "access"])
def test_refresh_rejects_invalid_expired_or_wrong_type_cookie(
    client: TestClient, db: Session, kind: str
) -> None:
    settings = get_settings()
    business = create_business(db, f"Refresh {kind}")
    user = create_user(db, business, UserRole.CUSTOMER)
    now = datetime.now(UTC)
    if kind == "expired":
        token = jwt.encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "iat": now - timedelta(minutes=2),
                "exp": now - timedelta(minutes=1),
            },
            settings.jwt_secret,
            algorithm="HS256",
        )
        expected_code = "AUTH_TOKEN_EXPIRED"
    elif kind == "invalid_signature":
        token = jwt.encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            "different-secret-that-is-long-enough",
            algorithm="HS256",
        )
        expected_code = "AUTH_TOKEN_INVALID"
    else:
        token = create_access_token(user.id, business.id, user.role)
        expected_code = "AUTH_TOKEN_WRONG_TYPE"
    client.cookies.set("refresh_token", token, path="/auth/refresh")

    response = client.post("/auth/refresh")

    assert_standard_error(response, 401, expected_code)


def test_refresh_rejects_missing_cookie_and_nonexistent_user(
    client: TestClient,
) -> None:
    missing = client.post("/auth/refresh")
    assert_standard_error(missing, 401, "AUTH_TOKEN_INVALID")

    token = create_refresh_token(uuid.uuid4(), uuid.uuid4(), UserRole.ADMIN)
    client.cookies.set("refresh_token", token, path="/auth/refresh")
    deleted = client.post("/auth/refresh")
    assert_standard_error(deleted, 401, "AUTH_TOKEN_INVALID")


def test_me_uses_database_identity_and_never_exposes_hash(
    client: TestClient, db: Session
) -> None:
    business = create_business(db, "Profile")
    user = create_user(db, business, UserRole.CUSTOMER)
    headers = bearer(user, business_id=uuid.uuid4(), role=UserRole.ADMIN)

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(user.id)
    assert data["role"] == "customer"
    assert data["business"]["id"] == str(business.id)
    assert "password" not in response.text.lower()


@pytest.mark.parametrize("kind", ["missing", "expired", "invalid_signature", "refresh"])
def test_me_rejects_missing_or_invalid_access_credentials(
    client: TestClient, db: Session, kind: str
) -> None:
    if kind == "missing":
        response = client.get("/auth/me")
        expected_code = "AUTH_TOKEN_INVALID"
    else:
        settings = get_settings()
        business = create_business(db, f"Me {kind}")
        user = create_user(db, business, UserRole.CUSTOMER)
        now = datetime.now(UTC)
        if kind == "expired":
            token = jwt.encode(
                {
                    "sub": str(user.id),
                    "type": "access",
                    "iat": now - timedelta(minutes=2),
                    "exp": now - timedelta(minutes=1),
                },
                settings.jwt_secret,
                algorithm="HS256",
            )
            expected_code = "AUTH_TOKEN_EXPIRED"
        elif kind == "invalid_signature":
            token = jwt.encode(
                {
                    "sub": str(user.id),
                    "type": "access",
                    "iat": now,
                    "exp": now + timedelta(minutes=5),
                },
                "different-secret-that-is-long-enough",
                algorithm="HS256",
            )
            expected_code = "AUTH_TOKEN_INVALID"
        else:
            token = create_refresh_token(user.id, business.id, user.role)
            expected_code = "AUTH_TOKEN_WRONG_TYPE"
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert_standard_error(response, 401, expected_code)
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_rejects_access_token_after_user_is_deleted(
    client: TestClient, db: Session
) -> None:
    business = create_business(db, "Deleted Identity")
    user = create_user(db, business, UserRole.CUSTOMER)
    headers = bearer(user)

    db.delete(user)
    db.commit()

    response = client.get("/auth/me", headers=headers)

    assert_standard_error(response, 401, "AUTH_TOKEN_INVALID")
    assert response.headers["www-authenticate"] == "Bearer"


def test_admin_lists_only_current_database_tenant(
    client: TestClient, db: Session
) -> None:
    business_a = create_business(db, "Tenant A")
    admin_a = create_user(db, business_a, UserRole.ADMIN)
    agent_a = create_user(db, business_a, UserRole.AGENT)
    business_b = create_business(db, "Tenant B")
    admin_b = create_user(db, business_b, UserRole.ADMIN)
    customer_b = create_user(db, business_b, UserRole.CUSTOMER)

    response_a = client.get(
        "/users", headers=bearer(admin_a, business_id=business_b.id, role="customer")
    )
    response_b = client.get("/users", headers=bearer(admin_b))

    assert response_a.status_code == response_b.status_code == 200
    assert {item["id"] for item in response_a.json()["data"]} == {
        str(admin_a.id),
        str(agent_a.id),
    }
    assert {item["id"] for item in response_b.json()["data"]} == {
        str(admin_b.id),
        str(customer_b.id),
    }
    assert "password" not in response_a.text.lower()
    assert "password" not in response_b.text.lower()


@pytest.mark.parametrize("role", [UserRole.AGENT, UserRole.CUSTOMER])
@pytest.mark.parametrize("method", ["get", "post"])
def test_non_admin_cannot_list_or_create_users(
    client: TestClient, db: Session, role: UserRole, method: str
) -> None:
    business = create_business(db, f"Denied {role.value} {method}")
    user = create_user(db, business, role)
    headers = bearer(user, role=UserRole.ADMIN)

    if method == "get":
        response = client.get("/users", headers=headers)
    else:
        response = client.post(
            "/users",
            headers=headers,
            json={
                "name": "Unauthorized",
                "email": f"unauthorized-{uuid.uuid4()}@example.com",
                "password": PASSWORD,
                "role": "agent",
            },
        )

    assert_standard_error(response, 403, "FORBIDDEN")


@pytest.mark.parametrize("role", ["agent", "customer"])
def test_admin_creates_hashed_user_in_own_tenant(
    client: TestClient, db: Session, role: str
) -> None:
    business_a = create_business(db, f"Create {role}")
    admin_a = create_user(db, business_a, UserRole.ADMIN)
    create_business(db, f"Other {role}")
    email = f"created-{role}-{uuid.uuid4()}@example.com"

    response = client.post(
        "/users",
        headers=bearer(admin_a),
        json={
            "name": "Created User",
            "email": email,
            "password": PASSWORD,
            "role": role,
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["business_id"] == str(business_a.id)
    assert "password" not in response.text.lower()
    created = db.scalar(select(User).where(User.email == email))
    assert created is not None
    assert created.business_id == business_a.id
    assert created.password_hash != PASSWORD
    assert verify_password(PASSWORD, created.password_hash)


def test_user_creation_rejects_tenant_and_admin_injection(
    client: TestClient, db: Session
) -> None:
    business_a = create_business(db, "Injection A")
    admin_a = create_user(db, business_a, UserRole.ADMIN)
    business_b = create_business(db, "Injection B")
    base_payload = {
        "name": "Injected User",
        "email": f"injected-{uuid.uuid4()}@example.com",
        "password": PASSWORD,
        "role": "agent",
    }

    tenant_response = client.post(
        "/users",
        headers=bearer(admin_a),
        json={**base_payload, "business_id": str(business_b.id)},
    )
    admin_response = client.post(
        "/users",
        headers=bearer(admin_a),
        json={
            **base_payload,
            "email": f"admin-{uuid.uuid4()}@example.com",
            "role": "admin",
        },
    )

    assert_standard_error(tenant_response, 422, "VALIDATION_ERROR")
    assert_standard_error(admin_response, 422, "VALIDATION_ERROR")
    assert (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.business_id == business_b.id)
        )
        == 0
    )


def test_duplicate_email_is_rejected_globally_for_admin_creation(
    client: TestClient, db: Session
) -> None:
    business_a = create_business(db, "Duplicate A")
    admin_a = create_user(db, business_a, UserRole.ADMIN)
    business_b = create_business(db, "Duplicate B")
    email = f"global-{uuid.uuid4()}@example.com"
    create_user(db, business_b, UserRole.CUSTOMER, email=email)

    response = client.post(
        "/users",
        headers=bearer(admin_a),
        json={
            "name": "Duplicate",
            "email": email,
            "password": PASSWORD,
            "role": "agent",
        },
    )

    assert_standard_error(response, 409, "CONFLICT")
    assert "unique" not in response.text.lower()


def test_cookie_secure_flag_and_cors_are_environment_aware(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_routes.settings, "refresh_cookie_secure", True)
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401

    from fastapi import Response

    cookie_response = Response()
    auth_routes._set_refresh_cookie(cookie_response, "opaque-token")
    assert "Secure" in cookie_response.headers["set-cookie"]

    origin = str(get_settings().cors_origins[0]).rstrip("/")
    allowed = client.options(
        "/auth/refresh",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    denied = client.options(
        "/auth/refresh",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == origin
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_refresh_origin_policy_allows_configured_and_rejects_untrusted_origin(
    client: TestClient, db: Session
) -> None:
    business = create_business(db, "Origin")
    user = create_user(db, business, UserRole.CUSTOMER)
    token = create_refresh_token(user.id, business.id, user.role)
    client.cookies.set("refresh_token", token, path="/auth/refresh")
    allowed_origin = str(get_settings().cors_origins[0]).rstrip("/")

    allowed = client.post("/auth/refresh", headers={"Origin": allowed_origin})
    denied = client.post(
        "/auth/refresh", headers={"Origin": "https://attacker.example"}
    )

    assert allowed.status_code == 200
    assert_standard_error(denied, 403, "FORBIDDEN")
