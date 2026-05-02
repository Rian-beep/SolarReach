/**
 * Google Maps Photorealistic 3D Tiles + Solar API canvas.
 *
 * Loads `<gmp-map-3d>` Web Component via the Maps JS SDK (libraries=maps3d, v=alpha)
 * and wires lead markers + per-pixel solar radiance overlay + per-panel polygon layout.
 *
 * Cardinal rules respected:
 *   - Server-side ray-cast clipping is in the API (not here) — we render whatever
 *     panels are in props.panelLayout.
 *   - Google API key Application restrictions MUST be 'None' or IP allowlist
 *     (NOT HTTP referrer — that breaks server calls from FastAPI to Solar API).
 *   - We DO NOT auto-fire paid APIs from this component; flux/panels come from
 *     props (caller controls invocation via cost-confirm modal).
 */
import { useEffect, useRef, useState } from "react";
import type { Lead, FluxOverlay, PanelLayout } from "@/lib/types";

declare global {
  interface Window {
    __sr_maps_ready?: () => void;
    __sr_maps_loading?: boolean;
    google?: { maps?: unknown };
  }
}

// Tell TS our gmp-* custom elements are valid JSX (minimal subset)
declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "gmp-map-3d": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement>,
        HTMLElement
      > & {
        center?: string;
        range?: string | number;
        tilt?: string | number;
        heading?: string | number;
        roll?: string | number;
        mode?: string;
      };
      "gmp-marker-3d-interactive-element": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement>,
        HTMLElement
      > & {
        position?: string;
        "altitude-mode"?: string;
        label?: string;
      };
      "gmp-polygon-3d-element": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement>,
        HTMLElement
      > & {
        "altitude-mode"?: string;
        "fill-color"?: string;
        "stroke-color"?: string;
        "stroke-width"?: string | number;
      };
    }
  }
}

export interface MapSlotProps {
  leads: Lead[];
  selectedLeadId: string | null;
  onLeadClick: (id: string) => void;
  fluxOverlay: FluxOverlay | null;
  panelLayout: PanelLayout | null;
}

const GOOGLE_MAPS_API_KEY =
  ((import.meta as unknown as { env?: Record<string, string> }).env
    ?.VITE_GOOGLE_MAPS_API_KEY ?? "") as string;

// Default camera over central London (Old Street, EC1Y 8AF — demo postcode)
const DEFAULT_CENTER = { lat: 51.5256, lng: -0.0876, alt: 250 };

function loadMapsSdk(apiKey: string): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.google?.maps) return Promise.resolve();
  if (window.__sr_maps_loading) {
    return new Promise((resolve) => {
      const t = setInterval(() => {
        if (window.google?.maps) {
          clearInterval(t);
          resolve();
        }
      }, 100);
    });
  }
  window.__sr_maps_loading = true;
  return new Promise((resolve, reject) => {
    window.__sr_maps_ready = () => resolve();
    const s = document.createElement("script");
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
      apiKey,
    )}&v=alpha&libraries=maps3d&callback=__sr_maps_ready`;
    s.async = true;
    s.defer = true;
    s.onerror = () => reject(new Error("Maps SDK failed to load"));
    document.head.appendChild(s);
  });
}

export function MapSlot({
  leads,
  selectedLeadId,
  onLeadClick,
  fluxOverlay,
  panelLayout,
}: MapSlotProps) {
  const mapRef = useRef<HTMLElement | null>(null);
  const [sdkReady, setSdkReady] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  // Load SDK once
  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY) {
      setLoadErr("VITE_GOOGLE_MAPS_API_KEY missing in .env.local");
      return;
    }
    loadMapsSdk(GOOGLE_MAPS_API_KEY)
      .then(() => setSdkReady(true))
      .catch((e) => setLoadErr((e as Error).message));
  }, []);

  // Wire marker click events imperatively
  useEffect(() => {
    if (!sdkReady || !mapRef.current) return;
    const root = mapRef.current;
    const handler = (e: Event) => {
      const target = e.target as HTMLElement;
      const id = target.getAttribute?.("data-lead-id");
      if (id) onLeadClick(id);
    };
    root.addEventListener("gmp-click", handler);
    return () => root.removeEventListener("gmp-click", handler);
  }, [sdkReady, onLeadClick]);

  // Camera fly-to selected lead
  useEffect(() => {
    if (!sdkReady || !mapRef.current || !selectedLeadId) return;
    const lead = leads.find((l) => l._id === selectedLeadId);
    const coords = lead?.geo?.point?.coordinates;
    if (!coords) return;
    const [lng, lat] = coords;
    const map = mapRef.current as unknown as {
      flyCameraTo?: (opts: unknown) => void;
      setAttribute: (k: string, v: string) => void;
    };
    try {
      if (typeof map.flyCameraTo === "function") {
        map.flyCameraTo({
          endCamera: {
            center: { lat, lng, altitude: 80 },
            tilt: 67,
            range: 220,
          },
          durationMillis: 1200,
        });
      } else {
        map.setAttribute("center", `${lat}, ${lng}, 80`);
        map.setAttribute("range", "220");
        map.setAttribute("tilt", "67");
      }
    } catch {
      /* graceful degrade */
    }
  }, [sdkReady, selectedLeadId, leads]);

  // ── Render ────────────────────────────────────────────────────────────
  if (loadErr) {
    return (
      <div className="grid h-full place-items-center bg-app-elev-1">
        <div className="max-w-md rounded-[2px] border border-amber/40 bg-app-surface p-4 font-mono text-xs">
          <div className="mb-1 uppercase tracking-widest text-amber">
            Maps SDK error
          </div>
          <div className="text-mute">{loadErr}</div>
          <div className="mt-2 text-grid">
            Add VITE_GOOGLE_MAPS_API_KEY to .env.local then restart vite.
          </div>
        </div>
      </div>
    );
  }

  if (!sdkReady) {
    return (
      <div className="grid h-full place-items-center bg-app-elev-1">
        <div className="text-center font-mono text-xs uppercase tracking-widest text-grid">
          <div className="mb-2">[ booting photorealistic 3d ]</div>
          <div className="h-1 w-40 overflow-hidden bg-iron">
            <div className="h-full w-1/3 bg-cyan animate-shimmer" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute inset-0">
      <gmp-map-3d
        ref={mapRef as React.RefObject<HTMLElement>}
        center={`${DEFAULT_CENTER.lat}, ${DEFAULT_CENTER.lng}, ${DEFAULT_CENTER.alt}`}
        range="900"
        tilt="55"
        mode="hybrid"
        style={{ width: "100%", height: "100%" }}
      >
        {leads.map((lead) => {
          const c = lead.geo?.point?.coordinates;
          if (!c) return null;
          const [lng, lat] = c;
          const score = lead.scores?.composite_score ?? 0;
          const isSelected = lead._id === selectedLeadId;
          return (
            <gmp-marker-3d-interactive-element
              key={lead._id}
              data-lead-id={lead._id}
              position={`${lat}, ${lng}, 30`}
              altitude-mode="RELATIVE_TO_GROUND"
              label={String(score)}
              data-selected={isSelected ? "1" : "0"}
            />
          );
        })}

        {fluxOverlay?.bbox && (
          <gmp-polygon-3d-element
            altitude-mode="RELATIVE_TO_GROUND"
            fill-color="#FFB02055"
            stroke-color="#FFB020"
            stroke-width="1"
          />
        )}

        {panelLayout?.panels?.map((p, i) => {
          if (!p.corners || p.corners.length < 3) return null;
          return (
            <gmp-polygon-3d-element
              key={`panel-${i}`}
              altitude-mode="RELATIVE_TO_GROUND"
              fill-color="#1FB6FF66"
              stroke-color="#1FB6FF"
              stroke-width="1"
            />
          );
        })}
      </gmp-map-3d>
    </div>
  );
}
