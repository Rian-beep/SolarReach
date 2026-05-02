"""Pydantic v2 models mirroring `packages/shared/schemas/*.schema.json`.

Note: shapes match the JSON Schemas. We use `model_config = ConfigDict(extra="allow")`
to allow upstream evolution without breaking unmarshalling, while still validating known fields.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- GeoJSON helpers ----------

class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: Literal["Point"] = "Point"
    coordinates: list[float]  # [lng, lat] EPSG:4326


class GeoPolygon(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]
    source: Literal["inspire_index_polygon", "solar_api_bbox", "synthesized"] = (
        "synthesized"
    )
    inspire_id: Optional[str] = None
    area_m2_approx: Optional[float] = None


# ---------- leads ----------

class LeadGeo(BaseModel):
    model_config = ConfigDict(extra="allow")
    point: GeoPoint


class LeadScores(BaseModel):
    model_config = ConfigDict(extra="allow")
    solar_roi: float = 0.0
    financial_health: float = 0.0
    social_impact: float = 0.0
    composite_score: int = 0
    scored_at: Optional[str] = None


class LeadOwner(BaseModel):
    model_config = ConfigDict(extra="allow")
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    source: Literal["ccod", "ocod", "synthesized"] = "synthesized"


class LeadDecisionMaker(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: Optional[str] = None
    role: Optional[str] = None
    confidence: float = 0.0
    rationale: Optional[str] = None


class LeadPanel(BaseModel):
    model_config = ConfigDict(extra="allow")
    corners: list[list[float]]
    tilt: float
    azimuth: float
    kwh_yr: float


class LeadPanelLayout(BaseModel):
    model_config = ConfigDict(extra="allow")
    panels: list[LeadPanel] = Field(default_factory=list)
    panel_count: int = 0
    annual_kwh: float = 0.0
    clipped_at: Optional[str] = None
    clip_method: Optional[str] = None


class LeadFluxOverlay(BaseModel):
    model_config = ConfigDict(extra="allow")
    url: str
    bbox: list[float]
    vmin: float
    vmax: float
    cached_at: Optional[str] = None


class LeadFinancial(BaseModel):
    model_config = ConfigDict(extra="allow")
    capex_gbp: float = 0.0
    annual_saving_gbp: float = 0.0
    payback_years: float = 0.0
    npv_25yr_gbp: float = 0.0


PremisesType = Literal[
    "office", "leisure", "warehouse", "retail", "education", "residential", "mixed"
]


class Lead(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str = Field(alias="_id")
    client_id: str
    address: str
    postcode: str
    borough: Optional[str] = None
    premises_type: PremisesType
    geo: LeadGeo
    rooftop_polygon: Optional[GeoPolygon] = None
    scores: Optional[LeadScores] = None
    owner: Optional[LeadOwner] = None
    decision_maker: Optional[LeadDecisionMaker] = None
    panel_layout: Optional[LeadPanelLayout] = None
    flux_overlay: Optional[LeadFluxOverlay] = None
    financial: Optional[LeadFinancial] = None
    created_at: str
    updated_at: Optional[str] = None


# ---------- companies ----------

class Company(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str = Field(alias="_id")
    name: str
    ch_number: Optional[str] = None
    registered_address: Optional[str] = None
    title_number: Optional[str] = None
    ccod_proprietor_name: Optional[str] = None
    property_address: Optional[str] = None
    directors: list[str] = Field(default_factory=list)
    embedding: Optional[list[float]] = None


# ---------- directors ----------

class Director(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str = Field(alias="_id")
    company_id: str
    name: str
    name_display: Optional[str] = None
    role: Optional[str] = None
    appointed_on: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    ch_officer_id: Optional[str] = None


# ---------- inspire_polygons ----------

class InspirePolygonDoc(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str = Field(alias="_id")
    inspire_id: str
    borough: Optional[str] = None
    polygon: GeoPolygon
    area_m2_approx: float
    centroid: GeoPoint


# ---------- clients ----------

class ClientBranding(BaseModel):
    model_config = ConfigDict(extra="allow")
    primary: Optional[str] = None
    logo_url: Optional[str] = None


class ClientPricing(BaseModel):
    model_config = ConfigDict(extra="allow")
    panel_unit_gbp: float = 850.0
    install_per_kw_gbp: float = 180.0


class Client(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str = Field(alias="_id")
    name: str
    branding: ClientBranding = Field(default_factory=ClientBranding)
    pricing: ClientPricing = Field(default_factory=ClientPricing)
    session_budget_gbp: float = 1.0


# ---------- audit_log ----------

class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str = Field(alias="_id")
    ts: str
    actor: str
    action: str
    lead_id: Optional[str] = None
    cost_cents: float = 0
    recipient_sha256: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "GeoPoint",
    "GeoPolygon",
    "Lead",
    "LeadGeo",
    "LeadScores",
    "LeadOwner",
    "LeadDecisionMaker",
    "LeadPanel",
    "LeadPanelLayout",
    "LeadFluxOverlay",
    "LeadFinancial",
    "Company",
    "Director",
    "InspirePolygonDoc",
    "Client",
    "ClientBranding",
    "ClientPricing",
    "AuditEvent",
    "PremisesType",
]
