import { useState } from "react";
import { INDUSTRY_BENCHMARKS } from "@/lib/industry_benchmarks";

interface HUDBenchmarksProps {
  className?: string;
}

interface BenchmarkRow {
  label: string;
  value: string;
  hint?: string;
}

const ROWS: readonly BenchmarkRow[] = [
  {
    label: "INSTALL £/kW",
    value: `£${INDUSTRY_BENCHMARKS.uk_install_cost_per_kw_gbp.toFixed(0)}`,
    hint: `range £${INDUSTRY_BENCHMARKS.uk_install_cost_per_kw_range_gbp[0]}–£${INDUSTRY_BENCHMARKS.uk_install_cost_per_kw_range_gbp[1]} · UK 2025`,
  },
  {
    label: "PAYBACK",
    value: `${INDUSTRY_BENCHMARKS.uk_typical_payback_years_commercial.toFixed(1)} yr`,
    hint: "UK commercial median, capex model",
  },
  {
    label: "SEG EXPORT",
    value: `${(INDUSTRY_BENCHMARKS.seg_export_rate_gbp_per_kwh * 100).toFixed(1)}p/kWh`,
    hint: "best-available SEG tariff 2025-26",
  },
  {
    label: "GRID CO₂",
    value: `${INDUSTRY_BENCHMARKS.co2_kg_per_kwh_uk_2025.toFixed(3)} kg/kWh`,
    hint: "BEIS / DESNZ 2025 grid intensity",
  },
];

/** Compact benchmarks chip — sits below SCALE on the right column.
 *  Click to expand → 4-row table of UK industry reference numbers
 *  (install £/kW · payback · SEG rate · grid CO₂). All values come from
 *  the shared `industry_benchmarks` module so HUD copy can never drift
 *  from what the deck generator cites. */
export function HUDBenchmarks({ className }: HUDBenchmarksProps) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className={
        "absolute top-[68px] right-3 z-20 font-mono text-xs " + (className ?? "")
      }
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label="Toggle UK solar industry benchmarks"
        className={
          "rounded-[2px] border border-iron-bright px-2 py-1 transition-colors duration-[80ms] " +
          (open ? "bg-app-elev-1 text-bone" : "text-grid hover:text-bone")
        }
        style={{ backgroundColor: "rgba(10, 14, 20, 0.85)" }}
      >
        <span className="uppercase tracking-wide">BENCHMARKS</span>
        <span className="ml-2 text-cyan tabular-nums" aria-hidden>
          {open ? "−" : "+"}
        </span>
      </button>

      {open && (
        <div
          className="mt-1 rounded-[2px] border border-iron-bright px-2.5 py-2 shadow-[0_0_24px_-4px_rgba(0,0,0,0.9)]"
          style={{ backgroundColor: "rgba(10, 14, 20, 0.92)" }}
          role="region"
          aria-label="UK solar industry benchmarks"
        >
          <div className="text-cyan uppercase tracking-widest mb-1.5 text-[10px]">
            UK SOLAR · 2025
          </div>
          <table className="w-[200px] border-separate border-spacing-y-0.5">
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.label}>
                  <td className="pr-2 align-top text-grid uppercase tracking-wide whitespace-nowrap">
                    {r.label}
                  </td>
                  <td
                    className="text-bone tabular-nums text-right whitespace-nowrap"
                    title={r.hint}
                  >
                    {r.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-1.5 pt-1 border-t border-iron-bright text-[9px] text-dim uppercase tracking-widest">
            shared/industry_benchmarks
          </div>
        </div>
      )}
    </div>
  );
}
