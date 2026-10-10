"""Trusted server event broadcasting helpers."""

import uuid
from datetime import datetime

from app.models import TicketStatus
from app.schemas.message import (
    TicketStatusChangedData,
    TicketStatusChangedEvent,
)
from app.websocket.manager import connection_manager


async def broadcast_ticket_status_changed(
    ticket_id: uuid.UUID,
    status: TicketStatus,
    updated_at: datetime,
) -> None:
    event = TicketStatusChangedEvent(
        data=TicketStatusChangedData(
            ticket_id=ticket_id,
            status=status,
            updated_at=updated_at,
        )
    )
    await connection_manager.broadcast(ticket_id, event.model_dump(mode="json"))
