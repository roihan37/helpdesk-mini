import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.message import Message


class MessageAttachment(Base):
    __tablename__ = "message_attachments"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_message_attachments_message_id"),
        UniqueConstraint("storage_key", name="uq_message_attachments_storage_key"),
        CheckConstraint("storage_provider IN ('local', 's3')", name="ck_attachment_provider"),
        CheckConstraint("mime_type IN ('image/jpeg', 'image/png', 'image/webp')", name="ck_attachment_mime"),
        CheckConstraint("byte_size > 0 AND byte_size <= 5242880", name="ck_attachment_size"),
        CheckConstraint("width > 0 AND height > 0", name="ck_attachment_dimensions"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", name="fk_attachment_message"), nullable=False
    )
    storage_provider: Mapped[str] = mapped_column(String(5), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(10), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    message: Mapped["Message"] = relationship(back_populates="attachment")
