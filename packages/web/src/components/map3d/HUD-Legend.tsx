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
          // Inferno colormap (matches the per-pixel flux PNG and the
          // per-building rooftop tints). Purple → red → orange → yellow.
          background:
            "linear-gradient(to right, #000004 0%, #420A68 22%, #932667 45%, #DD513A 65%, #F37819 82%, #FCA40D 92%, #FCFFA4 100%)",
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
