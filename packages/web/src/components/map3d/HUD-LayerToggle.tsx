export type LayerKey = "pins" | "radiance" | "panels" | "polygons";

export type LayerState = Record<LayerKey, boolean>;

interface HUDLayerToggleProps {
  state: LayerState;
  onChange: (next: LayerState) => void;
  className?: string;
}

const LAYERS: { key: LayerKey; label: string }[] = [
  { key: "pins", label: "PINS" },
  { key: "radiance", label: "RADIANCE" },
  { key: "panels", label: "PANELS" },
  { key: "polygons", label: "POLYGONS" },
];

export function HUDLayerToggle({
  state,
  onChange,
  className,
}: HUDLayerToggleProps) {
  return (
    <div
      className={
        "absolute bottom-3 right-3 z-20 rounded-[2px] border border-iron-bright px-2 py-1.5 font-mono text-xs " +
        (className ?? "")
      }
      style={{ backgroundColor: "rgba(10, 14, 20, 0.8)" }}
    >
      <div className="text-grid uppercase tracking-wide mb-1">LAYERS</div>
      <div className="flex flex-col gap-px">
        {LAYERS.map((l) => {
          const on = state[l.key];
          return (
            <label
              key={l.key}
              className="flex items-center gap-2 cursor-pointer select-none px-1 py-0.5 hover:bg-app-elev-1 transition-colors duration-[80ms]"
            >
              <span
                className={
                  "inline-flex size-3 items-center justify-center border " +
                  (on
                    ? "border-cyan bg-cyan/20 text-cyan"
                    : "border-iron text-dim")
                }
                aria-hidden
              >
                {on ? "x" : ""}
              </span>
              <input
                type="checkbox"
                checked={on}
                onChange={(e) =>
                  onChange({ ...state, [l.key]: e.target.checked })
                }
                className="sr-only"
              />
              <span
                className={
                  "uppercase tracking-wide " + (on ? "text-bone" : "text-dim")
                }
              >
                {l.label}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
