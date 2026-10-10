from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session_factory() -> sessionmaker[Session]:
    """Return the application session factory for short-lived worker sessions."""
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
