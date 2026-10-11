"""Guarded startup for the local Docker demo, not a production entrypoint."""

import os
import secrets
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models import Business, Message, Ticket, User
from app.scripts.seed_demo import (
    BUSINESS_SPECS,
    DEMO_PASSWORD_ENV,
    USER_SPECS,
    DemoSeedError,
    seed_demo,
    validate_demo_password,
)

SECRET_PATH = Path("/var/lib/helpdesk-demo/jwt-secret")


def validate_local_demo_target(database_url: str) -> None:
    try:
        url = make_url(database_url)
    except Exception as error:
        raise DemoSeedError("Invalid local demo database URL.") from error
    if (
        url.get_backend_name() != "postgresql"
        or url.host != "db"
        or url.port != 5432
        or url.username != "helpdesk_demo"
        or url.database != "helpdesk_mini_demo"
        or url.query
    ):
        raise DemoSeedError(
            "Automatic initialization is restricted to the Compose local demo database."
        )


def load_demo_secret(path: Path) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        secret = path.read_text(encoding="utf-8").strip()
    else:
        secret = secrets.token_urlsafe(48)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(secret)
    if len(secret) < 32:
        raise DemoSeedError("Persisted local demo JWT secret is invalid.")
    return secret


def initialize_demo(db: Session, password: str) -> bool:
    business_ids = set(db.scalars(select(Business.id)))
    user_ids = set(db.scalars(select(User.id)))
    if {spec.id for spec in BUSINESS_SPECS} <= business_ids and {
        spec.id for spec in USER_SPECS
    } <= user_ids:
        return False
    if (
        business_ids
        or user_ids
        or db.scalar(select(Ticket.id).limit(1)) is not None
        or db.scalar(select(Message.id).limit(1)) is not None
    ):
        raise DemoSeedError(
            "Automatic seed refused: non-empty database has no complete demo identity "
            "manifest. Existing records were not changed."
        )
    db.rollback()  # End the read transaction before the seed's atomic transaction.
    seed_demo(db, password)
    return True


def main() -> int:
    try:
        validate_local_demo_target(os.environ.get("DATABASE_URL", ""))
        password = validate_demo_password(os.environ.get(DEMO_PASSWORD_ENV))
        os.environ["JWT_SECRET"] = load_demo_secret(SECRET_PATH)
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        # Settings must be loaded only after the generated signing secret is available.
        from app.db.session import get_session_factory

        with get_session_factory()() as db:
            created = initialize_demo(db, password)
        print(
            "Local demo initialized: 2 businesses, 8 users, 5 tickets, 7 messages."
            if created
            else "Local demo already initialized; existing data preserved.",
            flush=True,
        )
    except (DemoSeedError, OSError, subprocess.CalledProcessError) as error:
        detail = (
            str(error) if isinstance(error, DemoSeedError) else type(error).__name__
        )
        print(f"Local demo startup refused: {detail}", file=sys.stderr)
        return 2
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--workers",
            "1",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
