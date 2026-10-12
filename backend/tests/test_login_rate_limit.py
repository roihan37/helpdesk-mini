from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier, Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.routes import auth as auth_routes
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.login_rate_limit import LoginRateLimiter, get_login_rate_limiter
from app.core.security import TokenPair
from app.db.session import get_db
from app.main import app

EMAIL = "customer@example.com"
IP = "192.0.2.1"
PAYLOAD = {"email": EMAIL, "password": "wrong-password"}


@dataclass
class Clock:
    now: float = 1_000.0

    def __call__(self) -> float:
        return self.now


def invalid_credentials() -> AppError:
    return AppError(
        status_code=401,
        code="AUTH_INVALID_CREDENTIALS",
        message="Invalid email or password.",
    )


def fail(limiter: LoginRateLimiter, email: str = EMAIL, ip: str = IP) -> None:
    with pytest.raises(AppError) as error:
        with limiter.attempt(email, ip):
            raise invalid_credentials()
    assert error.value.status_code == 401
    assert error.value.code == "AUTH_INVALID_CREDENTIALS"
    assert error.value.message == "Invalid email or password."


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def limiter(clock: Clock) -> LoginRateLimiter:
    return LoginRateLimiter(
        max_failed_attempts=5,
        failed_window_seconds=900,
        ip_max_requests=30,
        ip_window_seconds=60,
        clock=clock,
    )


@pytest.fixture
def authenticate(monkeypatch: pytest.MonkeyPatch) -> Mock:
    mock = Mock(side_effect=invalid_credentials())
    monkeypatch.setattr(auth_routes, "authenticate_user", mock)
    return mock


@pytest.fixture
def client(limiter: LoginRateLimiter, authenticate: Mock) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        with Session() as db:
            yield db

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_login_rate_limiter] = lambda: limiter
    try:
        with TestClient(app, client=(IP, 50_000)) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_normal_login_preserves_tokens_and_refresh_cookie(
    client: TestClient, authenticate: Mock
) -> None:
    authenticate.side_effect = None
    authenticate.return_value = TokenPair("access.jwt", "refresh.jwt")
    response = client.post("/auth/login", json=PAYLOAD)
    assert response.status_code == 200
    assert response.json()["data"]["access_token"] == "access.jwt"
    assert response.json()["data"]["refresh_token"] == "refresh.jwt"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Path=/auth/refresh" in response.headers["set-cookie"]
    assert "retry-after" not in response.headers


def test_five_failures_return_401_then_429_without_authenticating(
    client: TestClient, authenticate: Mock
) -> None:
    for _ in range(5):
        response = client.post("/auth/login", json=PAYLOAD)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
        assert "retry-after" not in response.headers
    response = client.post("/auth/login", json=PAYLOAD)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"
    assert response.json() == {
        "error": {
            "code": "AUTH_RATE_LIMITED",
            "message": "Too many login attempts. Please try again later.",
            "details": None,
        }
    }
    assert "set-cookie" not in response.headers
    assert EMAIL not in response.text
    assert PAYLOAD["password"] not in response.text
    assert authenticate.call_count == 5


def test_valid_credentials_remain_blocked_until_window_expires(
    client: TestClient, authenticate: Mock, clock: Clock
) -> None:
    for _ in range(5):
        assert client.post("/auth/login", json=PAYLOAD).status_code == 401
    authenticate.side_effect = None
    authenticate.return_value = TokenPair("access.jwt", "refresh.jwt")
    response = client.post("/auth/login", json=PAYLOAD)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"
    assert authenticate.call_count == 5
    clock.now += 900
    response = client.post("/auth/login", json=PAYLOAD)
    assert response.status_code == 200
    assert "retry-after" not in response.headers
    assert authenticate.call_count == 6


def test_case_and_whitespace_share_the_same_failure_limit(client: TestClient) -> None:
    for email in (EMAIL, EMAIL.upper(), f"  {EMAIL}  ", EMAIL, EMAIL.upper()):
        assert (
            client.post("/auth/login", json={**PAYLOAD, "email": email}).status_code
            == 401
        )
    assert client.post("/auth/login", json=PAYLOAD).status_code == 429


def test_different_email_and_peer_ip_have_independent_limits(
    client: TestClient,
) -> None:
    for _ in range(5):
        assert client.post("/auth/login", json=PAYLOAD).status_code == 401
    assert client.post("/auth/login", json=PAYLOAD).status_code == 429
    assert (
        client.post(
            "/auth/login", json={**PAYLOAD, "email": "another@example.com"}
        ).status_code
        == 401
    )
    with TestClient(app, client=("192.0.2.2", 50_001)) as other:
        assert other.post("/auth/login", json=PAYLOAD).status_code == 401


def test_client_forwarded_headers_cannot_bypass_limits(client: TestClient) -> None:
    for _ in range(5):
        assert client.post("/auth/login", json=PAYLOAD).status_code == 401
    response = client.post(
        "/auth/login",
        json=PAYLOAD,
        headers={
            "X-Forwarded-For": "198.51.100.1",
            "X-Real-IP": "198.51.100.2",
            "Forwarded": "for=198.51.100.3",
        },
    )
    assert response.status_code == 429


def test_retry_after_rounds_up_and_failure_window_expires(
    client: TestClient, clock: Clock, authenticate: Mock
) -> None:
    for _ in range(5):
        assert client.post("/auth/login", json=PAYLOAD).status_code == 401
    clock.now += 0.25
    response = client.post("/auth/login", json=PAYLOAD)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"
    clock.now += 1
    assert client.post("/auth/login", json=PAYLOAD).headers["retry-after"] == "899"
    clock.now += 898.75
    assert client.post("/auth/login", json=PAYLOAD).status_code == 401
    assert authenticate.call_count == 6


def test_success_does_not_erase_recent_failures(
    client: TestClient, authenticate: Mock
) -> None:
    for _ in range(4):
        assert client.post("/auth/login", json=PAYLOAD).status_code == 401
    authenticate.side_effect = None
    authenticate.return_value = TokenPair("access.jwt", "refresh.jwt")
    assert client.post("/auth/login", json=PAYLOAD).status_code == 200
    authenticate.side_effect = invalid_credentials()
    assert client.post("/auth/login", json=PAYLOAD).status_code == 401
    assert client.post("/auth/login", json=PAYLOAD).status_code == 429


def test_ip_limit_counts_different_emails_successes_and_invalid_payloads(
    client: TestClient, limiter: LoginRateLimiter, clock: Clock, authenticate: Mock
) -> None:
    limiter.ip_max_requests = 3
    authenticate.side_effect = None
    authenticate.return_value = TokenPair("access.jwt", "refresh.jwt")
    assert client.post("/auth/login", json=PAYLOAD).status_code == 200
    authenticate.side_effect = invalid_credentials()
    assert (
        client.post(
            "/auth/login", json={**PAYLOAD, "email": "other@example.com"}
        ).status_code
        == 401
    )
    assert client.post("/auth/login", json={"email": "invalid"}).status_code == 422
    response = client.post("/auth/login", json=PAYLOAD)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert authenticate.call_count == 2
    with TestClient(app, client=("192.0.2.2", 50_001)) as other:
        assert other.post("/auth/login", json=PAYLOAD).status_code == 401
    clock.now += 59.5
    assert client.post("/auth/login", json=PAYLOAD).headers["retry-after"] == "1"
    clock.now += 0.5
    assert client.post("/auth/login", json=PAYLOAD).status_code == 401


def test_default_ip_cap_is_thirty_requests(client: TestClient) -> None:
    for index in range(30):
        assert (
            client.post(
                "/auth/login", json={**PAYLOAD, "email": f"user{index}@example.com"}
            ).status_code
            == 401
        )
    assert client.post("/auth/login", json=PAYLOAD).status_code == 429


def test_retry_after_is_exposed_to_allowed_browser_origin(client: TestClient) -> None:
    for _ in range(5):
        client.post("/auth/login", json=PAYLOAD)
    origin = str(get_settings().cors_origins[0]).rstrip("/")
    response = client.post("/auth/login", json=PAYLOAD, headers={"Origin": origin})
    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "Retry-After" in response.headers["access-control-expose-headers"]


@pytest.mark.parametrize("failed", (True, False))
def test_concurrent_attempts_reserve_slots_and_release_them(
    limiter: LoginRateLimiter, failed: bool
) -> None:
    entered = Barrier(6)
    release = Event()

    def attempt() -> int:
        try:
            with limiter.attempt(EMAIL, IP):
                entered.wait(timeout=5)
                assert release.wait(timeout=5)
                if failed:
                    raise invalid_credentials()
            return 200
        except AppError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(attempt) for _ in range(5)]
        try:
            entered.wait(timeout=5)
            with pytest.raises(AppError) as blocked:
                with limiter.attempt(EMAIL, IP):
                    pytest.fail("Concurrent sixth attempt must not be admitted")
            assert blocked.value.status_code == 429
            assert blocked.value.headers == {"Retry-After": "900"}
        finally:
            release.set()
        assert [future.result(timeout=5) for future in futures] == [
            401 if failed else 200
        ] * 5
    if failed:
        with pytest.raises(AppError) as blocked:
            with limiter.attempt(EMAIL, IP):
                pytest.fail("Five concurrent failures must remain limited")
        assert blocked.value.status_code == 429
    else:
        with limiter.attempt(EMAIL, IP):
            pass


def test_concurrent_ip_checks_cannot_exceed_cap(clock: Clock) -> None:
    limiter = LoginRateLimiter(
        max_failed_attempts=5,
        failed_window_seconds=900,
        ip_max_requests=3,
        ip_window_seconds=60,
        clock=clock,
    )
    start = Barrier(11)

    def check() -> int:
        start.wait(timeout=5)
        try:
            limiter.check_ip(IP)
            return 200
        except AppError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check) for _ in range(10)]
        start.wait(timeout=5)
        results = [future.result(timeout=5) for future in futures]
    assert results.count(200) == 3
    assert results.count(429) == 7


def test_singleton_initialization_is_concurrency_safe() -> None:
    with ThreadPoolExecutor(max_workers=10) as executor:
        limiters = list(executor.map(lambda _: get_login_rate_limiter(), range(10)))
    assert all(limiter is limiters[0] for limiter in limiters)


def test_server_errors_release_reservations_without_counting_failures(
    limiter: LoginRateLimiter,
) -> None:
    for _ in range(6):
        with pytest.raises(RuntimeError):
            with limiter.attempt(EMAIL, IP):
                raise RuntimeError("Database unavailable")
    for _ in range(5):
        fail(limiter)
    with pytest.raises(AppError) as blocked:
        with limiter.attempt(EMAIL, IP):
            pytest.fail("Only invalid credentials should count as failures")
    assert blocked.value.status_code == 429


def test_memory_capacity_fails_closed_without_evicting_live_limits(
    clock: Clock,
) -> None:
    limiter = LoginRateLimiter(
        max_failed_attempts=1,
        failed_window_seconds=900,
        ip_max_requests=30,
        ip_window_seconds=60,
        clock=clock,
        max_keys=2,
    )
    fail(limiter)
    fail(limiter, "other@example.com")
    for email in (EMAIL, "third@example.com"):
        with pytest.raises(AppError) as blocked:
            with limiter.attempt(email, IP):
                pytest.fail("Live limits must not be evicted at capacity")
        assert blocked.value.status_code == 429
        assert blocked.value.headers == {"Retry-After": "900"}
    clock.now += 900
    with limiter.attempt("third@example.com", IP):
        pass


def test_rate_limits_are_environment_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGIN_MAX_FAILED_ATTEMPTS", "2")
    monkeypatch.setenv("LOGIN_FAILED_WINDOW_SECONDS", "120")
    monkeypatch.setenv("LOGIN_IP_MAX_REQUESTS", "10")
    monkeypatch.setenv("LOGIN_IP_WINDOW_SECONDS", "30")
    settings = Settings()  # type: ignore[call-arg]
    assert settings.login_max_failed_attempts == 2
    assert settings.login_failed_window_seconds == 120
    assert settings.login_ip_max_requests == 10
    assert settings.login_ip_window_seconds == 30


@pytest.mark.parametrize(
    "name",
    (
        "LOGIN_MAX_FAILED_ATTEMPTS",
        "LOGIN_FAILED_WINDOW_SECONDS",
        "LOGIN_IP_MAX_REQUESTS",
        "LOGIN_IP_WINDOW_SECONDS",
    ),
)
def test_invalid_rate_limit_configuration_is_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(name, "0")
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_openapi_documents_rate_limit_error_and_retry_header() -> None:
    response = app.openapi()["paths"]["/auth/login"]["post"]["responses"]["429"]
    assert response["headers"]["Retry-After"]["schema"] == {
        "type": "integer",
        "minimum": 1,
    }
    assert response["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
