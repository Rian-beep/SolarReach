import { useState } from "react";
import {
  AlertTriangle,
  Banknote,
  ExternalLink,
  Leaf,
  Receipt,
  Zap,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import {
  computeMonthlyPayment,
  formatYears,
  UK_SEG_EXPORT_RATE_GBP_PER_KWH,
  type FundingModelId,
} from "@/lib/financial";
import { gbp } from "@/lib/utils";
import type { Lead } from "@/lib/types";

interface ReferenceTabProps {
  lead: Lead;
}

// ── Static funding-model metadata (mirrors codex constants_funding.py) ────
interface FundingModelMeta {
  id: FundingModelId;
  short: string; // tab label
  name: string;
  description: string;
  termYears: number; // representative term used for monthly calc
  termLabel: string;
  ownership: "client" | "provider";
  ownershipLabel: string;
  segClaimer: "client" | "provider" | "split";
  segLabel: string;
  pros: [string, string];
  cons: [string, string];
}

const FUNDING_MODELS: FundingModelMeta[] = [
  {
    id: "capex",
    short: "CAPEX",
    name: "Capital Expense",
    description: "Buy outright. Full ownership day one. Maximum 25-year NPV.",
    termYears: 0,
    termLabel: "n/a · upfront",
    ownership: "client",
    ownershipLabel: "Client owns day 1",
    segClaimer: "client",
    segLabel: "Client claims SEG",
    pros: ["Highest 25yr NPV", "Full AIA tax write-off"],
    cons: ["Upfront cash outlay", "Balance-sheet impact"],
  },
  {
    id: "free_install",
    short: "FREE INSTALL",
    name: "Free Install (PPA)",
    description:
      "£0 upfront. Provider owns kit; client pays per-kWh at ~85% of grid.",
    termYears: 20,
    termLabel: "20–25 yr",
    ownership: "provider",
    ownershipLabel: "Provider owns",
    segClaimer: "provider",
    segLabel: "Provider claims SEG",
    pros: ["Zero capex", "Maintenance included"],
    cons: ["Lower long-term saving", "20yr commitment"],
  },
  {
    id: "lease_purchase",
    short: "LEASE PURCHASE",
    name: "Lease Purchase",
    description:
      "Asset finance lease 5–10 yr. Off-balance under IFRS 16. Own at end.",
    termYears: 7,
    termLabel: "5–10 yr",
    ownership: "client",
    ownershipLabel: "Client owns at end",
    segClaimer: "client",
    segLabel: "Client claims SEG",
    pros: ["Preserves working capital", "Ownership at end"],
    cons: ["Interest cost over term", "Credit approval req."],
  },
  {
    id: "operational_lease",
    short: "OP LEASE",
    name: "Operational Lease",
    description:
      "Pure rental. 100% tax-deductible OpEx. Hand back at end of term.",
    termYears: 6,
    termLabel: "5–7 yr",
    ownership: "provider",
    ownershipLabel: "Provider owns",
    segClaimer: "provider",
    segLabel: "Provider claims SEG",
    pros: ["Fully tax deductible", "Tech refresh at end"],
    cons: ["No asset at end", "Higher TCO"],
  },
  {
    id: "hire_purchase",
    short: "HIRE PURCHASE",
    name: "Hire Purchase",
    description:
      "Deposit + monthly + balloon. Asset on balance sheet from day 1.",
    termYears: 4,
    termLabel: "3–5 yr",
    ownership: "client",
    ownershipLabel: "Client owns at end",
    segClaimer: "client",
    segLabel: "Client claims SEG",
    pros: ["Capital allowance day 1", "Fixed-rate protection"],
    cons: ["On balance sheet", "Interest cost"],
  },
];

const RESIDENTIAL_PREMISES = new Set<string>(["residential"]);

export function ReferenceTab({ lead }: ReferenceTabProps) {
  // ── ALL HOOKS BEFORE CONDITIONAL RETURNS ────────────────────────────────
  const [activeModel, setActiveModel] = useState<FundingModelId>("capex");

  const fin = lead.financial;
  const capex = fin?.capex_gbp ?? 0;
  const annualSaving = fin?.annual_saving_gbp ?? 0;

  // SEG export estimate: 20% of annual generation exported at commercial sites
  const annualKwh = lead.panel_layout?.annual_kwh ?? 0;
  const exportedKwh = annualKwh * 0.2;
  const segAnnualGbp = exportedKwh * UK_SEG_EXPORT_RATE_GBP_PER_KWH;

  const isResidential = RESIDENTIAL_PREMISES.has(
    (lead.premises_type as string) ?? "",
  );

  return (
    <div className="space-y-3">
      {/* ── Interactive Funding Model Selector ─────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="text-[10px] uppercase tracking-widest text-grid">
            Click each · live monthly cash-flow
          </div>
          <CardTitle className="flex items-center gap-2">
            <Banknote className="size-4 text-cyan" strokeWidth={1.5} />
            FUNDING MODEL
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs
            value={activeModel}
            onValueChange={(v) => setActiveModel(v as FundingModelId)}
          >
            <TabsList className="font-mono text-[10px] uppercase tracking-widest">
              {FUNDING_MODELS.map((m) => (
                <TabsTrigger
                  key={m.id}
                  value={m.id}
                  className="px-2 text-[10px]"
                >
                  {m.short}
                </TabsTrigger>
              ))}
            </TabsList>

            {FUNDING_MODELS.map((m) => {
              const monthly = computeMonthlyPayment(
                capex,
                m.id,
                m.termYears || 1,
                0.06,
                annualSaving,
              );
              return (
                <TabsContent key={m.id} value={m.id}>
                  <div className="space-y-2.5 rounded-[2px] border border-iron-bright bg-app-elev-1 p-3">
                    {/* Name + description */}
                    <div>
                      <div className="font-mono text-sm uppercase tracking-wide text-bone">
                        {m.name}
                      </div>
                      <p className="mt-1 text-xs text-mute leading-relaxed">
                        {m.description}
                      </p>
                    </div>

                    {/* Monthly payment hero */}
                    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[2px] border border-iron bg-iron">
                      <div className="bg-app-surface px-2 py-1.5">
                        <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
                          MONTHLY
                        </div>
                        <div className="font-mono text-lg text-cyan tabular-nums">
                          {m.id === "capex"
                            ? "£0"
                            : gbp(monthly, { decimals: 0 })}
                        </div>
                      </div>
                      <div className="bg-app-surface px-2 py-1.5">
                        <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
                          TERM
                        </div>
                        <div className="font-mono text-lg text-bone tabular-nums">
                          {m.termLabel}
                        </div>
                      </div>
                    </div>

                    {/* Ownership + SEG badges */}
                    <div className="flex flex-wrap gap-1.5">
                      <Badge
                        variant={
                          m.ownership === "client" ? "cyan" : "magenta"
                        }
                      >
                        {m.ownershipLabel}
                      </Badge>
                      <Badge variant="amber">{m.segLabel}</Badge>
                    </div>

                    {/* Pros / Cons */}
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <div>
                        <div className="font-mono text-[10px] uppercase tracking-widest text-emerald">
                          PROS
                        </div>
                        <ul className="mt-1 space-y-0.5">
                          {m.pros.map((p) => (
                            <li
                              key={p}
                              className="font-mono text-[11px] text-mute"
                            >
                              <span className="text-emerald">+ </span>
                              {p}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <div className="font-mono text-[10px] uppercase tracking-widest text-red">
                          CONS
                        </div>
                        <ul className="mt-1 space-y-0.5">
                          {m.cons.map((c) => (
                            <li
                              key={c}
                              className="font-mono text-[11px] text-mute"
                            >
                              <span className="text-red">− </span>
                              {c}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </TabsContent>
              );
            })}
          </Tabs>
        </CardContent>
      </Card>

      {/* ── TAX BREAKS · UK 2026 ────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="text-[10px] uppercase tracking-widest text-grid">
            UK incentives · {isResidential ? "residential" : "commercial"}
          </div>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="size-4 text-amber" strokeWidth={1.5} />
            TAX BREAKS
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {/* Smart Export Guarantee */}
          <div className="rounded-[2px] border border-iron bg-app-elev-1 p-2.5">
            <div className="mb-0.5 flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-bone">
                <Zap className="size-3 text-amber" strokeWidth={1.5} />
                SMART EXPORT GUARANTEE
              </span>
              <span className="font-mono text-sm text-amber tabular-nums">
                £{UK_SEG_EXPORT_RATE_GBP_PER_KWH.toFixed(2)}/kWh
              </span>
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
              Ofgem 2026 · paid for exported energy
            </div>
            {annualKwh > 0 && (
              <div className="mt-1 font-mono text-[11px] text-mute">
                Est.{" "}
                <span className="text-bone tabular-nums">
                  {Math.round(exportedKwh).toLocaleString("en-GB")} kWh/yr
                </span>{" "}
                exported ={" "}
                <span className="text-emerald tabular-nums">
                  {gbp(segAnnualGbp, { decimals: 0 })}/yr
                </span>
              </div>
            )}
          </div>

          {/* Capital Allowances — AIA */}
          <div className="rounded-[2px] border border-iron bg-app-elev-1 p-2.5">
            <div className="mb-0.5 flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-widest text-bone">
                CAPITAL ALLOWANCES (AIA)
              </span>
              <Badge variant="emerald">100%</Badge>
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
              First £1M qualifying plant · until 2026-04-30
            </div>
            <div className="mt-1 font-mono text-[11px] text-mute">
              After cap → 18% writing-down allowance on remainder.
            </div>
          </div>

          {/* Super Deduction — EXPIRED */}
          <div className="rounded-[2px] border border-red/30 bg-red/5 p-2.5">
            <div className="mb-0.5 flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-bone">
                <AlertTriangle
                  className="size-3 text-red"
                  strokeWidth={1.5}
                />
                SUPER DEDUCTION (130%)
              </span>
              <Badge variant="red">EXPIRED</Badge>
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
              Ended 2023-04 · context only
            </div>
            <div className="mt-1 font-mono text-[11px] text-mute">
              Some leads still carrying accelerated allowances from the window.
            </div>
          </div>

          {/* VAT */}
          <div className="rounded-[2px] border border-iron bg-app-elev-1 p-2.5">
            <div className="mb-0.5 flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-widest text-bone">
                VAT
              </span>
              {isResidential ? (
                <Badge variant="emerald">0%</Badge>
              ) : (
                <Badge variant="amber">20% RECOVERABLE</Badge>
              )}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
              {isResidential
                ? "0% VAT · residential install (UK 2022-)"
                : "20% standard · recoverable if VAT-registered"}
            </div>
          </div>

          {/* ECO4 */}
          <div className="rounded-[2px] border border-iron bg-app-elev-1 p-2.5">
            <div className="mb-0.5 flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-widest text-bone">
                ECO4 GRANT
              </span>
              {isResidential ? (
                <Badge variant="emerald">UP TO £14k</Badge>
              ) : (
                <Badge variant="outline">RESIDENTIAL ONLY</Badge>
              )}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-grid">
              Fuel-poor / EPC D-G + qualifying benefits
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── REFERENCES ──────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="text-[10px] uppercase tracking-widest text-grid">
            Sources · UK government & open data
          </div>
          <CardTitle className="flex items-center gap-2">
            <Leaf className="size-4 text-emerald" strokeWidth={1.5} />
            REFERENCES
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1.5 font-mono text-[11px] text-mute">
            <li>
              <a
                href="https://www.ofgem.gov.uk/environmental-and-social-schemes/smart-export-guarantee-seg"
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 text-mute hover:text-cyan transition-colors"
              >
                <ExternalLink className="size-3" strokeWidth={1.5} />
                Ofgem · Smart Export Guarantee (SEG)
              </a>
            </li>
            <li>
              <a
                href="https://www.gov.uk/capital-allowances/annual-investment-allowance"
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 text-mute hover:text-cyan transition-colors"
              >
                <ExternalLink className="size-3" strokeWidth={1.5} />
                HMRC · Annual Investment Allowance (AIA)
              </a>
            </li>
            <li>
              <span className="inline-flex items-center gap-1">
                <span className="text-grid">·</span>
                HM Treasury Spring Statement 2026 (capital allowances cap)
              </span>
            </li>
            <li>
              <span className="inline-flex items-center gap-1">
                <span className="text-grid">·</span>
                HM Land Registry · CCOD/OCOD/INSPIRE freehold polygons
              </span>
            </li>
            <li>
              <span className="inline-flex items-center gap-1">
                <span className="text-grid">·</span>
                Companies House · officer + filing data
              </span>
            </li>
            <li>
              <span className="inline-flex items-center gap-1">
                <span className="text-grid">·</span>
                Google Solar API · per-pixel kWh/m²/day flux
              </span>
            </li>
          </ul>
          {fin && (
            <div className="mt-3 border-t border-iron pt-2 font-mono text-[10px] uppercase tracking-widest text-grid">
              Computed for this lead · payback{" "}
              <span className="text-bone tabular-nums">
                {formatYears(fin.payback_years)}
              </span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
