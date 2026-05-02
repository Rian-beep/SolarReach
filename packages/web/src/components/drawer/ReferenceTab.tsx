import { Coins, FileBadge, Leaf } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import type { Lead } from "@/lib/types";

interface ReferenceTabProps {
  lead: Lead;
}

const FUNDING_MODELS = [
  {
    name: "CAPITAL EXPENSE",
    paymentFormula: "100% upfront",
    ownership: "Client owns",
    ownershipColor: "cyan",
    seg: "Client claims SEG",
    term: "—",
  },
  {
    name: "FREE INSTALL (PPA)",
    paymentFormula: "£0 capex · pay-per-kWh",
    ownership: "Provider owns",
    ownershipColor: "magenta",
    seg: "Provider claims SEG",
    term: "20–25 yr",
  },
  {
    name: "LEASE PURCHASE",
    paymentFormula: "(capex + interest) ÷ months",
    ownership: "Client owns at end",
    ownershipColor: "cyan",
    seg: "Client claims SEG",
    term: "5–10 yr",
  },
  {
    name: "OPERATIONAL LEASE",
    paymentFormula: "monthly fixed lease",
    ownership: "Provider owns",
    ownershipColor: "magenta",
    seg: "Provider claims SEG",
    term: "5–7 yr",
  },
  {
    name: "HIRE PURCHASE",
    paymentFormula: "deposit + monthly + balloon",
    ownership: "Client owns at end",
    ownershipColor: "cyan",
    seg: "Client claims SEG",
    term: "3–5 yr",
  },
] as const;

function formatGbp(n: number | undefined): string {
  if (n == null) return "—";
  return `£${Math.round(n).toLocaleString("en-GB")}`;
}

export function ReferenceTab({ lead }: ReferenceTabProps) {
  const fin = lead.financial;

  return (
    <div className="space-y-4">
      {/* ROI breakdown */}
      <Card>
        <CardHeader>
          <div className="text-[10px] uppercase tracking-widest text-grid">
            Computed for this lead
          </div>
          <CardTitle className="flex items-center gap-2 font-mono">
            <Coins className="size-4 text-amber" strokeWidth={1.5} />
            ROI BREAKDOWN
          </CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full font-mono text-xs">
            <tbody>
              <tr className="border-b border-iron">
                <td className="py-1.5 text-mute uppercase tracking-wide text-[10px]">CAPEX</td>
                <td className="py-1.5 text-right text-bone">{formatGbp(fin?.capex_gbp)}</td>
              </tr>
              <tr className="border-b border-iron">
                <td className="py-1.5 text-mute uppercase tracking-wide text-[10px]">ANNUAL SAVING</td>
                <td className="py-1.5 text-right text-bone">{formatGbp(fin?.annual_saving_gbp)}</td>
              </tr>
              <tr className="border-b border-iron">
                <td className="py-1.5 text-mute uppercase tracking-wide text-[10px]">PAYBACK</td>
                <td className="py-1.5 text-right text-bone">
                  {fin?.payback_years != null ? `${fin.payback_years.toFixed(1)} yr` : "—"}
                </td>
              </tr>
              <tr>
                <td className="py-1.5 text-mute uppercase tracking-wide text-[10px]">NPV (25 yr)</td>
                <td className="py-1.5 text-right text-emerald">{formatGbp(fin?.npv_25yr_gbp)}</td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Funding options */}
      <Card>
        <CardHeader>
          <div className="text-[10px] uppercase tracking-widest text-grid">
            UK commercial solar · 2026
          </div>
          <CardTitle className="flex items-center gap-2 font-mono">
            <FileBadge className="size-4 text-cyan" strokeWidth={1.5} />
            FUNDING MODELS
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {FUNDING_MODELS.map((m) => (
            <div
              key={m.name}
              className="rounded-[2px] border border-iron bg-app-elev-1 p-2.5"
            >
              <div className="mb-1.5 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-widest text-bone">
                  {m.name}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-widest text-grid">
                  {m.term}
                </span>
              </div>
              <div className="font-mono text-[11px] text-mute">{m.paymentFormula}</div>
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px]">
                <span
                  className={`rounded-[2px] border px-1.5 py-0.5 font-mono uppercase tracking-widest ${
                    m.ownershipColor === "cyan"
                      ? "border-cyan/40 text-cyan"
                      : "border-magenta/40 text-magenta"
                  }`}
                >
                  {m.ownership}
                </span>
                <span className="rounded-[2px] border border-amber/40 px-1.5 py-0.5 font-mono uppercase tracking-widest text-amber">
                  {m.seg}
                </span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Citations */}
      <Card>
        <CardHeader>
          <div className="text-[10px] uppercase tracking-widest text-grid">
            Sources · open data
          </div>
          <CardTitle className="flex items-center gap-2 font-mono">
            <Leaf className="size-4 text-emerald" strokeWidth={1.5} />
            REFERENCES
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1 font-mono text-[11px] text-mute">
            <li>· HM Land Registry · CCOD/OCOD/INSPIRE freehold polygons</li>
            <li>· Companies House · officer + filing data</li>
            <li>· Google Solar API · per-pixel kWh/m²/day flux</li>
            <li>· PVGIS (EU JRC) · solar yield modelling</li>
            <li>· UK SEG export tariff (Ofgem 2026)</li>
            <li>· Ministry of Housing · IMD social-impact index</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
