import { useLeadStore } from "@/stores/useLeadStore";

interface HUDCoordsProps {
  /** Override (e.g. from camera). When unset, falls back to selected lead. */
  lat?: number;
  lng?: number;
  className?: string;
}

export function HUDCoords({ lat, lng, className }: HUDCoordsProps) {
  // All hooks before any conditional return
  const selectedLeadId = useLeadStore((s) => s.selectedLeadId);
  const leads = useLeadStore((s) => s.leads);

  let lngVal = lng;
  let latVal = lat;
  if (lngVal === undefined || latVal === undefined) {
    const selected = leads.find((l) => l._id === selectedLeadId);
    if (selected?.geo?.point?.coordinates) {
      lngVal = selected.geo.point.coordinates[0];
      latVal = selected.geo.point.coordinates[1];
    }
  }

  const fmt = (v: number | undefined) =>
    v === undefined ? "—".padStart(8, " ") : v.toFixed(4).padStart(8, " ");

  return (
    <div
      className={
        "absolute top-3 left-3 z-20 rounded-[2px] border border-iron-bright bg-app-glass backdrop-blur-[2px] px-2 py-1 font-mono text-xs " +
        (className ?? "")
      }
      style={{ backgroundColor: "rgba(10, 14, 20, 0.8)" }}
    >
      <div className="flex items-center gap-3">
        <span className="text-grid uppercase tracking-wide">LAT</span>
        <span className="text-bone tabular-nums">{fmt(latVal)}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-grid uppercase tracking-wide">LNG</span>
        <span className="text-bone tabular-nums">{fmt(lngVal)}</span>
      </div>
    </div>
  );
}
