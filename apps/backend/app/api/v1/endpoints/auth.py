from __future__ import annotations

import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from app.db.database import get_db
from app.core.config import get_settings
from app.services.auth import AuthService
from app.schemas.user import UserResponse
from app.models.user import User

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_current_user(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


@router.get("/login")
async def login(request: Request):
    if not settings.google_client_id:
        raise HTTPException(
            status_code=500,
            detail={"code": "configuration_error", "message": "Google OAuth not configured"},
        )

    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    redirect_uri = f"{settings.backend_base_url}/api/v1/auth/google/callback"

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=email%20profile&"
        f"state={state}&"
        f"access_type=offline"
    )

    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
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

    auth_service = AuthService(db)

    try:
        token_url = "https://oauth2.googleapis.com/token"
        import httpx
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
        access_token = token_data.get("access_token")

        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        async with httpx.AsyncClient() as client:
            userinfo_response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        user_info = userinfo_response.json()
        email = user_info.get("email")
        google_id = user_info.get("id")
        name = user_info.get("name", "")

        existing_user = await auth_service.get_user_by_google_id(google_id)
        if existing_user:
            session_token = auth_service.create_session(existing_user.id)
            response = RedirectResponse(url=settings.frontend_base_url, status_code=303)
            response.set_cookie(
                key="filum_session",
                value=session_token,
                httponly=True,
                secure=True,
                samesite="lax",
            )
            return response

        username = email.split("@")[0] if email else f"user_{google_id[:8]}"
        user = await auth_service.create_user_from_google(
            email=email,
            google_id=google_id,
            username=username,
            display_name=name,
        )

        session_token = auth_service.create_session(user.id)
        response = RedirectResponse(url=settings.frontend_base_url, status_code=303)
        response.set_cookie(
            key="filum_session",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return response

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "oauth_error", "message": f"Failed to authenticate: {str(e)}"},
        )


@router.post("/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("filum_session", path="/")
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
