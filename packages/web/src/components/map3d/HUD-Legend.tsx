interface HUDLegendProps {
  vmin?: number;
  vmax?: number;
  className?: string;
}

export function HUDLegend({ vmin = 1.5, vmax = 5.5, className }: HUDLegendProps) {
  return (
    <div
      className={
        "absolute bottom-3 left-3 z-20 rounded-[2px] border border-iron-bright px-2 py-1.5 font-mono text-xs " +
        (className ?? "")
      }
      style={{ backgroundColor: "rgba(10, 14, 20, 0.8)" }}
    >
      <div className="text-grid uppercase tracking-wide mb-1">
        RADIANCE kWh/m²·day
      </div>
      <div
        className="h-2 w-32 rounded-[1px] mb-1"
        style={{
          background:
            "linear-gradient(to right, #1FB6FF 0%, #FFB020 50%, #F040C0 100%)",
        }}
      />
      <div className="flex items-center justify-between text-dim tabular-nums">
        <span>{vmin.toFixed(1)}</span>
        <span>{((vmin + vmax) / 2).toFixed(1)}</span>
        <span>{vmax.toFixed(1)}</span>
      </div>
    </div>
  );
}
