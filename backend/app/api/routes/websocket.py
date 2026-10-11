"""Authenticated ticket-room WebSocket endpoint."""

import logging
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import require_roles, resolve_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_session_factory
from app.models import UserRole
from app.schemas.message import (
    MessageCreatedEvent,
    MessagePublic,
    MessageSendEvent,
    WebSocketErrorData,
    WebSocketErrorEvent,
)
from app.services.authorization import get_authorized_ticket
from app.services.messages import create_message
from app.websocket.events import broadcast_ticket_list_event
from app.websocket.manager import connection_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/tickets")
async def ticket_list_subscription(
    websocket: WebSocket,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> None:
    token = websocket.query_params.get("token")
    if token is None or not _origin_allowed(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        await run_in_threadpool(_authorize_list_connection, session_factory, token)
    except AppError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception:
        logger.exception("Ticket-list WebSocket handshake failed")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return
    await connection_manager.subscribe(websocket, token)
    try:
        # Server-to-client subscription only. No client-supplied scope or mutations.
        frame = await websocket.receive()
        if frame["type"] != "websocket.disconnect":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.unsubscribe(websocket)


def _authorize_list_connection(
    session_factory: sessionmaker[Session], token: str
) -> None:
    with session_factory() as db:
        current_user = resolve_current_user(token, db)
        require_roles(current_user, {UserRole.ADMIN, UserRole.AGENT, UserRole.CUSTOMER})


@router.websocket("/tickets/{ticket_id}")
async def ticket_chat(
    websocket: WebSocket,
    ticket_id: uuid.UUID,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> None:
    token = websocket.query_params.get("token")
    if token is None or not _origin_allowed(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        await run_in_threadpool(
            _authorize_connection, session_factory, token, ticket_id
        )
    except AppError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception:
        logger.exception("Unexpected WebSocket handshake failure")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    await connection_manager.connect(ticket_id, websocket)
    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except ValueError:
                await _send_error(
                    websocket,
                    "VALIDATION_ERROR",
                    "WebSocket event validation failed.",
                )
                continue

            try:
                event = MessageSendEvent.model_validate(payload)
            except ValidationError:
                await _send_error(
                    websocket,
                    "VALIDATION_ERROR",
                    "WebSocket event validation failed.",
                )
                continue

            try:
                message, business_id, customer_id, updated_at = await run_in_threadpool(
                    _persist_message,
                    session_factory,
                    token,
                    ticket_id,
                    event.body,
                )
            except AppError as error:
                if error.status_code in {401, 404}:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break
                if error.code == "TICKET_CLOSED":
                    await _send_error(
                        websocket,
                        "TICKET_CLOSED",
                        "This ticket no longer accepts messages.",
                    )
                else:
                    await _send_error(
                        websocket,
                        "FORBIDDEN",
                        "You are not allowed to send messages to this ticket.",
                    )
                continue
            except Exception:
                logger.exception("Unexpected WebSocket message failure")
                await _send_error(
                    websocket,
                    "INTERNAL_SERVER_ERROR",
                    "An unexpected error occurred.",
                )
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                break

            created = MessageCreatedEvent(data=message)
            await connection_manager.broadcast(
                ticket_id, created.model_dump(mode="json")
            )
            await broadcast_ticket_list_event(
                session_factory,
                "ticket.message_created",
                ticket_id,
                business_id,
                customer_id,
                updated_at,
            )
    finally:
        await connection_manager.disconnect(ticket_id, websocket)


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if origin is None:
        return False
    allowed = {str(value).rstrip("/") for value in get_settings().cors_origins}
    return origin.rstrip("/") in allowed


def _authorize_connection(
    session_factory: sessionmaker[Session],
    token: str,
    ticket_id: uuid.UUID,
) -> None:
    with session_factory() as db:
        current_user = resolve_current_user(token, db)
        get_authorized_ticket(db, ticket_id, current_user)


def _persist_message(
    session_factory: sessionmaker[Session],
    token: str,
    ticket_id: uuid.UUID,
    body: str,
) -> tuple[MessagePublic, uuid.UUID, uuid.UUID, datetime]:
    with session_factory() as db:
        current_user = resolve_current_user(token, db)
        ticket = get_authorized_ticket(db, ticket_id, current_user)
        message = create_message(db, ticket_id, current_user, body)
        return message, ticket.business_id, ticket.customer_id, ticket.updated_at


async def _send_error(
    websocket: WebSocket,
    code: str,
    message: str,
) -> None:
    event = WebSocketErrorEvent(
        data=WebSocketErrorData.model_validate({"code": code, "message": message})
    )
    await websocket.send_json(event.model_dump(mode="json"))
