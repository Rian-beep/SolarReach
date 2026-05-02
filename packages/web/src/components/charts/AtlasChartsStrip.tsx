import { useState } from "react";
import { BarChart3, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

const CHARTS = [
  { key: "leads-by-score", label: "LEADS BY SCORE" },
  { key: "score-distribution", label: "SCORE DISTRIBUTION" },
  { key: "spend-over-time", label: "SPEND OVER TIME" },
  { key: "pipeline-funnel", label: "PIPELINE FUNNEL" },
] as const;

export function AtlasChartsStrip() {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-iron bg-app-surface">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2 text-mute hover:text-bone transition-colors duration-[80ms]"
      >
        <span className="flex items-center gap-2 font-mono text-xs uppercase tracking-wide">
          <BarChart3 className="size-3.5" strokeWidth={1.5} />
          ATLAS CHARTS
        </span>
        <span className="flex items-center gap-1 font-mono text-xs text-dim">
          {open ? "COLLAPSE" : "EXPAND"}
          {open ? (
            <ChevronDown className="size-3.5" strokeWidth={1.5} />
          ) : (
            <ChevronRight className="size-3.5" strokeWidth={1.5} />
          )}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {CHARTS.map((c) => (
              <Card key={c.key}>
                <CardHeader className="pb-1">
                  <CardTitle>{c.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-24 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
          <p className="mt-2 font-mono text-xs text-grid uppercase tracking-wide">
            // atlas charts iframe wires post-mongo-config
          </p>
        </div>
      )}
    </div>
  );
}
