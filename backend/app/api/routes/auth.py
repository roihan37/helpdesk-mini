"""Authentication and registration endpoints."""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    AccessToken,
    AccessTokenResponse,
    BusinessPublic,
    BusinessSummary,
    CurrentUser,
    CurrentUserResponse,
    LoginRequest,
    RegisterBusinessRequest,
    RegistrationData,
    RegistrationResponse,
    TokenPair,
    TokenPairResponse,
)
from app.schemas.common import ErrorResponse
from app.schemas.user import UserPublic
from app.services.auth import authenticate_user, refresh_access_token, register_business

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path="/auth/refresh",
    )


def _validate_refresh_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        return
    allowed_origins = {str(item).rstrip("/") for item in settings.cors_origins}
    if origin.rstrip("/") not in allowed_origins:
        raise AppError(
            status_code=403,
            code="FORBIDDEN",
            message="Request origin is not allowed.",
        )


@router.post(
    "/register-business",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def register_business_endpoint(
    payload: RegisterBusinessRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegistrationResponse:
    business, admin = register_business(db, payload)
    return RegistrationResponse(
        data=RegistrationData(
            business=BusinessPublic.model_validate(business),
            admin=UserPublic.model_validate(admin),
        )
    )


@router.post(
    "/login",
    response_model=TokenPairResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPairResponse:
    tokens = authenticate_user(db, str(payload.email), payload.password)
    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenPairResponse(
        data=TokenPair(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def refresh(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> AccessTokenResponse:
    _validate_refresh_origin(request)
    if refresh_token is None:
        raise AppError(
            status_code=401,
            code="AUTH_TOKEN_INVALID",
            message="Refresh token cookie is required.",
        )
    access_token = refresh_access_token(db, refresh_token)
    return AccessTokenResponse(
        data=AccessToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    responses={401: {"model": ErrorResponse}},
)
def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        data=CurrentUser(
            id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            role=cast(Literal["admin", "agent", "customer"], current_user.role),
            business=BusinessSummary.model_validate(current_user.business),
        )
    )
