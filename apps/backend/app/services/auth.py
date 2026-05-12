from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import get_settings
from app.models.user import User
from app.crypto.keygen import KeyManager

settings = get_settings()
logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
SESSION_EXPIRE_HOURS = 24


class AuthService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._key_manager = KeyManager(settings.master_encryption_key)

    def create_session(self, user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRE_HOURS)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.session_secret, algorithm=ALGORITHM)

    async def get_current_user(self, request: Request) -> User | None:
        token = request.cookies.get("filum_session")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
            user_id = UUID(payload["sub"])
            result = await self._db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and not user.deleted_at:
                return user
        except (JWTError, ValueError, KeyError) as e:
            logger.warning(f"Session validation failed: {e}")

        return None

    async def get_user_by_google_id(self, google_id: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.google_id == google_id)
        )
        return result.scalar_one_or_none()

    async def create_user_from_google(
        self,
        email: str,
        google_id: str,
        username: str,
        display_name: str | None = None,
    ) -> User:
        private_pem, public_pem, public_key_raw = KeyManager.generate_keypair()
        encrypted_private = self._key_manager.encrypt_private_key(private_pem)

        user = User(
            email=email,
            google_id=google_id,
            username=username,
            display_name=display_name or username,
            public_key=public_key_raw,
            encrypted_private_key=encrypted_private,
            is_verified=True,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user
