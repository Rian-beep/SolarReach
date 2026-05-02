import type { FluxOverlay, Lead, PanelLayout } from "@/lib/types";

/**
 * MapSlot — owned by Luke (Google Maps Photorealistic 3D + Solar API).
 * This file is intentionally a STUB. Do not implement Maps logic here.
 *
 * Contract (frozen — see CONTRACTS.md § 4):
 */
export interface MapSlotProps {
  leads: Lead[];
  selectedLeadId: string | null;
  onLeadClick: (id: string) => void;
  fluxOverlay: FluxOverlay | null;
  panelLayout: PanelLayout | null;
}

export function MapSlot(_props: MapSlotProps) {
  return (
    <div className="grid h-full place-items-center bg-app-bg/40 border-2 border-dashed border-gotham-dark/40 rounded-2xl">
      <div className="text-center">
        <div className="text-2xl">🗺️</div>
        <div className="mt-2 font-semibold">Map mounts here</div>
        <div className="text-sm opacity-70">
          Owned by Luke — Google Maps Photorealistic 3D + Solar API
        </div>
      </div>
    </div>
  );
}
