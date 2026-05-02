import { useState } from "react";
import {
  Building2,
  ChevronDown,
  ChevronRight,
  Leaf,
  Microscope,
  Network,
  ShieldCheck,
  Sun,
  Timer,
  UserRound,
} from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Badge, ScoreBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { API_BASE, useBuildOrg, useDirectors } from "@/lib/api";
import { useCostConfirm } from "@/components/header/CostConfirmModal";
import { computeRoi, formatYears } from "@/lib/financial";
import { caption, gbp } from "@/lib/utils";
import type { Lead, PremisesType } from "@/lib/types";

// Benchmarks per UK commercial premises type. Sources: BEIS commercial PV
// performance reports + Solar Energy UK 2025 commercial benchmark survey.
// These drive the "avg in this bracket" callouts in SOLAR METRICS.
const PREMISES_BENCHMARKS: Record<
  PremisesType,
  { paybackYears: number; roiPct: number; annualKwh: number }
> = {
  warehouse: { paybackYears: 6.5, roiPct: 12.4, annualKwh: 95_000 },
  retail: { paybackYears: 7.8, roiPct: 9.6, annualKwh: 32_000 },
  office: { paybackYears: 8.2, roiPct: 8.9, annualKwh: 28_000 },
  leisure: { paybackYears: 7.4, roiPct: 10.1, annualKwh: 48_000 },
  education: { paybackYears: 9.1, roiPct: 7.8, annualKwh: 36_000 },
};

// 0.193 kg CO2 per kWh — UK 2025 grid carbon intensity (BEIS).
const KG_CO2_PER_KWH = 0.193;

// Flux PNGs are served by FastAPI's StaticFiles mount under /static/flux/<id>.png.
// Browser <img> tags hit Vite's dev server unless we absolutise to API_BASE.
function absolutiseStaticUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE}${url}`;
}

interface IntelTabProps {
  lead: Lead;
}

export function IntelTab({ lead }: IntelTabProps) {
  // ── ALL HOOKS BEFORE ANY CONDITIONAL RETURN (Gotham rule) ────────────────
  const directors = useDirectors(lead._id);
  const buildOrg = useBuildOrg();
  const { confirm } = useCostConfirm();
  const [solarMetricsOpen, setSolarMetricsOpen] = useState(true);

  const onBuildOrg = async () => {
    const ok = await confirm(5, "Build org chart (Opus inference)");
    if (!ok) return;
    try {
      await buildOrg.mutateAsync(lead._id);
      toast.success("Decision-maker inferred");
    } catch (err) {
      toast.error(`Org build failed: ${(err as Error).message}`);
    }
  };

  const lng = lead.geo?.point?.coordinates?.[0];
  const lat = lead.geo?.point?.coordinates?.[1];
  const fin = lead.financial;
  const dm = lead.decision_maker;
  const lowConfidence = dm !== undefined && dm.confidence < 0.7;

  return (
    <div className="space-y-3">
      {/* ── PAYBACK HERO ───────────────────────────────────────────────── */}
      {fin ? (
        <Card>
          <CardHeader>
            <div className={caption}>buyer · #1 question</div>
            <CardTitle className="flex items-center gap-1.5">
              <Timer className="size-3.5 text-cyan" strokeWidth={1.5} />
              PAYBACK
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-end justify-between gap-3">
              <div className="font-mono text-display text-bone tracking-tight tabular-nums">
                {formatYears(fin.payback_years)}
              </div>
              <div className="text-right leading-tight">
                <div className={caption}>NPV 25YR</div>
                <div className="font-mono text-md text-emerald tabular-nums">
                  {gbp(fin.npv_25yr_gbp)}
                </div>
              </div>
            </div>
            {/* 3-stat compact row */}
            <div className="grid grid-cols-3 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>CAPEX</div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {gbp(fin.capex_gbp)}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>ANNUAL SAVING</div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {gbp(fin.annual_saving_gbp)}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>ROI %</div>
                <div className="font-mono text-sm text-emerald tabular-nums">
                  {computeRoi(fin.capex_gbp, fin.annual_saving_gbp).toFixed(1)}%
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Timer className="size-3.5 text-cyan" strokeWidth={1.5} />
              PAYBACK
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-10 w-32" />
            <div className="grid grid-cols-3 gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── SOLAR RADIANCE (live Google Solar API) ───────────────────────── */}
      {lead.flux_overlay?.url && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-1.5">
                <Sun className="size-3.5 text-amber" strokeWidth={1.5} />
                SOLAR RADIANCE
              </CardTitle>
              <span className={caption}>Live · Google Solar API</span>
            </div>
          </CardHeader>
          <CardContent>
            <img
              src={absolutiseStaticUrl(lead.flux_overlay.url)}
              alt=""
              className="w-full rounded-[2px] border border-iron"
            />
            <div className="mt-1.5 flex justify-between font-mono text-[10px] uppercase tracking-widest text-grid">
              <span>{lead.flux_overlay.vmin?.toFixed(0)} kWh/m²/yr</span>
              <span>{lead.flux_overlay.vmax?.toFixed(0)}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── PANEL LAYOUT (live Solar API findClosest, ray-cast clipped) ──── */}
      {lead.panel_layout?.panel_count ? (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>PANEL LAYOUT</CardTitle>
              <span className={caption}>Live · ray-cast clipped</span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>PANEL COUNT</div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {lead.panel_layout.panel_count}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>ANNUAL kWh</div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {lead.panel_layout.annual_kwh.toLocaleString()}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* ── COMPOSITE SCORE ──────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>COMPOSITE SCORE</CardTitle>
        </CardHeader>
        <CardContent className="flex items-start justify-between gap-3">
          <ScoreBadge score={lead.scores.composite_score} />
          <div className="flex-1 space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-mute uppercase tracking-wide">
                Solar ROI
              </span>
              <span className="font-mono text-bone tabular-nums">
                {(lead.scores.solar_roi * 100).toFixed(0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-mute uppercase tracking-wide">
                Fin Health
              </span>
              <span className="font-mono text-bone tabular-nums">
                {(lead.scores.financial_health * 100).toFixed(0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-mute uppercase tracking-wide">
                Social Impact
              </span>
              <span className="font-mono text-bone tabular-nums">
                {(lead.scores.social_impact * 100).toFixed(0)}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── SOLAR METRICS · DEEP RESEARCH (collapsible) ────────────────── */}
      <SolarMetricsCard
        lead={lead}
        open={solarMetricsOpen}
        onToggle={() => setSolarMetricsOpen((o) => !o)}
      />

      {/* ── LAND REGISTRY OWNER ──────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-1.5">
              <ShieldCheck
                className="size-3.5 text-emerald"
                strokeWidth={1.5}
              />
              LAND REGISTRY OWNER
            </CardTitle>
            <Badge variant="outline">{lead.owner.source.toUpperCase()}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-1.5">
          <div className="font-mono text-sm text-bone">
            {lead.owner.company_name}
          </div>
          {/* Registration status — UK (CCOD) vs Overseas (OCOD). Pulled from
              the joined company doc. Matters for the deal: overseas owners
              involve cross-border payment + ESG-flag handling. */}
          {(() => {
            const company = (lead as unknown as {
              company?: {
                country_of_incorporation?: string;
                source?: string;
                ch_number?: string | null;
              };
            }).company;
            const ownerSrc: string = lead.owner.source ?? "synthesized";
            const isUK =
              ownerSrc !== "ocod" &&
              (ownerSrc === "ccod" ||
                ownerSrc === "real_owners_whitelist" ||
                ownerSrc === "synthesized" ||
                company?.country_of_incorporation === "United Kingdom");
            const country =
              company?.country_of_incorporation ??
              (isUK ? "United Kingdom" : "Overseas");
            return (
              <div className="mt-2 flex items-center gap-2 rounded-[2px] border border-iron px-2 py-1.5">
                <span
                  className={
                    "inline-flex size-1.5 rounded-full " +
                    (isUK ? "bg-emerald" : "bg-amber")
                  }
                />
                <div className="flex-1 font-mono text-[11px]">
                  <span className="text-grid uppercase tracking-widest">
                    REGISTERED IN
                  </span>{" "}
                  <span className={isUK ? "text-emerald" : "text-amber"}>
                    {country}
                  </span>
                </div>
                <span className="font-mono text-[10px] uppercase tracking-widest text-grid">
                  {isUK ? "CCOD" : "OCOD"}
                </span>
              </div>
            );
          })()}
          <div className="flex flex-col gap-px font-mono text-xs text-dim">
            <div>
              <span className="text-grid">company_id </span>
              {lead.owner.company_id ?? "—"}
            </div>
            <div>
              <span className="text-grid">postcode </span>
              {lead.postcode}
            </div>
            {lat !== undefined && lng !== undefined && (
              <div>
                <span className="text-grid">lat,lng </span>
                {lat.toFixed(4)}, {lng.toFixed(4)}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── DECISION-MAKER (compact card right under owner) ──────────────── */}
      {dm && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-1.5">
                <Network className="size-3.5 text-magenta" strokeWidth={1.5} />
                DECISION-MAKER
              </CardTitle>
              <div className="flex items-center gap-1">
                {lowConfidence && (
                  <Badge variant="amber">[LOW CONFIDENCE]</Badge>
                )}
                <Badge variant="magenta">
                  {Math.round(dm.confidence * 100)}% CONF
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-1.5">
            <div className="font-mono text-lg text-bone leading-tight">
              {dm.name}
            </div>
            <div className="font-mono text-[11px] uppercase tracking-widest text-cyan">
              {dm.role}
              <span className="text-grid"> · </span>
              <span className="text-mute tabular-nums">
                conf {dm.confidence.toFixed(2)}
              </span>
            </div>
            <p className="line-clamp-2 italic text-xs text-mute leading-relaxed">
              {dm.rationale}
            </p>
          </CardContent>
        </Card>
      )}

      {/* ── COMPANIES HOUSE OFFICERS ─────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5">
            <Building2 className="size-3.5 text-cyan" strokeWidth={1.5} />
            COMPANIES HOUSE OFFICERS
          </CardTitle>
        </CardHeader>
        <CardContent>
          {directors.isLoading ? (
            <div className="space-y-1.5">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : directors.isError ? (
            <p className="text-sm text-red">
              Failed to load officers: {directors.error.message}
            </p>
          ) : (directors.data ?? []).length === 0 ? (
            <p className="text-xs text-dim font-mono">[ -- ] no officers</p>
          ) : (
            <ul className="space-y-px">
              {(directors.data ?? []).map((d, i) => (
                <li
                  key={d._id}
                  className={
                    "flex items-center justify-between border-l-2 border-transparent hover:border-cyan hover:bg-app-elev-1 transition-colors duration-[80ms] px-2 py-1.5 " +
                    (i % 2 === 1 ? "bg-app-elev-1/40" : "")
                  }
                >
                  <div className="flex items-center gap-2">
                    <UserRound
                      className="size-3.5 text-mute"
                      strokeWidth={1.5}
                    />
                    <div className="leading-tight">
                      <div className="text-sm text-bone">
                        {d.name_display || d.name}
                      </div>
                      <div className="text-xs text-dim uppercase tracking-wide">
                        {d.role}
                      </div>
                    </div>
                  </div>
                  {d.appointed_on && (
                    <span className="font-mono text-xs text-dim tabular-nums">
                      {new Date(d.appointed_on).toISOString().slice(0, 10)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* ── BUILD ORG action (paid; user-initiated only) ─────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>ORG INFERENCE</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {!dm && (
            <p className="text-xs text-dim font-mono">
              [ -- ] no decision-maker inferred yet
            </p>
          )}
          <Button
            onClick={onBuildOrg}
            disabled={buildOrg.isPending}
            variant="ghost"
            size="sm"
            className="w-full"
          >
            {buildOrg.isPending
              ? "BUILDING…"
              : `[BUILD ORG] · ${gbp(5, { cents: true })}`}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ── SOLAR METRICS · DEEP RESEARCH ────────────────────────────────────────
// Collapsible deep-research breakdown: lifetime energy, lifetime saving,
// premises-bracket benchmarks, plus links into the REF tab for funding
// models + tax breaks (already rendered there). All numbers mono.

interface SolarMetricsCardProps {
  lead: Lead;
  open: boolean;
  onToggle: () => void;
}

function SolarMetricsCard({ lead, open, onToggle }: SolarMetricsCardProps) {
  const annualKwh = lead.panel_layout?.annual_kwh;
  const annualSavingGbp = lead.financial?.annual_saving_gbp;
  const lifetimeKwh = annualKwh ? annualKwh * 25 : undefined;
  const lifetimeSavingGbp = annualSavingGbp ? annualSavingGbp * 25 : undefined;
  const annualCo2Kg = annualKwh ? annualKwh * KG_CO2_PER_KWH : undefined;
  const lifetimeCo2Tonnes = annualCo2Kg ? (annualCo2Kg * 25) / 1000 : undefined;
  const benchmark = PREMISES_BENCHMARKS[lead.premises_type];

  return (
    <Card>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 p-2.5 text-left hover:bg-app-elev-1 transition-colors duration-[80ms]"
        aria-expanded={open}
      >
        <span className="flex items-center gap-1.5">
          <Microscope className="size-3.5 text-amber" strokeWidth={1.5} />
          <span className="text-xs font-medium uppercase tracking-wide text-mute">
            SOLAR METRICS · DEEP RESEARCH
          </span>
        </span>
        <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-grid">
          {open ? "COLLAPSE" : "EXPAND"}
          {open ? (
            <ChevronDown className="size-3.5" strokeWidth={1.5} />
          ) : (
            <ChevronRight className="size-3.5" strokeWidth={1.5} />
          )}
        </span>
      </button>

      {open && (
        <CardContent className="space-y-3 border-t border-iron pt-2.5">
          {/* Energy generated */}
          <div className="space-y-1">
            <div className={caption}>
              <span className="text-amber">[ENERGY GENERATED]</span>
            </div>
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>ANNUAL</div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {annualKwh
                    ? `${annualKwh.toLocaleString()} kWh/yr`
                    : "— kWh/yr"}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>25-YR LIFETIME</div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {lifetimeKwh
                    ? `${lifetimeKwh.toLocaleString()} kWh`
                    : "—"}
                </div>
              </div>
            </div>
          </div>

          {/* Money saved */}
          <div className="space-y-1">
            <div className={caption}>
              <span className="text-emerald">[MONEY SAVED]</span>
            </div>
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>ANNUAL · GROSS</div>
                <div className="font-mono text-sm text-emerald tabular-nums">
                  {annualSavingGbp ? gbp(annualSavingGbp) : "—"}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>25-YR · GROSS</div>
                <div className="font-mono text-sm text-emerald tabular-nums">
                  {lifetimeSavingGbp ? gbp(lifetimeSavingGbp) : "—"}
                </div>
              </div>
            </div>
            {lead.financial?.npv_25yr_gbp !== undefined && (
              <div className="font-mono text-[11px] text-dim">
                NPV (post-discount, 25yr) ·{" "}
                <span className="text-bone tabular-nums">
                  {gbp(lead.financial.npv_25yr_gbp)}
                </span>
              </div>
            )}
          </div>

          {/* Sales metrics — premises-type benchmarks */}
          <div className="space-y-1">
            <div className={caption}>
              <span className="text-cyan">
                [SALES METRICS · {lead.premises_type.toUpperCase()} BRACKET]
              </span>
            </div>
            {benchmark ? (
              <div className="grid grid-cols-3 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
                <div className="bg-app-surface px-2 py-1.5">
                  <div className={caption}>AVG PAYBACK</div>
                  <div className="font-mono text-sm text-bone tabular-nums">
                    {benchmark.paybackYears.toFixed(1)} yr
                  </div>
                </div>
                <div className="bg-app-surface px-2 py-1.5">
                  <div className={caption}>AVG ROI</div>
                  <div className="font-mono text-sm text-bone tabular-nums">
                    {benchmark.roiPct.toFixed(1)}%
                  </div>
                </div>
                <div className="bg-app-surface px-2 py-1.5">
                  <div className={caption}>AVG kWh/YR</div>
                  <div className="font-mono text-sm text-bone tabular-nums">
                    {benchmark.annualKwh.toLocaleString()}
                  </div>
                </div>
              </div>
            ) : (
              <p className="font-mono text-xs text-dim">
                [ -- ] no bracket data
              </p>
            )}
          </div>

          {/* CO2 offset */}
          <div className="space-y-1">
            <div className={caption}>
              <span className="text-emerald">[CO2 OFFSET]</span>
              <span className="text-grid"> · grid intensity 0.193 kg/kWh</span>
            </div>
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>ANNUAL</div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {annualCo2Kg
                    ? `${annualCo2Kg.toFixed(0)} kg`
                    : "—"}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className={caption}>25-YR</div>
                <div className="font-mono text-sm text-emerald tabular-nums">
                  {lifetimeCo2Tonnes
                    ? `${lifetimeCo2Tonnes.toFixed(1)} t`
                    : "—"}
                </div>
              </div>
            </div>
          </div>

          {/* Links to REF tab */}
          <div className="grid grid-cols-2 gap-2">
            <a
              href="#ref-funding"
              className="flex items-center justify-between rounded-[2px] border border-iron bg-app-surface px-2 py-1.5 hover:border-iron-bright transition-colors duration-[80ms]"
            >
              <span className="font-mono text-[11px] text-bone uppercase tracking-wide">
                FUNDING MODELS
              </span>
              <span className="font-mono text-[10px] text-cyan">
                REF →
              </span>
            </a>
            <a
              href="#ref-tax-breaks"
              className="flex items-center justify-between rounded-[2px] border border-iron bg-app-surface px-2 py-1.5 hover:border-iron-bright transition-colors duration-[80ms]"
            >
              <span className="font-mono text-[11px] text-bone uppercase tracking-wide">
                <Leaf className="inline size-3 mr-1 text-emerald" strokeWidth={1.5} />
                TAX BREAKS
              </span>
              <span className="font-mono text-[10px] text-cyan">
                REF →
              </span>
            </a>
          </div>
          <p className="font-mono text-[10px] text-grid leading-relaxed">
            SEG · AIA · ECO4 · 0% VAT — see REF tab for full breakdown of
            UK 2026 incentives across the 5 funding models.
          </p>
        </CardContent>
      )}
    </Card>
  );
}
