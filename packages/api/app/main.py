"""FastAPI application entrypoint.

Lifespan boots a Mongo client and pings it (best-effort — graceful degrade).
Routers mount at root per CONTRACTS § 2.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.routers import health as health_router
from app.routers import admin as admin_router
from app.routers import financial as financial_router
from app.routers import flux as flux_router
from app.routers import inbound as inbound_router
from app.routers import leads as leads_router
from app.routers import panels as panels_router
from app.routers import realapi as realapi_router
from app.routers import scan as scan_router
from app.routers import voice as voice_router

log = logging.getLogger("solarreach.api")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client: AsyncIOMotorClient | None = None
    try:
        client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
        try:
            await client.admin.command("ping")
            log.info("mongo connected: %s", settings.mongo_db)
            # Verify indexes — best-effort, log only.
            await _verify_indexes(client[settings.mongo_db])
        except Exception as e:  # noqa: BLE001
            log.warning("mongo unreachable at startup: %s", e)
        app.state.mongo_client = client
        yield
    finally:
        if client is not None:
            client.close()


async def _verify_indexes(db) -> None:
    # We log presence only; A1/infra owns index creation.
    try:
        info = await db.leads.index_information()
        log.info("leads indexes: %s", list(info.keys()))
    except Exception as e:  # noqa: BLE001
        log.info("leads index check skipped: %s", e)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SolarReach API",
        version="0.1.0",
        description="A2 API gateway. See docs/CONTRACTS.md.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router.router, tags=["meta"])
    app.include_router(scan_router.router, tags=["scan"])
    app.include_router(leads_router.router, tags=["leads"])
    app.include_router(flux_router.router, tags=["flux"])
    app.include_router(panels_router.router, tags=["panels"])
    app.include_router(voice_router.router, tags=["voice"])
    app.include_router(admin_router.router, tags=["admin"])
    app.include_router(financial_router.router, tags=["financial"])
    app.include_router(inbound_router.router, tags=["inbound"])
    app.include_router(realapi_router.router, tags=["realapi"])
    # Static (generated decks/pdfs)
    static_dir = Path("/tmp/decks")
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/pitches", StaticFiles(directory=str(static_dir)), name="pitches")
    # Flux PNGs (Solar API → reproject → inferno colormap, see routers/flux.py).
    flux_dir = Path("/tmp/flux")
    flux_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/flux", StaticFiles(directory=str(flux_dir)), name="flux")
    return app


app = create_app()
