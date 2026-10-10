import uuid

import pytest
from pydantic import ValidationError

from app.schemas.message import MessageSendEvent


def test_message_send_event_trims_and_accepts_only_documented_shape() -> None:
    event = MessageSendEvent.model_validate(
        {"type": "message.send", "body": "  Please help  "}
    )

    assert event.body == "Please help"
    with pytest.raises(ValidationError):
        MessageSendEvent.model_validate(
            {
                "type": "message.send",
                "body": "forged",
                "sender_id": str(uuid.uuid4()),
            }
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "unsupported", "body": "hello"},
        {"type": "message.send", "body": "   "},
        {"type": "message.send", "body": "x" * 5001},
    ],
)
def test_message_send_event_rejects_invalid_input(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        MessageSendEvent.model_validate(payload)
