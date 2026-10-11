"""Image validation and private storage; no database, network or real AWS."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.core import storage
from app.core.errors import AppError
from app.models import TicketStatus, UserRole
from app.services import attachments


def image_bytes(format="PNG"):
    output = BytesIO()
    Image.new("RGB", (8, 6), "blue").save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize(
    "format,mime,extension",
    [
        ("JPEG", "image/jpeg", "jpg"),
        ("PNG", "image/png", "png"),
        ("WEBP", "image/webp", "webp"),
    ],
)
def test_images_are_canonicalized_without_trailing_payload(format, mime, extension):
    result, actual_mime, actual_extension, width, height = attachments._validate_image(
        image_bytes(format) + b"private trailing payload",
        mime,
    )
    assert (actual_mime, actual_extension, width, height) == (mime, extension, 8, 6)
    assert b"private trailing payload" not in result
    with Image.open(BytesIO(result)) as image:
        image.load()
        assert image.format == format


@pytest.mark.parametrize(
    "content,mime",
    [
        (b"", "image/png"),
        (b"malformed", "image/jpeg"),
        (b"<svg xmlns='http://www.w3.org/2000/svg' />", "image/svg+xml"),
        (image_bytes(), "image/jpeg"),
        (image_bytes()[:20], "image/png"),
        (image_bytes(), None),
    ],
)
def test_invalid_image_and_mime_are_rejected(content, mime):
    with pytest.raises(AppError) as error:
        attachments._validate_image(content, mime)
    assert error.value.status_code == 422
    assert error.value.code == "INVALID_IMAGE"


def test_local_storage_private_roundtrip_and_exclusive_write(tmp_path):
    local = storage.LocalStorage(tmp_path / "uploads")
    key = "a" * 32 + ".png"
    content = image_bytes()
    local.put(key, content, "image/png")
    assert local.get(key) == content
    assert (local.root / key).stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        local.put(key, b"overwrite", "image/png")
    assert local.get(key) == content
    local.delete(key)
    local.delete(key)
    assert not (local.root / key).exists()


@pytest.mark.parametrize(
    "key",
    [
        "../secret.png",
        "/secret.png",
        "a/b.png",
        "\\secret",
        "invalid.png",
        "a" * 32 + ".svg",
    ],
)
def test_local_storage_rejects_untrusted_keys(tmp_path, key):
    local = storage.LocalStorage(tmp_path)
    for operation in [
        lambda: local.put(key, b"data", "image/png"),
        lambda: local.get(key),
        lambda: local.delete(key),
    ]:
        with pytest.raises(ValueError):
            operation()


def test_local_storage_rejects_symlink_without_exposing_target(tmp_path):
    target = tmp_path / "private"
    target.write_bytes(b"private")
    key = "b" * 32 + ".png"
    (tmp_path / key).symlink_to(target)
    local = storage.LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        local.get(key)
    with pytest.raises(ValueError):
        local.delete(key)
    assert target.read_bytes() == b"private"


def test_s3_uses_private_conditional_objects_and_closes_stream(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        storage,
        "get_settings",
        lambda: SimpleNamespace(
            aws_region="test-region",
            aws_bucket_name="test-bucket",
            aws_access_key_id=None,
            aws_secret_access_key=None,
        ),
    )
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(storage.boto3, "client", factory)
    s3 = storage.S3Storage()
    key, content = "private/" + "c" * 32 + ".png", image_bytes()
    s3.put(key, content, "image/png")
    client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key=key,
        Body=content,
        ContentType="image/png",
        IfNoneMatch="*",
    )
    stream = MagicMock()
    stream.read.return_value = content
    client.get_object.return_value = {"Body": stream}
    assert s3.get(key) == content
    stream.read.assert_called_once_with(storage.MAX_IMAGE_BYTES + 1)
    stream.close.assert_called_once()
    s3.delete(key)
    client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=key)
    client.put_object.side_effect = RuntimeError("mock storage unavailable")
    with pytest.raises(RuntimeError):
        s3.put(key, content, "image/png")
    stream.read.return_value = b""
    with pytest.raises(ValueError):
        s3.get(key)
    assert stream.close.call_count == 2
    factory.assert_called_once_with("s3", region_name="test-region")


def upload(content):
    return UploadFile(
        filename="untrusted.png",
        file=BytesIO(content),
        headers=Headers({"content-type": "image/png"}),
    )


@pytest.mark.parametrize(
    "role,status,expected",
    [
        (UserRole.ADMIN, TicketStatus.OPEN, 403),
        (UserRole.CUSTOMER, TicketStatus.CLOSED, 409),
    ],
)
def test_upload_denied_before_read_or_storage(monkeypatch, role, status, expected):
    monkeypatch.setattr(
        attachments,
        "get_authorized_ticket",
        lambda *args: SimpleNamespace(status=status),
    )
    file = MagicMock()
    get_storage = MagicMock()
    monkeypatch.setattr(attachments, "get_storage", get_storage)
    with pytest.raises(AppError) as error:
        attachments.create_image_message(
            MagicMock(),
            MagicMock(),
            None,
            SimpleNamespace(role=role),
            SimpleNamespace(file=file),
            "",
        )
    assert error.value.status_code == expected
    file.read.assert_not_called()
    get_storage.assert_not_called()


def test_oversized_upload_is_rejected_before_storage(monkeypatch):
    monkeypatch.setattr(
        attachments,
        "get_authorized_ticket",
        lambda *args: SimpleNamespace(status=TicketStatus.OPEN),
    )
    store = MagicMock()
    monkeypatch.setattr(attachments, "get_storage", store)
    with pytest.raises(AppError) as error:
        attachments.create_image_message(
            MagicMock(),
            MagicMock(),
            None,
            SimpleNamespace(role=UserRole.CUSTOMER),
            upload(b"x" * (storage.MAX_IMAGE_BYTES + 1)),
            "",
        )
    assert error.value.status_code == 413
    store.assert_not_called()


@pytest.mark.parametrize(
    "committed,verification_fails,delete_expected",
    [
        (None, False, True),
        ("committed-id", False, False),
        (None, True, False),
    ],
)
def test_database_failure_cleans_only_proven_uncommitted_files(
    monkeypatch, committed, verification_fails, delete_expected
):
    monkeypatch.setattr(
        attachments,
        "get_authorized_ticket",
        lambda *args: SimpleNamespace(status=TicketStatus.OPEN),
    )
    monkeypatch.setattr(
        attachments, "get_settings", lambda: SimpleNamespace(storage_provider="local")
    )
    store = MagicMock()
    monkeypatch.setattr(attachments, "get_storage", lambda provider: store)
    monkeypatch.setattr(
        attachments,
        "create_message",
        MagicMock(side_effect=RuntimeError("commit failed")),
    )
    verification = MagicMock()
    verification.__enter__.return_value = verification
    verification.scalar.return_value = committed
    if verification_fails:
        verification.scalar.side_effect = RuntimeError("verification unavailable")
    with pytest.raises(RuntimeError, match="commit failed"):
        attachments.create_image_message(
            MagicMock(),
            lambda: verification,
            None,
            SimpleNamespace(role=UserRole.CUSTOMER),
            upload(image_bytes()),
            "caption",
        )
    store.put.assert_called_once()
    assert store.delete.called is delete_expected
    if delete_expected:
        assert store.delete.call_args.args[0] == store.put.call_args.args[0]


def test_storage_failure_does_not_attempt_database_write(monkeypatch):
    monkeypatch.setattr(
        attachments,
        "get_authorized_ticket",
        lambda *args: SimpleNamespace(status=TicketStatus.OPEN),
    )
    monkeypatch.setattr(
        attachments, "get_settings", lambda: SimpleNamespace(storage_provider="local")
    )
    store = MagicMock()
    store.put.side_effect = RuntimeError("storage failed")
    monkeypatch.setattr(attachments, "get_storage", lambda provider: store)
    create = MagicMock()
    monkeypatch.setattr(attachments, "create_message", create)
    with pytest.raises(AppError) as error:
        attachments.create_image_message(
            MagicMock(),
            MagicMock(),
            None,
            SimpleNamespace(role=UserRole.CUSTOMER),
            upload(image_bytes()),
            "caption",
        )
    assert error.value.status_code == 503
    create.assert_not_called()
