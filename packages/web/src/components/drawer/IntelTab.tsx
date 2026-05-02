import { Building2, Network, ShieldCheck, UserRound } from "lucide-react";
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
import { gbp } from "@/lib/utils";
import type { Lead } from "@/lib/types";

interface IntelTabProps {
  lead: Lead;
}

export function IntelTab({ lead }: IntelTabProps) {
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

  return (
    <div className="space-y-3">
      {/* Composite score block */}
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

      {/* Land Registry / owner */}
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

      {/* Officers */}
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

      {/* Decision maker */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-1.5">
              <Network className="size-3.5 text-magenta" strokeWidth={1.5} />
              DECISION MAKER
            </CardTitle>
            {lead.decision_maker?.confidence !== undefined && (
              <Badge variant="magenta">
                {Math.round(lead.decision_maker.confidence * 100)}% CONF
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {lead.decision_maker ? (
            <div className="rounded-[2px] border border-iron bg-app-elev-1 p-2">
              <div className="font-mono text-sm text-bone">
                {lead.decision_maker.name}
              </div>
              <div className="text-xs text-cyan uppercase tracking-wide">
                {lead.decision_maker.role}
              </div>
              <p className="mt-1.5 text-xs text-mute leading-relaxed">
                {lead.decision_maker.rationale}
              </p>
            </div>
          ) : (
            <p className="text-xs text-dim font-mono">
              [ -- ] no decision maker inferred
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

      {/* Financials snapshot if present */}
      {lead.financial && (
        <Card>
          <CardHeader>
            <CardTitle>FINANCIAL SNAPSHOT</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full font-mono text-xs">
              <tbody>
                <tr className="border-b border-iron">
                  <td className="py-1 text-mute uppercase tracking-wide">
                    capex
                  </td>
                  <td className="py-1 text-right text-bone tabular-nums">
                    {gbp(lead.financial.capex_gbp)}
                  </td>
                </tr>
                <tr className="border-b border-iron bg-app-elev-1/40">
                  <td className="py-1 text-mute uppercase tracking-wide">
                    annual saving
                  </td>
                  <td className="py-1 text-right text-bone tabular-nums">
                    {gbp(lead.financial.annual_saving_gbp)}
                  </td>
                </tr>
                <tr className="border-b border-iron">
                  <td className="py-1 text-mute uppercase tracking-wide">
                    payback yrs
                  </td>
                  <td className="py-1 text-right text-bone tabular-nums">
                    {lead.financial.payback_years.toFixed(1)}
                  </td>
                </tr>
                <tr className="bg-app-elev-1/40">
                  <td className="py-1 text-mute uppercase tracking-wide">
                    npv 25yr
                  </td>
                  <td className="py-1 text-right text-emerald tabular-nums">
                    {gbp(lead.financial.npv_25yr_gbp)}
                  </td>
                </tr>
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
