export type LayerKey = "pins" | "radiance" | "panels" | "polygons";

export type LayerState = Record<LayerKey, boolean>;

interface HUDLayerToggleProps {
  state: LayerState;
  onChange: (next: LayerState) => void;
  /** When false, lead-dependent layers (radiance/panels) hint that they
   *  need a lead selection — but stay clickable. */
  hasSelectedLead?: boolean;
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
  hasSelectedLead = false,
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
          const ghost = l.needsLead && !hasSelectedLead;
          // Lead-required layers stay CLICKABLE even without a lead — the
          // hint just notes when they'll have data to show.
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
              {ghost && (
                <span
                  className="text-[9px] uppercase tracking-widest text-grid"
                  title="select a lead to populate this layer"
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
