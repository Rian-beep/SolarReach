// TS interfaces matching CONTRACTS.md § 1.

export type PremisesType =
  | "office"
  | "leisure"
  | "warehouse"
  | "retail"
  | "education";

export interface GeoPoint {
  type: "Point";
  coordinates: [number, number]; // [lng, lat]
}

export interface RooftopPolygon {
  type: "Polygon";
  coordinates: number[][][];
  source: "inspire_index_polygon" | "solar_api_bbox" | "synthesized";
  inspire_id?: string;
  area_m2_approx?: number;
}

export interface LeadScores {
  solar_roi: number;
  financial_health: number;
  social_impact: number;
  composite_score: number;
  scored_at: string;
}

export interface LeadOwner {
  company_id: string | null;
  company_name: string;
  source: "ccod" | "ocod" | "synthesized";
}

export interface DecisionMaker {
  name: string;
  role: string;
  confidence: number;
  rationale: string;
}

export interface PanelInstance {
  corners: [number, number][];
  tilt: number;
  azimuth: number;
  kwh_yr: number;
}

export interface PanelLayout {
  panels: PanelInstance[];
  panel_count: number;
  annual_kwh: number;
  clipped_at: string;
  clip_method: string;
}

export interface FluxOverlay {
  url: string;
  bbox: [number, number, number, number]; // w, s, e, n
  vmin: number;
  vmax: number;
  cached_at: string;
}

export interface Financial {
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
  rooftop_polygon?: RooftopPolygon;
  scores: LeadScores;
  owner: LeadOwner;
  decision_maker?: DecisionMaker;
  panel_layout?: PanelLayout;
  flux_overlay?: FluxOverlay;
  financial?: Financial;
  created_at: string;
  updated_at: string;
}

export interface Director {
  _id: string;
  company_id: string;
  name: string;
  name_display: string;
  role: string;
  appointed_on?: string;
  email?: string;
  linkedin_url?: string;
  ch_officer_id?: string;
}

export interface Company {
  _id: string;
  name: string;
  ch_number: string | null;
  registered_address?: string;
  title_number?: string;
  ccod_proprietor_name?: string;
  directors: string[];
  embedding?: number[];
}

export interface Spend {
  spent_cents: number;
  budget_cents: number;
  budget_pct: number;
}

export interface PricingTier {
  id: "starter" | "pro" | "enterprise";
  name: string;
  price_gbp: number;
  features: string[];
}

export interface Client {
  _id: string;
  name: string;
  branding: { primary: string; logo_url?: string };
  pricing: { panel_unit_gbp: number; install_per_kw_gbp: number };
  session_budget_gbp: number;
  // Admin Centre extensions (optional — older docs may not have them)
  product_description?: string;
  product_features?: string[];
  warranty_terms?: string;
  pricing_tiers?: PricingTier[];
  expertise_notes?: string;
}

export interface ScanResponse {
  scan_id: string;
  lead_count: number;
  stream_url: string;
}

export interface PitchResponse {
  pptx_url: string;
  pdf_url: string;
  emails: { a: string; b: string };
  deck_json: Record<string, unknown>;
}

export type OutreachChannel = "email" | "linkedin" | "intro_call";

export interface OutreachResponse {
  subject: string;
  body: string;
  channel: OutreachChannel;
  cost_cents: number;
}

export type VoiceProviderStatus =
  | "ok"
  | "demo_mode"
  | "disclosure_pending"
  | "upstream_error";

export interface VoiceSignedUrl {
  signed_url: string | null;
  agent_id: string | null;
  system_prompt_filled: string;
  status: VoiceProviderStatus;
  message: string;
  provider: string;
}

export type VoicePitchStatus = "ok" | "demo_mode" | "upstream_error";

export interface VoicePitchAudio {
  audio_url: string | null;
  script: string;
  duration_sec: number;
  cost_cents: number;
  status: VoicePitchStatus;
  message: string;
}

export interface CalculatorResponse {
  capex_gbp: number;
  annual_saving_gbp: number;
  payback_years: number;
  npv_25yr_gbp: number;
  eco4_eligible: boolean;
  eco4_grant_gbp: number;
  panel_count: number;
  annual_kwh: number;
}

export interface InboundLeadPayload {
  name: string;
  email: string;
  phone: string;
  address: string;
  annual_kwh?: number;
  premises_type?: PremisesType;
}

export interface TranscriptChunk {
  id: string;
  role: "agent" | "user" | "system";
  text: string;
  ts: number;
}

// ─── Swarm ────────────────────────────────────────────────────────────────

export interface SwarmArtifacts {
  pptx_url: string | null;
  mp3_url: string | null;
  research_bullets: string[];
}

export type SwarmJobStatus = "queued" | "running" | "done" | "error";

export interface SwarmRunResponse {
  job_id: string;
  status: SwarmJobStatus;
}

export interface SwarmJob {
  job_id: string;
  status: SwarmJobStatus;
  started_at: string | null;
  finished_at: string | null;
  result: string | null;
  error: string | null;
  artifacts: SwarmArtifacts | null;
}

// ─── Rian agent (deepagents/LangGraph integration) ────────────────────────

export type RianAgentKind = "lead_research" | "outreach_drafter";

export type RianAgentStatus = "ok" | "demo_mode" | "upstream_error";

// "queued"/"running" before the agent finishes; "done" only when status="ok".
// Failures resolve to "demo_mode" / "upstream_error" / "error" so the UI can
// distinguish "Rian's stack isn't installed" from "the stack ran and threw".
export type RianRunStatus =
  | "queued"
  | "running"
  | "done"
  | "demo_mode"
  | "upstream_error"
  | "error";

export interface RianAgentOutput {
  status: RianAgentStatus;
  agent: string;
  summary: string;
  thread_id: string | null;
  message_count: number;
  metadata: Record<string, unknown>;
}

export interface RianRunResponse {
  run_id: string;
  status: RianRunStatus;
}

export interface RianRunDetail {
  run_id: string;
  status: RianRunStatus;
  agent: string;
  target_lead_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  output: RianAgentOutput | null;
  error: string | null;
}
