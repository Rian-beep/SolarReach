"""Settings via pydantic-settings.

All values readable from env. Missing values do not crash app: endpoints
guard themselves and return clear errors / mock responses where required.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Mongo
    mongo_uri: str = Field(default="mongodb://localhost:27017/?authSource=admin")
    mongo_db: str = Field(default="solarreach")

    # Anthropic
    anthropic_api_key: str = Field(default="")

    # Google
    google_maps_api_key: str = Field(default="")

    # ElevenLabs
    elevenlabs_api_key: str = Field(default="")
    elevenlabs_agent_id: str = Field(default="")

    # Companies House
    companies_house_api_key: str = Field(default="")

    # Compliance / cost
    solarreach_live_outbound: bool = Field(default=False)
    roi_gate_threshold: int = Field(default=70)
    session_budget_gbp: float = Field(default=1.00)

    # Redis (optional)
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Static / outbox
    outbox_dir: str = Field(default="outbox")
    static_dir: str = Field(default="static")

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
