"""Application API router."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.users import router as users_router
from app.api.routes.websocket import router as websocket_router

api_router = APIRouter(
    routes=[
        *auth_router.routes,
        *users_router.routes,
        *tickets_router.routes,
        *websocket_router.routes,
    ]
)
