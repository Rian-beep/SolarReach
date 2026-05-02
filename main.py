from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from voice_service.disclosure_check import check_disclosure
from voice_service.routers.voice import router as voice_router

check_disclosure()

app = FastAPI(title="SolarReach Voice Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
