from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.db.database import get_db
from app.services.auth import AuthService
from app.schemas.auth import LoginResponse
from app.schemas.user import UserResponse
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


@router.get("/login")
async def login():
    google_client_id = "your_google_client_id"
    redirect_uri = "http://localhost:8000/api/v1/auth/google/callback"
    return RedirectResponse(
        url=f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={google_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=email%20profile&"
        f"state=random_state_string"
    )


@router.get("/google/callback")
async def google_callback(code: str | None = None, db: AsyncSession = Depends(get_db)):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    auth_service = AuthService(db)
    return {"message": "OAuth callback - implement Google token exchange", "code": code}


@router.post("/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("filum_session")
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
