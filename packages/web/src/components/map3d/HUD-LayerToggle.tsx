export type LayerKey = "pins" | "radiance" | "panels" | "polygons";

export type LayerState = Record<LayerKey, boolean>;

interface HUDLayerToggleProps {
  state: LayerState;
  onChange: (next: LayerState) => void;
  /** When false, lead-dependent layers (radiance/panels/polygons) are
   *  disabled and grayed out — pins remains live. */
  hasSelectedLead?: boolean;
  className?: string;
}

const LAYERS: { key: LayerKey; label: string; needsLead: boolean }[] = [
  { key: "pins", label: "PINS", needsLead: false },
  { key: "radiance", label: "RADIANCE", needsLead: true },
  { key: "panels", label: "PANELS", needsLead: true },
  { key: "polygons", label: "POLYGONS", needsLead: true },
];

export function HUDLayerToggle({
  state,
  onChange,
  hasSelectedLead = false,
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
          const disabled = l.needsLead && !hasSelectedLead;
          return (
            <label
              key={l.key}
              aria-disabled={disabled}
              className={
                "flex items-center gap-2 select-none px-1 py-0.5 transition-colors duration-[80ms] " +
                (disabled
                  ? "cursor-not-allowed opacity-50"
                  : "cursor-pointer hover:bg-app-elev-1")
              }
            >
              <span
                className={
                  "inline-flex size-3 items-center justify-center border " +
                  (disabled
                    ? "border-iron text-grid"
                    : on
                      ? "border-cyan bg-cyan/20 text-cyan"
                      : "border-iron text-dim")
                }
                aria-hidden
              >
                {on && !disabled ? "x" : ""}
              </span>
              <input
                type="checkbox"
                checked={on}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ ...state, [l.key]: e.target.checked })
                }
                className="sr-only"
              />
              <span
                className={
                  "uppercase tracking-wide " +
                  (disabled ? "text-grid" : on ? "text-bone" : "text-dim")
                }
              >
                {l.label}
              </span>
            </label>
          );
        })}
        {!hasSelectedLead && (
          <div className="mt-1 border-t border-iron-grid pt-1 text-grid uppercase tracking-wide">
            select a lead
          </div>
        )}
      </div>
    </div>
  );
}
