// SolarReach shared TypeScript types — mirror of packages/shared/schemas/*.json
// Keep in sync with packages/shared/py/solarreach_shared/models.py.

// ---------- GeoJSON ----------

export interface GeoPoint {
  type: "Point";
  coordinates: [number, number]; // [lng, lat] EPSG:4326
}

export type PolygonSource =
  | "inspire_index_polygon"
  | "solar_api_bbox"
  | "synthesized";

export interface GeoPolygon {
  type: "Polygon";
  coordinates: number[][][];
  source: PolygonSource;
  inspire_id?: string | null;
  area_m2_approx?: number | null;
}

// ---------- leads ----------

export type PremisesType =
  | "office"
  | "leisure"
  | "warehouse"
  | "retail"
  | "education"
  | "residential"
  | "mixed";

export interface LeadScores {
  solar_roi: number;
  financial_health: number;
  social_impact: number;
  composite_score: number;
  scored_at?: string;
}

export interface LeadOwner {
  company_id?: string | null;
  company_name?: string;
  source: "ccod" | "ocod" | "synthesized";
}

export interface LeadDecisionMaker {
  name?: string;
  role?: string;
  confidence: number;
  rationale?: string;
}

export interface LeadPanel {
  corners: number[][];
  tilt: number;
  azimuth: number;
  kwh_yr: number;
}

export interface LeadPanelLayout {
  panels: LeadPanel[];
  panel_count: number;
  annual_kwh: number;
  clipped_at?: string;
  clip_method?: string;
}

export interface LeadFluxOverlay {
  url: string;
  bbox: [number, number, number, number];
  vmin: number;
  vmax: number;
  cached_at?: string;
}

export interface LeadFinancial {
  capex_gbp: number;
  annual_saving_gbp: number;
  payback_years: number;
  npv_25yr_gbp: number;
}

export interface Lead {
  _id: string;
  client_id: string;
  address: string;
  postcode: string;
  borough?: string;
  premises_type: PremisesType;
  geo: { point: GeoPoint };
  rooftop_polygon?: GeoPolygon;
  scores?: LeadScores;
  owner?: LeadOwner;
  decision_maker?: LeadDecisionMaker;
  panel_layout?: LeadPanelLayout;
  flux_overlay?: LeadFluxOverlay;
  financial?: LeadFinancial;
  created_at: string;
  updated_at?: string;
}

// ---------- companies ----------

export interface Company {
  _id: string;
  name: string;
  ch_number?: string | null;
  registered_address?: string | null;
  title_number?: string | null;
  ccod_proprietor_name?: string | null;
  property_address?: string | null;
  directors: string[];
  embedding?: number[] | null;
}

// ---------- directors ----------

export interface Director {
  _id: string;
  company_id: string;
  name: string;
  name_display?: string;
  role?: string;
  appointed_on?: string;
  email?: string;
  linkedin_url?: string;
  ch_officer_id?: string;
}

// ---------- inspire_polygons ----------

export interface InspirePolygonDoc {
  _id: string;
  inspire_id: string;
  borough?: string;
  polygon: GeoPolygon;
  area_m2_approx: number;
  centroid: GeoPoint;
}

// ---------- clients ----------

export interface ClientBranding {
  primary?: string;
  logo_url?: string;
}

export interface ClientPricing {
  panel_unit_gbp: number;
  install_per_kw_gbp: number;
}

export interface ClientDoc {
  _id: string;
  name: string;
  branding: ClientBranding;
  pricing: ClientPricing;
  session_budget_gbp: number;
}

// ---------- audit_log ----------

export interface AuditEvent {
  _id: string;
  ts: string;
  actor: string;
  action: string;
  lead_id?: string | null;
  cost_cents: number;
  recipient_sha256?: string | null;
  metadata: Record<string, unknown>;
}
