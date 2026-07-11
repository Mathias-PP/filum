from __future__ import annotations

import asyncio

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
    # PIL rendering + PNG encode is CPU-bound sync work — keep it off the loop.
    png = await asyncio.to_thread(generate_og_image, title, creator)
    return Response(
        content=png,
        media_type="image/png",
        # OG images are immutable for a given (title, creator) — let crawlers
        # and CDNs cache them instead of re-rendering on every share.
        headers={"Cache-Control": "public, max-age=86400"},
    )
