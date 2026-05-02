import { useCameraStore } from "@/stores/useCameraStore";
import { useLeadStore } from "@/stores/useLeadStore";

interface HUDCoordsProps {
  /** Override (rarely used; HUD reads from camera store). */
  lat?: number;
  lng?: number;
  className?: string;
}

export function HUDCoords({ lat, lng, className }: HUDCoordsProps) {
  // ── ALL hooks before any conditional return (cardinal rule) ──────────
  const camLat = useCameraStore((s) => s.lat);
  const camLng = useCameraStore((s) => s.lng);
  const selectedLeadId = useLeadStore((s) => s.selectedLeadId);
  const leads = useLeadStore((s) => s.leads);

  // Priority: explicit prop > live camera > selected lead > "—".
  let latVal: number | undefined = lat ?? camLat ?? undefined;
  let lngVal: number | undefined = lng ?? camLng ?? undefined;
  if (latVal === undefined || lngVal === undefined) {
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
