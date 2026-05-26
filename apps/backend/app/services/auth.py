from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
SESSION_EXPIRE_HOURS = 24

# Matches the slug pattern used by the user schema. Lowercase alphanumeric +
# hyphens, must start with alphanumeric, length 3..81. We intentionally do not
# couple to schemas.user.SlugPattern to keep the service layer independent.
_VALID_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LEN = 80
_MAX_COLLISION_ATTEMPTS = 50


def _slugify_username(raw: str) -> str:
    """Coerce an arbitrary string (typically an email's local part) into a
    valid username slug. Lowercase, replace runs of non-alphanumerics with a
    single hyphen, trim leading/trailing hyphens, truncate to 80 chars.

    Returns "" if nothing usable remains. Callers must fall back to a
    deterministic name (e.g. derived from google_id) in that case.

    Examples:
      "mathias.pinault"   -> "mathias-pinault"
      "john+tag"          -> "john-tag"
      "Léa-C"             -> "l-a-c"   (after lower(), the accent is dropped)
      "_underscored__"    -> "underscored"
      "ab"                -> ""        (too short to be a valid slug)
    """
    s = raw.strip().lower()
    s = _NON_SLUG_CHARS.sub("-", s).strip("-")
    s = s[:_MAX_SLUG_LEN]
    return s if _VALID_SLUG.match(s) else ""


class AuthService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._key_manager = KeyManager(settings.master_encryption_key)

    def create_session(self, user_id: UUID) -> str:
        expire = datetime.now(UTC) + timedelta(hours=SESSION_EXPIRE_HOURS)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.now(UTC),
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
        except (jwt.InvalidTokenError, ValueError, KeyError) as e:
            logger.warning(f"Session validation failed: {e}")

        return None

    async def get_user_by_google_id(self, google_id: str) -> User | None:
        result = await self._db.execute(select(User).where(User.google_id == google_id))
        return result.scalar_one_or_none()

    async def _resolve_available_username(self, preferred: str, google_id: str) -> str:
        """Pick a username that does not collide with an existing row.

        Slugifies the preferred input. If that slug is already taken (another
        Google account whose email local part produces the same slug), append
        a numeric suffix until we find a free one. Falls back to a
        google_id-derived name if even that fails (extremely unlikely, but
        guarantees the OAuth flow never raises an IntegrityError).
        """
        base = _slugify_username(preferred)
        if not base:
            # Email local part was unusable (e.g. only special chars after
            # lowercasing). Use the Google subject as a deterministic fallback.
            base = f"user-{google_id[:12]}"

        # Fetch all usernames that share this base or start with `base-` to
        # avoid a query-per-attempt. For the realistic case (a few homonyms)
        # this is a single round-trip.
        result = await self._db.execute(
            select(User.username).where((User.username == base) | (User.username.like(f"{base}-%")))
        )
        taken = {row[0] for row in result.all()}
        if base not in taken:
            return base
        for n in range(2, _MAX_COLLISION_ATTEMPTS + 2):
            candidate = f"{base}-{n}"
            if len(candidate) > _MAX_SLUG_LEN:
                break
            if candidate not in taken:
                return candidate
        # Pathological case: 50+ homonyms. Append the google_id tail.
        return f"{base[: _MAX_SLUG_LEN - 13]}-{google_id[:12]}"

    async def create_user_from_google(
        self,
        email: str,
        google_id: str,
        username: str,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        """Create a new user from a Google OAuth profile.

        ``username`` is treated as a *preferred* base name (typically the
        email's local part). It is slugified to URL-safe characters and any
        collision with an existing user is resolved by appending a numeric
        suffix, so this method never raises an IntegrityError on a clean
        unique-username constraint.

        Email uniqueness is still enforced at the DB level; conflicts there
        would indicate that the same physical email has been linked to two
        different Google accounts, which we surface as the original
        IntegrityError (left to the caller).
        """
        private_pem, public_pem, public_key_raw = KeyManager.generate_keypair()
        encrypted_private = self._key_manager.encrypt_private_key(private_pem)

        resolved_username = await self._resolve_available_username(username, google_id)

        user = User(
            email=email,
            google_id=google_id,
            username=resolved_username,
            display_name=display_name or resolved_username,
            avatar_url=avatar_url,
            public_key=public_key_raw,
            encrypted_private_key=encrypted_private,
            is_verified=True,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user
