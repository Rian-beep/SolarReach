export type LayerKey = "pins" | "radiance" | "panels" | "polygons";

export type LayerState = Record<LayerKey, boolean>;

/** Per-layer count of lead-set members carrying useful data. Drives the
 *  ·idle / ·n live hint chips. Polygons + pins are always considered live
 *  (they render off the base lead doc). Radiance/panels light up only when
 *  some lead in the set actually has cached overlay/layout data. */
export type LayerDataCounts = Record<LayerKey, number>;

interface HUDLayerToggleProps {
  state: LayerState;
  onChange: (next: LayerState) => void;
  /** Total leads currently rendered. Used as the denominator on the
   *  `·n/total live` hint, e.g. `·13/264 live` for radiance. */
  totalLeads?: number;
  /** How many leads in the current set actually have data for each
   *  layer. Replaces the previous `hasSelectedLead` gate so the layers
   *  reflect dataset coverage, not the single-selection state. */
  dataAvailable?: LayerDataCounts;
  className?: string;
}

interface LayerDef {
  key: LayerKey;
  label: string;
  hint: string;
  needsLead: boolean;
}

const LAYERS: LayerDef[] = [
  { key: "pins", label: "PINS", hint: "lead markers", needsLead: false },
  {
    key: "polygons",
    label: "ROOFS",
    hint: "rooftop tint by score",
    needsLead: false,
  },
  {
    key: "radiance",
    label: "RADIANCE",
    hint: "Solar API flux PNG HUD",
    needsLead: true,
  },
  {
    key: "panels",
    label: "PANELS",
    hint: "per-panel layout",
    needsLead: true,
  },
];

export function HUDLayerToggle({
  state,
  onChange,
  totalLeads = 0,
  dataAvailable,
  className,
}: HUDLayerToggleProps) {
  return (
    <div
      className={
        "pointer-events-auto absolute bottom-3 right-3 z-30 rounded-[2px] border border-iron-bright px-2.5 py-2 font-mono text-xs " +
        "shadow-[0_0_24px_-4px_rgba(0,0,0,0.9)] " +
        (className ?? "")
      }
      // Solid app-surface bg — must read against bright photorealistic
      // imagery (sun-lit white buildings) without losing contrast.
      style={{ backgroundColor: "#0A0E14F5" }}
    >
      <div className="text-cyan uppercase tracking-widest mb-1.5 text-[10px]">
        LAYERS
      </div>
      <div className="flex flex-col gap-0.5">
        {LAYERS.map((l) => {
          const on = state[l.key];
          // Per-layer data coverage. Lead-dependent layers (radiance/panels)
          // show ·n/total live when data exists, ·idle otherwise. Always-on
          // layers (pins/polygons) suppress the hint entirely.
          const count = dataAvailable?.[l.key] ?? 0;
          const showCount = l.needsLead && count > 0;
          const showIdle = l.needsLead && count === 0;
          return (
            <label
              key={l.key}
              className="flex items-center gap-2 select-none cursor-pointer rounded-[2px] px-1 py-0.5 transition-colors duration-[80ms] hover:bg-app-elev-1"
            >
              <span
                className={
                  "inline-flex size-3.5 shrink-0 items-center justify-center border text-[10px] leading-none " +
                  (on
                    ? "border-cyan bg-cyan/30 text-cyan"
                    : "border-iron-bright text-dim")
                }
                aria-hidden
              >
                {on ? "✕" : ""}
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
                  "flex-1 uppercase tracking-wide " +
                  (on ? "text-bone" : "text-mute")
                }
              >
                {l.label}
              </span>
              {showCount && (
                <span
                  className="text-[9px] uppercase tracking-widest text-cyan tabular-nums"
                  title={`${count} of ${totalLeads} leads carry data for this layer`}
                >
                  ·{count}/{totalLeads} live
                </span>
              )}
              {showIdle && (
                <span
                  className="text-[9px] uppercase tracking-widest text-grid"
                  title="no leads in the current set carry data for this layer yet"
                >
                  ·idle
                </span>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}
