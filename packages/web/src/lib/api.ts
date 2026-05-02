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
  PanelLayout,
  PitchResponse,
  PricingTier,
  ScanResponse,
  Spend,
  VoiceSignedUrl,
} from "./types";

export const API_BASE: string =
  (import.meta as { env?: Record<string, string | undefined> }).env
    ?.VITE_API_BASE ?? "http://localhost:8000";

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
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    ...init,
  });
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
