import stat
from pathlib import Path

import pytest

from app.scripts.seed_demo import DemoSeedError
from app.scripts.start_demo import load_demo_secret, validate_local_demo_target

DEMO_URL = (
    "postgresql+psycopg://helpdesk_demo:local-demo-postgres-only"
    "@db:5432/helpdesk_mini_demo"
)


def test_startup_accepts_only_the_compose_demo_target() -> None:
    validate_local_demo_target(DEMO_URL)


@pytest.mark.parametrize(
    "database_url",
    (
        "",
        DEMO_URL.replace("helpdesk_mini_demo", "production"),
        DEMO_URL.replace("@db:", "@production-db:"),
        DEMO_URL.replace("helpdesk_demo:", "production_user:"),
        DEMO_URL.replace(":5432/", ":5433/"),
        DEMO_URL + "?host=production-db",
        "sqlite:///helpdesk_mini_demo",
    ),
)
def test_startup_rejects_non_demo_targets(database_url: str) -> None:
    with pytest.raises(DemoSeedError):
        validate_local_demo_target(database_url)


def test_generated_secret_is_private_and_preserved_on_restart(tmp_path: Path) -> None:
    path = tmp_path / "state" / "jwt-secret"
    secret = load_demo_secret(path)
    assert len(secret) >= 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_demo_secret(path) == secret
    assert load_demo_secret(tmp_path / "other-secret") != secret


def test_invalid_existing_secret_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "jwt-secret"
    path.write_text("invalid", encoding="utf-8")
    with pytest.raises(DemoSeedError, match="secret is invalid"):
        load_demo_secret(path)
    assert path.read_text(encoding="utf-8") == "invalid"
