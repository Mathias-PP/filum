from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.services.og_image import generate_og_image

router = APIRouter(tags=["og"])


@router.get("/og")
async def og_image(
    title: str = Query(..., description="Card title to show in the image"),
    creator: str | None = Query(None, description="Creator name"),
):
    if len(title) > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title too long")
    png = generate_og_image(title, creator)
    return Response(content=png, media_type="image/png")
