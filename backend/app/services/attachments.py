"""Image validation and private, ticket-authorized attachment workflows."""

import logging
import uuid
import warnings
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import require_roles
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.storage import MAX_IMAGE_BYTES, get_storage
from app.models import Message, MessageAttachment, TicketStatus, User, UserRole
from app.schemas.message import MessagePublic
from app.services.authorization import get_authorized_ticket
from app.services.messages import create_message

logger = logging.getLogger(__name__)
_FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}


def _invalid_image() -> AppError:
    return AppError(422, "INVALID_IMAGE", "Upload a valid, non-animated JPEG, PNG or WebP image (up to 5 MB, 8192 pixels per side and 20 megapixels).")


def _validate_image(content: bytes, claimed_mime: str | None) -> tuple[bytes, str, str, int, int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                image_format = image.format
                if image_format not in _FORMATS:
                    raise _invalid_image()
                mime, extension = _FORMATS[image_format]
                width, height = image.size
                if claimed_mime != mime or not (0 < width <= 8192 and 0 < height <= 8192) or width * height > 20_000_000:
                    raise _invalid_image()
                if getattr(image, "is_animated", False):
                    raise _invalid_image()
                image.verify()
            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
                # Canonical encoding strips trailing payloads and EXIF/private metadata.
                pixels = decoded.convert("RGB" if image_format == "JPEG" else "RGBA")
                pixels.info.clear()
                output = BytesIO()
                pixels.save(output, format=image_format)
                normalized = output.getvalue()
                if len(normalized) > MAX_IMAGE_BYTES:
                    raise _invalid_image()
                return normalized, mime, extension, width, height
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _invalid_image() from None


def create_image_message(
    db: Session, session_factory: sessionmaker[Session], ticket_id: uuid.UUID,
    current_user: User, upload: UploadFile, caption: str,
) -> MessagePublic:
    ticket = get_authorized_ticket(db, ticket_id, current_user)
    require_roles(current_user, {UserRole.AGENT, UserRole.CUSTOMER})
    if ticket.status == TicketStatus.CLOSED:
        raise AppError(409, "TICKET_CLOSED", "This ticket no longer accepts messages.")
    try:
        content = upload.file.read(MAX_IMAGE_BYTES + 1)
    finally:
        upload.file.close()
    if len(content) > MAX_IMAGE_BYTES:
        raise AppError(413, "IMAGE_TOO_LARGE", "Images must not exceed 5 MB.")
    normalized, mime, extension, width, height = _validate_image(content, upload.content_type)
    settings = get_settings()
    key = f"{uuid.uuid4().hex}.{extension}"
    if settings.storage_provider == "s3":
        prefix = settings.aws_s3_prefix.rstrip("/")
        key = f"{prefix}/{key}" if prefix else key
    attachment_id = uuid.uuid4()
    attachment = MessageAttachment(
        id=attachment_id, storage_provider=settings.storage_provider, storage_key=key,
        mime_type=mime, byte_size=len(normalized), width=width, height=height,
    )
    try:
        storage = get_storage(settings.storage_provider)
        storage.put(key, normalized, mime)
    except Exception:
        # An S3 timeout may mean the write succeeded. Do not blindly delete a
        # potentially existing object after an uncertain/conditional write.
        logger.warning("Attachment storage failure may require orphan reconciliation")
        raise AppError(503, "ATTACHMENT_STORAGE_UNAVAILABLE", "Image storage is unavailable. Try again later.") from None
    try:
        # Expire the previously inspected row, so the locked authorization read
        # observes a concurrent close before committing the message.
        db.expire(ticket)
        return create_message(db, ticket_id, current_user, caption.strip(), attachment)
    except Exception:
        # Commit failures can be ambiguous. Delete only after a separate session
        # proves this attachment was not committed; otherwise retain for reconciliation.
        try:
            with session_factory() as verification_db:
                committed = verification_db.scalar(select(MessageAttachment.id).where(MessageAttachment.id == attachment_id))
            if committed is None:
                storage.delete(key)
        except Exception:
            logger.warning("Attachment cleanup requires administrator reconciliation")
        raise


def retrieve_image(db: Session, ticket_id: uuid.UUID, attachment_id: uuid.UUID, current_user: User) -> tuple[bytes, str]:
    get_authorized_ticket(db, ticket_id, current_user)
    attachment = db.scalar(
        select(MessageAttachment).join(Message)
        .where(Message.ticket_id == ticket_id, MessageAttachment.id == attachment_id)
    )
    if attachment is None:
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "Attachment not found.")
    try:
        content = get_storage(attachment.storage_provider).get(attachment.storage_key)
    except Exception:
        raise AppError(503, "ATTACHMENT_STORAGE_UNAVAILABLE", "Image storage is unavailable. Try again later.") from None
    return content, attachment.mime_type
