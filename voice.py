import os
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/voice", tags=["voice"])

ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_AGENT_ID = os.environ["ELEVENLABS_AGENT_ID"]
MONGO_URI = os.environ["MONGO_URI"]

_mongo_client: AsyncIOMotorClient | None = None


def get_db():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(MONGO_URI)
    return _mongo_client.get_default_database()


class TranscriptChunk(BaseModel):
    lead_id: str
    role: str
    text: str


@router.get("/signed-url")
async def get_signed_url():
    url = "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url"
    params = {"agent_id": ELEVENLABS_AGENT_ID}
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers, timeout=10)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    return {"signed_url": data.get("signed_url")}


@router.post("/transcript")
async def save_transcript(chunk: TranscriptChunk):
    db = get_db()
    doc = {
        "ts": datetime.now(timezone.utc),
        "meta": {"lead_id": chunk.lead_id, "role": chunk.role},
        "text": chunk.text,
    }
    await db["calls_ts"].insert_one(doc)
    return {"ok": True}
