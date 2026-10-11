"""Add message positions and private ticket read cursors.

Revision ID: b5c8d41e92af
Revises: a3930ac451be
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5c8d41e92af"
down_revision: str | None = "a3930ac451be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL assigns positions to existing rows without changing their history.
    op.add_column(
        "messages",
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=True), nullable=False),
    )
    op.create_index(
        "ix_messages_ticket_id_sequence",
        "messages",
        ["ticket_id", "sequence"],
        unique=True,
    )
    op.create_table(
        "ticket_read_states",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("last_read_sequence", sa.BigInteger(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "last_read_sequence >= 0",
            name="ck_ticket_read_states_last_read_sequence_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_ticket_read_states_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], name="fk_ticket_read_states_ticket_id_tickets"
        ),
        sa.PrimaryKeyConstraint("user_id", "ticket_id", name="pk_ticket_read_states"),
    )
    op.create_index(
        "ix_ticket_read_states_ticket_id", "ticket_read_states", ["ticket_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_read_states_ticket_id", table_name="ticket_read_states")
    op.drop_table("ticket_read_states")
    op.drop_index("ix_messages_ticket_id_sequence", table_name="messages")
    op.drop_column("messages", "sequence")
