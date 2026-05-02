import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import type {
  CalculatorResponse,
  Client,
  Director,
  FluxOverlay,
  InboundLeadPayload,
  Lead,
  OutreachChannel,
  OutreachResponse,
  PanelLayout,
  PitchResponse,
  PricingTier,
  RianAgentKind,
  RianRunDetail,
  RianRunResponse,
  ScanResponse,
  Spend,
  SwarmJob,
  SwarmRunResponse,
  VoicePitchAudio,
  VoiceSignedUrl,
} from "./types";

// In dev, leave this empty so requests are relative and go through the Vite
// proxy (see packages/web/vite.config.ts). The proxy handles transient API
// restarts cleanly (returns 502) instead of producing bare "Failed to fetch"
// network errors. In prod the bundle runs on the same origin as the API, so
// relative paths still work. Override with VITE_API_BASE only if the web is
// served from a different origin than the API (e.g. preview deploys).
export const API_BASE: string =
  (import.meta as { env?: Record<string, string | undefined> }).env
    ?.VITE_API_BASE ?? "";

class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function http<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
      ...init,
    });
  } catch (err) {
    // fetch() rejects with TypeError on network failure (DNS, refused
    // connection, CORS preflight failure). Surface a message the user can act
    // on instead of bare "Failed to fetch".
    const cause = err instanceof Error ? err.message : String(err);
    throw new ApiError(
      0,
      `Cannot reach API at ${API_BASE || window.location.origin}${path} — is the server running? (${cause})`,
      null,
    );
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      try {
        body = await res.text();
      } catch {
        // ignore
      }
    }
    throw new ApiError(res.status, `HTTP ${res.status} on ${path}`, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ─── Scan ──────────────────────────────────────────────────────────────────

export interface ScanArgs {
  postcode: string;
  client_id?: string;
  limit?: number;
}

export function useScan(): UseMutationResult<ScanResponse, Error, ScanArgs> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: ScanArgs) =>
      http<ScanResponse>("/scan", {
        method: "POST",
        body: JSON.stringify({
          postcode: args.postcode,
          client_id: args.client_id ?? "client-greensolar-uk",
          limit: args.limit ?? 50,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

// ─── Leads ─────────────────────────────────────────────────────────────────

export function useLeads(clientId = "client-greensolar-uk"): UseQueryResult<
  Lead[],
  Error
> {
  return useQuery({
    queryKey: ["leads", clientId],
    queryFn: () => http<Lead[]>(`/leads?client_id=${clientId}`),
    staleTime: 30_000,
  });
}

export function useLeadDetail(
  id: string | null,
): UseQueryResult<Lead, Error> {
  return useQuery({
    queryKey: ["lead", id],
    queryFn: () => http<Lead>(`/lead/${id}`),
    enabled: !!id,
    staleTime: 15_000,
  });
}

// ─── Directors / Org ───────────────────────────────────────────────────────

export function useDirectors(
  leadId: string | null,
): UseQueryResult<Director[], Error> {
  return useQuery({
    queryKey: ["directors", leadId],
    queryFn: () =>
      http<{ directors: Director[] }>(
        `/lead/${leadId}/refresh_directors`,
        { method: "POST" },
      ).then((r) => r.directors),
    enabled: !!leadId,
    staleTime: 5 * 60_000,
  });
}

export function useBuildOrg(): UseMutationResult<
  { decision_maker: { name: string; role: string; confidence: number; rationale: string } },
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (leadId: string) =>
      http<{
        decision_maker: { name: string; role: string; confidence: number; rationale: string };
      }>(`/lead/${leadId}/build_org`, { method: "POST" }),
    onSuccess: (_, leadId) => {
      qc.invalidateQueries({ queryKey: ["lead", leadId] });
      qc.invalidateQueries({ queryKey: ["spend"] });
    },
  });
}

// ─── Pitch ─────────────────────────────────────────────────────────────────

export function useGeneratePitch(): UseMutationResult<
  PitchResponse,
  Error,
  { leadId: string; clientId?: string }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, clientId }) =>
      http<PitchResponse>(`/lead/${leadId}/pitch`, {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId ?? "client-greensolar-uk",
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spend"] });
    },
  });
}

// ─── Outreach (channel-tailored, Sonnet 4.6) ──────────────────────────────

export function useGenerateOutreach(): UseMutationResult<
  OutreachResponse,
  Error,
  { leadId: string; channel: OutreachChannel; clientId?: string }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, channel, clientId }) =>
      http<OutreachResponse>(`/lead/${leadId}/outreach`, {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId ?? "client-greensolar-uk",
          channel,
        }),
      }),
    onSuccess: (_, { leadId }) => {
      qc.invalidateQueries({ queryKey: ["lead", leadId] });
      qc.invalidateQueries({ queryKey: ["spend"] });
    },
  });
}

// ─── Flux / Panels ────────────────────────────────────────────────────────

export function useFluxOverlay(): UseMutationResult<
  FluxOverlay,
  Error,
  string
> {
  return useMutation({
    mutationFn: (leadId: string) =>
      http<FluxOverlay>(`/lead/${leadId}/flux_overlay`, { method: "POST" }),
  });
}

export function usePanels(): UseMutationResult<PanelLayout, Error, string> {
  return useMutation({
    mutationFn: (leadId: string) =>
      http<PanelLayout>(`/lead/${leadId}/panels`, { method: "POST" }),
  });
}

// ─── Spend ─────────────────────────────────────────────────────────────────

export function useSpend(): UseQueryResult<Spend, Error> {
  return useQuery({
    queryKey: ["spend"],
    queryFn: () => http<Spend>("/lead/spend/session"),
    refetchInterval: 4_000,
    refetchIntervalInBackground: false,
  });
}

// ─── Voice ─────────────────────────────────────────────────────────────────

export function useVoiceSignedUrl(): UseMutationResult<
  VoiceSignedUrl,
  Error,
  string
> {
  return useMutation({
    mutationFn: (leadId: string) =>
      http<VoiceSignedUrl>(`/voice/signed-url?lead_id=${leadId}`),
  });
}

export interface VoicePitchAudioArgs {
  leadId: string;
  clientId?: string;
}

export function useVoicePitchAudio(): UseMutationResult<
  VoicePitchAudio,
  Error,
  VoicePitchAudioArgs
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, clientId }) =>
      http<VoicePitchAudio>("/voice/pitch_audio", {
        method: "POST",
        body: JSON.stringify({
          lead_id: leadId,
          client_id: clientId ?? "client-greensolar-uk",
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spend"] });
    },
  });
}

// ─── Calculator + Inbound ──────────────────────────────────────────────────

export function useCalculator(): UseMutationResult<
  CalculatorResponse,
  Error,
  { address: string; annual_kwh: number; premises_type?: string }
> {
  return useMutation({
    mutationFn: (body) =>
      http<CalculatorResponse>("/financial/calculator", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

export function useSubmitInbound(): UseMutationResult<
  { ok: boolean; lead_id?: string },
  Error,
  InboundLeadPayload
> {
  return useMutation({
    mutationFn: (body) =>
      http<{ ok: boolean; lead_id?: string }>("/inbound/lead", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

// ─── Admin ─────────────────────────────────────────────────────────────────

export interface AdminPayload {
  branding?: { primary?: string; logo_url?: string };
  pricing?: { panel_unit_gbp?: number; install_per_kw_gbp?: number };
  session_budget_gbp?: number;
  // Admin Centre extensions — fed downstream into pitch/email generators.
  product_description?: string;
  product_features?: string[];
  warranty_terms?: string;
  pricing_tiers?: PricingTier[];
  expertise_notes?: string;
}

export function useSaveAdmin(): UseMutationResult<
  Client,
  Error,
  { slug: string; payload: AdminPayload }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, payload }) =>
      http<Client>(`/admin/client/${slug}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client"] });
    },
  });
}

export function useClient(slug: string): UseQueryResult<Client, Error> {
  return useQuery({
    queryKey: ["client", slug],
    queryFn: () => http<Client>(`/admin/client/${slug}`),
    staleTime: 60_000,
  });
}

// ─── Swarm ─────────────────────────────────────────────────────────────────

export interface SwarmRunArgs {
  objective: string;
  target_lead_id?: string | null;
}

export function useSwarmRun(): UseMutationResult<
  SwarmRunResponse,
  Error,
  SwarmRunArgs
> {
  return useMutation({
    mutationFn: (args) =>
      http<SwarmRunResponse>("/swarm/run", {
        method: "POST",
        body: JSON.stringify({
          objective: args.objective,
          target_lead_id: args.target_lead_id ?? null,
        }),
      }),
  });
}

/**
 * Poll a swarm job. Refetches every 2 s while the job is queued/running.
 * Pass `null` to disable.
 */
export function useSwarmJob(
  jobId: string | null,
): UseQueryResult<SwarmJob, Error> {
  return useQuery({
    queryKey: ["swarm-job", jobId],
    queryFn: () => http<SwarmJob>(`/swarm/job/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "error" ? false : 2_000;
    },
    refetchIntervalInBackground: false,
    staleTime: 0,
  });
}

// ─── Rian agent (deepagents) ───────────────────────────────────────────────

export interface RunRianAgentArgs {
  agent: RianAgentKind;
  target_lead_id?: string | null;
  client_id?: string;
  params?: Record<string, unknown>;
}

export function useRunRianAgent(): UseMutationResult<
  RianRunResponse,
  Error,
  RunRianAgentArgs
> {
  return useMutation({
    mutationFn: (args) =>
      http<RianRunResponse>("/rian/run_agent", {
        method: "POST",
        body: JSON.stringify({
          agent: args.agent,
          target_lead_id: args.target_lead_id ?? null,
          client_id: args.client_id ?? "client-greensolar-uk",
          params: args.params ?? {},
        }),
      }),
  });
}

/**
 * Poll a Rian agent run. Mirrors useSwarmJob — refetches while the run is
 * queued/running, stops once a terminal status lands. Note that "demo_mode"
 * and "upstream_error" are TERMINAL states (the run finished, just not in
 * "ok" mode), so we treat them like "done" for polling purposes.
 */
export function useRianAgentRun(
  runId: string | null,
): UseQueryResult<RianRunDetail, Error> {
  return useQuery({
    queryKey: ["rian-run", runId],
    queryFn: () => http<RianRunDetail>(`/rian/run_agent/${runId}`),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const terminal: ReadonlyArray<string> = [
        "done",
        "demo_mode",
        "upstream_error",
        "error",
      ];
      return status && terminal.includes(status) ? false : 2_000;
    },
    refetchIntervalInBackground: false,
    staleTime: 0,
  });
}
