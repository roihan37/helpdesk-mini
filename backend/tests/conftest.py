import os

import pytest

# The local M0 environment predates this required M2 setting. Tests make the
# local-only cookie policy explicit without weakening production configuration.
os.environ.setdefault("REFRESH_COOKIE_SECURE", "false")


@pytest.fixture(autouse=True)
def isolate_login_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import login_rate_limit

    monkeypatch.setattr(login_rate_limit, "_limiter", None)
