"""Add private image attachment metadata.

Revision ID: c7e4a682d193
Revises: b5c8d41e92af
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "c7e4a682d193"
down_revision = "b5c8d41e92af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_provider", sa.String(5), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(10), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], name="fk_attachment_message"),
        sa.UniqueConstraint("message_id", name="uq_message_attachments_message_id"),
        sa.UniqueConstraint("storage_key", name="uq_message_attachments_storage_key"),
        sa.CheckConstraint("storage_provider IN ('local', 's3')", name="ck_attachment_provider"),
        sa.CheckConstraint("mime_type IN ('image/jpeg', 'image/png', 'image/webp')", name="ck_attachment_mime"),
        sa.CheckConstraint("byte_size > 0 AND byte_size <= 5242880", name="ck_attachment_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_attachment_dimensions"),
    )


def downgrade() -> None:
    op.drop_table("message_attachments")
