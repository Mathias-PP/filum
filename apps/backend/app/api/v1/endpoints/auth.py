from __future__ import annotations

import secrets

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from httpx import HTTPError
from jwt import PyJWKClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from app.core.config import get_settings
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.auth import AuthService

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "filum_oauth_state"
STATE_EXPIRE_MINUTES = 10
GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_current_user(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


def _session_cookie_config() -> dict:
    if settings.debug:
        return {"samesite": "lax", "secure": False}
    return {"samesite": "none", "secure": True}


def _set_session_cookie(response: Response, token: str) -> None:
    cookie_config = _session_cookie_config()
    response.set_cookie(
        key="filum_session",
        value=token,
        httponly=True,
        max_age=86400,
        **cookie_config,
    )


def _delete_session_cookie(response: Response) -> None:
    cookie_config = _session_cookie_config()
    response.delete_cookie(
        key="filum_session",
        path="/",
        **{k: v for k, v in cookie_config.items() if k != "max_age"},
    )


def _set_state_cookie(response: Response, state: str) -> None:
    cookie_config = _session_cookie_config()
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        httponly=True,
        max_age=STATE_EXPIRE_MINUTES * 60,
        **cookie_config,
    )


def _delete_state_cookie(response: Response) -> None:
    response.delete_cookie(key=STATE_COOKIE, path="/")


def _generate_state() -> str:
    return secrets.token_urlsafe(32)


@router.get("/google/login")
async def google_login(request: Request):
    if not settings.google_client_id:
        raise HTTPException(
            status_code=500,
            detail={"code": "configuration_error", "message": "Google OAuth not configured"},
        )

    state = _generate_state()
    redirect_uri = f"{settings.backend_base_url}/api/v1/auth/google/callback"

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"state={state}&"
        f"access_type=offline"
    )

    response = RedirectResponse(url=auth_url, status_code=302)
    _set_state_cookie(response, state)
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise HTTPException(
            status_code=400,
            detail={"code": "oauth_error", "message": f"OAuth error: {error}"},
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=500,
            detail={"code": "configuration_error", "message": "Google OAuth not configured"},
        )

    # Verify state token (CSRF protection)
    stored_state = request.cookies.get(STATE_COOKIE)
    if not stored_state or not state or stored_state != state:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_state", "message": "Invalid or missing state parameter"},
        )

    auth_service = AuthService(db)

    try:
        token_url = "https://oauth2.googleapis.com/token"
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                token_url,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": f"{settings.backend_base_url}/api/v1/auth/google/callback",
                    "grant_type": "authorization_code",
                },
            )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")

        token_data = token_response.json()
        id_token = token_data.get("id_token")
        if not id_token:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_id_token", "message": "No id_token in response"},
            )

        # Verify id_token signature via Google's JWKS
        try:
            jwks_client = PyJWKClient(GOOGLE_JWKS_URI)
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)
            google_info: dict = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.google_client_id,
                options={"verify_exp": True, "verify_iat": True},
            )
        except jwt.PyJWTError as e:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_id_token", "message": f"Failed to verify id_token: {e}"},
            ) from e

        # Verify issuer
        issuer = google_info.get("iss", "")
        if issuer not in ("https://accounts.google.com", "accounts.google.com"):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_issuer", "message": "Invalid token issuer"},
            )

        google_sub: str = google_info["sub"]
        email: str | None = google_info.get("email")
        name: str | None = google_info.get("name")
        picture: str | None = google_info.get("picture")

        if not email:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_email", "message": "Email not provided by Google"},
            )

        # Find or create user
        existing_user = await auth_service.get_user_by_google_id(google_sub)
        if existing_user:
            session_token = auth_service.create_session(existing_user.id)
            response = RedirectResponse(url=settings.frontend_base_url, status_code=303)
            _delete_state_cookie(response)
            _set_session_cookie(response, session_token)
            return response

        username = email.split("@")[0] if email else f"user_{google_sub[:8]}"
        user = await auth_service.create_user_from_google(
            email=email,
            google_id=google_sub,
            username=username,
            display_name=name or username,
            avatar_url=picture,
        )

        session_token = auth_service.create_session(user.id)
        response = RedirectResponse(url=settings.frontend_base_url, status_code=303)
        _delete_state_cookie(response)
        _set_session_cookie(response, session_token)
        return response

    except HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "oauth_error", "message": f"Failed to authenticate: {str(e)}"},
        ) from e


@router.post("/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    response = RedirectResponse(url="/", status_code=303)
    _delete_session_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
