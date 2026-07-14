from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.waitlist_entry import WaitlistEntry
from app.schemas.waitlist import WaitlistCreate, WaitlistResponse

router = APIRouter()


@router.post("/waitlist", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def join_waitlist(
    request: Request,
    payload: WaitlistCreate,
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.lower().strip()
    existing = await db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == email))
    if existing is None:
        db.add(WaitlistEntry(email=email, context=payload.context))
        await db.commit()
    # Toujours 201 : ne révèle pas si l'email était déjà inscrit (anti-énumération)
    return WaitlistResponse()
