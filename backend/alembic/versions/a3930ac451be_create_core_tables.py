"""create_core_tables

Revision ID: a3930ac451be
Revises:
Create Date: 2026-10-09 17:11:14.656312
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3930ac451be"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_businesses_slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'agent', 'customer')",
            name="ck_users_role_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_users_business_id_businesses",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_business_id", "users", ["business_id"], unique=False)
    op.create_table(
        "tickets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("assigned_agent_id", sa.UUID(), nullable=True),
        sa.Column("subject", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="open", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_tickets_priority_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')",
            name="ck_tickets_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_agent_id"],
            ["users.id"],
            name="fk_tickets_assigned_agent_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_tickets_business_id_businesses",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            name="fk_tickets_customer_id_users",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tickets_business_id_status",
        "tickets",
        ["business_id", "status"],
        unique=False,
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["users.id"], name="fk_messages_sender_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_messages_ticket_id_tickets",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_ticket_id_created_at_id",
        "messages",
        ["ticket_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_messages_ticket_id_created_at_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_tickets_business_id_status", table_name="tickets")
    op.drop_table("tickets")
    op.drop_index("ix_users_business_id", table_name="users")
    op.drop_table("users")
    op.drop_table("businesses")
