import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.message import Message
    from app.models.ticket import Ticket


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'agent', 'customer')",
            name="ck_users_role_allowed",
        ),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_business_id", "business_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", name="fk_users_business_id_businesses"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    business: Mapped["Business"] = relationship(back_populates="users")
    customer_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="customer",
        foreign_keys="Ticket.customer_id",
    )
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assigned_agent",
        foreign_keys="Ticket.assigned_agent_id",
    )
    sent_messages: Mapped[list["Message"]] = relationship(back_populates="sender")
