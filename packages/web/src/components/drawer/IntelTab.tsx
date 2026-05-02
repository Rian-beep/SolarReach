import { Building2, Network, ShieldCheck, Timer, UserRound } from "lucide-react";
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
import { useBuildOrg, useDirectors } from "@/lib/api";
import { useCostConfirm } from "@/components/header/CostConfirmModal";
import { computeRoi, formatYears } from "@/lib/financial";
import { gbp } from "@/lib/utils";
import type { Lead } from "@/lib/types";

interface IntelTabProps {
  lead: Lead;
}

export function IntelTab({ lead }: IntelTabProps) {
  // ── ALL HOOKS BEFORE ANY CONDITIONAL RETURN (Gotham rule) ────────────────
  const directors = useDirectors(lead._id);
  const buildOrg = useBuildOrg();
  const { confirm } = useCostConfirm();

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
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-1.5">
                <Timer className="size-3.5 text-cyan" strokeWidth={1.5} />
                PAYBACK
              </CardTitle>
              <span className="font-mono text-[10px] uppercase tracking-widest text-grid">
                buyer · #1 question
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-end justify-between gap-3">
              <div className="font-mono text-display text-bone tracking-tight tabular-nums">
                {formatYears(fin.payback_years)}
              </div>
              <div className="text-right leading-tight">
                <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
                  NPV 25YR
                </div>
                <div className="font-mono text-md text-emerald tabular-nums">
                  {gbp(fin.npv_25yr_gbp)}
                </div>
              </div>
            </div>
            {/* 3-stat compact row */}
            <div className="grid grid-cols-3 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
              <div className="bg-app-surface px-2 py-1.5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
                  CAPEX
                </div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {gbp(fin.capex_gbp)}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
                  ANNUAL SAVING
                </div>
                <div className="font-mono text-sm text-bone tabular-nums">
                  {gbp(fin.annual_saving_gbp)}
                </div>
              </div>
              <div className="bg-app-surface px-2 py-1.5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
                  ROI %
                </div>
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
