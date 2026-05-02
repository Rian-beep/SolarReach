"""POST /admin/client/<slug> — update client doc."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db

router = APIRouter()


@router.post("/admin/client/{slug}")
async def upsert_client(
    slug: str,
    body: dict = Body(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = {**body, "_id": slug}
    await db.clients.update_one({"_id": slug}, {"$set": doc}, upsert=True)
    return doc
