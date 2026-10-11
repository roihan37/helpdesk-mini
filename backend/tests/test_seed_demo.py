import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import Business, Message, Ticket, User
from app.models.enums import TicketStatus, UserRole
from app.scripts.seed_demo import (
    BUSINESS_SPECS,
    MESSAGE_SPECS,
    TICKET_SPECS,
    USER_SPECS,
    DemoSeedError,
    seed_demo,
    validate_database_target,
)

PASSWORD = "local-demo-password-2026"
BUSINESS_IDS = tuple(spec.id for spec in BUSINESS_SPECS)
BUSINESS_SLUGS = tuple(spec.slug for spec in BUSINESS_SPECS)
USER_IDS = tuple(spec.id for spec in USER_SPECS)
USER_EMAILS = tuple(spec.email for spec in USER_SPECS)
TICKET_IDS = tuple(spec.id for spec in TICKET_SPECS)
MESSAGE_IDS = tuple(spec.id for spec in MESSAGE_SPECS)


def _remove_demo_records(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(delete(Message).where(Message.id.in_(MESSAGE_IDS)))
        connection.execute(delete(Ticket).where(Ticket.id.in_(TICKET_IDS)))
        connection.execute(
            delete(User).where((User.id.in_(USER_IDS)) | (User.email.in_(USER_EMAILS)))
        )
        connection.execute(
            delete(Business).where(
                (Business.id.in_(BUSINESS_IDS)) | (Business.slug.in_(BUSINESS_SLUGS))
            )
        )


@pytest.fixture(scope="session")
def seed_engine() -> Iterator[Engine]:
    database_url = os.environ.get("M1_TEST_DATABASE_URL")
    if database_url is None:
        pytest.fail(
            "M1_TEST_DATABASE_URL must point to a disposable PostgreSQL database"
        )
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail("Seed tests require a PostgreSQL database ending with '_test'")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_demo_records(seed_engine: Engine) -> Iterator[None]:
    _remove_demo_records(seed_engine)
    yield
    _remove_demo_records(seed_engine)


def test_seed_creates_required_manifest_and_hashed_passwords(
    seed_engine: Engine,
) -> None:
    with Session(seed_engine) as db:
        result = seed_demo(db, PASSWORD)
        businesses = db.scalars(
            select(Business).where(Business.id.in_(BUSINESS_IDS))
        ).all()
        users = db.scalars(select(User).where(User.id.in_(USER_IDS))).all()
        tickets = db.scalars(select(Ticket).where(Ticket.id.in_(TICKET_IDS))).all()
        messages = db.scalars(select(Message).where(Message.id.in_(MESSAGE_IDS))).all()

    assert result.businesses == 2
    assert result.users == 8
    assert len(businesses) == 2
    assert len(users) == 8
    assert len(tickets) == 5
    assert len(messages) == 7
    for business in businesses:
        business_users = [user for user in users if user.business_id == business.id]
        assert [user.role for user in business_users].count(UserRole.ADMIN) == 1
        assert [user.role for user in business_users].count(UserRole.AGENT) == 1
        assert [user.role for user in business_users].count(UserRole.CUSTOMER) == 2
    assert all(user.password_hash != PASSWORD for user in users)
    assert all(verify_password(PASSWORD, user.password_hash) for user in users)
    assert {ticket.status for ticket in tickets} >= {
        TicketStatus.OPEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    }
    assert all(
        next(user for user in users if user.id == ticket.customer_id).business_id
        == ticket.business_id
        for ticket in tickets
    )
    assert all(
        next(ticket for ticket in tickets if ticket.id == message.ticket_id).business_id
        == next(user for user in users if user.id == message.sender_id).business_id
        for message in messages
    )
    assert all(
        (sender := next(user for user in users if user.id == message.sender_id)).role
        == UserRole.AGENT
        or (
            sender.role == UserRole.CUSTOMER
            and sender.id
            == next(
                ticket for ticket in tickets if ticket.id == message.ticket_id
            ).customer_id
        )
        for message in messages
    )


def test_seed_is_idempotent_and_preserves_unrelated_rows(seed_engine: Engine) -> None:
    unrelated_id = uuid.uuid4()
    with Session(seed_engine) as db:
        with db.begin():
            db.add(
                Business(
                    id=unrelated_id,
                    name="Unrelated Test Business",
                    slug=f"unrelated-{unrelated_id}",
                )
            )
        seed_demo(db, PASSWORD)
        seed_demo(db, PASSWORD)
        assert db.scalar(
            select(func.count())
            .select_from(Business)
            .where(Business.id.in_(BUSINESS_IDS))
        ) == len(BUSINESS_IDS)
        assert db.scalar(
            select(func.count()).select_from(User).where(User.id.in_(USER_IDS))
        ) == len(USER_IDS)
        assert db.get(Business, unrelated_id) is not None
        unrelated = db.get(Business, unrelated_id)
        assert unrelated is not None
        db.delete(unrelated)
        db.commit()


def test_seed_rolls_back_all_new_rows_on_conflict(seed_engine: Engine) -> None:
    conflicting_id = uuid.uuid4()
    orbit = BUSINESS_SPECS[1]
    with Session(seed_engine) as db:
        with db.begin():
            db.add(
                Business(
                    id=conflicting_id,
                    name="Conflicting Orbit",
                    slug=orbit.slug,
                )
            )
        with pytest.raises(DemoSeedError, match="no demo changes were committed"):
            seed_demo(db, PASSWORD)
        assert (
            db.scalar(
                select(func.count())
                .select_from(Business)
                .where(Business.id.in_(BUSINESS_IDS))
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count()).select_from(User).where(User.id.in_(USER_IDS))
            )
            == 0
        )


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql+psycopg://user:secret@db.example/prod",
        "postgresql+psycopg://user:secret@db.example/helpdesk-production",
        "postgresql+psycopg://user:secret@prod-db.example/helpdesk",
        "postgresql+psycopg://user:secret@localhost/postgres",
    ),
)
def test_seed_refuses_protected_or_production_targets(database_url: str) -> None:
    with pytest.raises(DemoSeedError, match="Refusing"):
        validate_database_target(database_url, confirmed=True)


def test_seed_requires_explicit_confirmation() -> None:
    with pytest.raises(DemoSeedError, match="--confirm-demo-data"):
        validate_database_target(
            "postgresql+psycopg://user:secret@localhost/helpdesk_mini",
            confirmed=False,
        )
