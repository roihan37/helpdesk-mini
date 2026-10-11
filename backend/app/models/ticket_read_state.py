"""Private, monotonic conversation read cursor for one user and ticket."""

import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketReadState(Base):
    __tablename__ = "ticket_read_states"
    __table_args__ = (
        CheckConstraint(
            "last_read_sequence >= 0",
            name="ck_ticket_read_states_last_read_sequence_nonnegative",
        ),
        Index("ix_ticket_read_states_ticket_id", "ticket_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_ticket_read_states_user_id_users"),
        primary_key=True,
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", name="fk_ticket_read_states_ticket_id_tickets"),
        primary_key=True,
    )
    last_read_sequence: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
