/**
 * Google Maps Photorealistic 3D Tiles + Solar API canvas.
 *
 * Loads `<gmp-map-3d>` Web Component via the Maps JS SDK (libraries=maps3d, v=alpha)
 * and wires lead markers + per-pixel solar radiance overlay + per-panel polygon layout.
 *
 * Cinematic camera (A8):
 *   - Boot: UK-wide 600km altitude, tilt 30° — communicates "whole UK market".
 *   - First scan completes (leads array first populates) → fly to centroid of
 *     leads (avg lat/lng), range 2000m, tilt 55°. Once per session.
 *   - Lead selected → fly down to building, range 220m, tilt 67°, alt 80m.
 *   - prefers-reduced-motion → snap (no fly), still updates camera state.
 *
 * Marker styling (alpha SDK has no shadow-DOM ::part hooks yet — graceful
 * degrade): we add `data-score-band` (low/mid/high) + `data-selected` to each
 * `<gmp-marker-3d-interactive-element>`. CSS in index.css targets these
 * attribute selectors and styles the marker host element where the SDK lets us.
 *
 * Cardinal rules respected:
 *   - Server-side ray-cast clipping is in the API (not here) — we render whatever
 *     panels are in props.panelLayout.
 *   - Google API key Application restrictions MUST be 'None' or IP allowlist
 *     (NOT HTTP referrer — that breaks server calls from FastAPI to Solar API).
 *   - We DO NOT auto-fire paid APIs from this component; flux/panels come from
 *     props (caller controls invocation via cost-confirm modal).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { Lead, FluxOverlay, PanelLayout } from "@/lib/types";
import type { LayerState } from "@/components/map3d/HUD-LayerToggle";
import { useCameraStore } from "@/stores/useCameraStore";
import { useSearchStore } from "@/stores/useSearchStore";

declare global {
  interface Window {
    __sr_maps_ready?: () => void;
    __sr_maps_loading?: boolean;
    __sr_maps_auth_fail?: () => void;
    gm_authFailure?: () => void;
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
  /**
   * A8 PROPOSAL — additive prop (default preserves prior behaviour: all on
   * except radiance/panels which respect the parent's state if passed).
   * When unset, every overlay is shown (legacy behaviour).
   * See CONTRACTS.md § 4.
   */
  layers?: LayerState;
}

const GOOGLE_MAPS_API_KEY =
  ((import.meta as unknown as { env?: Record<string, string> }).env
    ?.VITE_GOOGLE_MAPS_API_KEY ?? "") as string;

// UK-wide overview camera. Google 3D tiles cap altitude/range around ~25km.
// 8km altitude + 80km range + 35° tilt = aerial 3D "whole UK" framing.
const UK_CENTER = { lat: 54.5, lng: -2.5, alt: 8000 };
const UK_RANGE = 80000;
const UK_TILT = 35; // aerial 3D default — user can two-finger swipe to flatten

// First-scan-complete camera tuning — drop straight to building-level
// oblique view so the user sees actual photorealistic 3D buildings, not
// terrain. 400m range + 67° tilt is "Google Earth aerial of the postcode".
const SCAN_RANGE = 400;
const SCAN_TILT = 67;

// Lead-selected camera tuning — close oblique view of the building.
const LEAD_RANGE = 200;
const LEAD_TILT = 67;
const LEAD_ALT = 60;

// Two-finger swipe → tilt mapping
const TILT_MIN = 0;
const TILT_MAX = 67; // up to fully oblique
const TILT_PER_DELTA_PX = 0.18; // pixels of vertical scroll per degree of tilt

// Animation durations (ms). Linear / ease-out only per Gotham theme.
const FLY_BOOT_TO_SCAN_MS = 1500;
const FLY_SCAN_TO_LEAD_MS = 1200;

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

  // Hide Google's "Using the alpha channel" dev banner — it's injected at
  // body level after the SDK loads. We watch for any node containing the
  // banner text and set display:none on it (and its parent if needed).
  if (typeof MutationObserver !== "undefined") {
    const obs = new MutationObserver((muts) => {
      for (const m of muts) {
        m.addedNodes.forEach((n) => {
          if (!(n instanceof HTMLElement)) return;
          const txt = n.innerText ?? "";
          if (txt.includes("alpha channel of the Google Maps")) {
            n.style.display = "none";
            const parent = n.parentElement;
            if (parent && parent !== document.body) {
              parent.style.display = "none";
            }
          }
        });
      }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    // Auto-disconnect after 30s — banner only appears once per session.
    setTimeout(() => obs.disconnect(), 30000);
  }

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

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

interface FlyToOpts {
  lat: number;
  lng: number;
  alt?: number;
  range: number;
  tilt: number;
  durationMs: number;
}

function flyOrSnap(map: HTMLElement, opts: FlyToOpts) {
  const reduced = prefersReducedMotion();
  const el = map as unknown as {
    flyCameraTo?: (opts: unknown) => void;
    setAttribute: (k: string, v: string) => void;
  };
  if (reduced || typeof el.flyCameraTo !== "function") {
    el.setAttribute(
      "center",
      `${opts.lat}, ${opts.lng}, ${opts.alt ?? 0}`,
    );
    el.setAttribute("range", String(opts.range));
    el.setAttribute("tilt", String(opts.tilt));
    return;
  }
  try {
    el.flyCameraTo({
      endCamera: {
        center: { lat: opts.lat, lng: opts.lng, altitude: opts.alt ?? 0 },
        tilt: opts.tilt,
        range: opts.range,
      },
      durationMillis: opts.durationMs,
    });
  } catch {
    /* graceful degrade */
  }
}

export function MapSlot({
  leads,
  selectedLeadId,
  onLeadClick,
  fluxOverlay,
  panelLayout,
  layers,
}: MapSlotProps) {
  // ── ALL hooks before any conditional return (cardinal rule) ──────────
  const mapRef = useRef<HTMLElement | null>(null);
  const [sdkReady, setSdkReady] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  // Track whether we've performed the boot→scan flyout once. Resets only
  // if leads is cleared back to empty (e.g. reset action).
  const flewToScanRef = useRef(false);

  // Track previous leads.length so we know when leads JUST populated.
  const prevLeadsLenRef = useRef(0);

  // Camera store mutator (HUDs subscribe directly).
  const setCamera = useCameraStore((s) => s.set);

  // Defaults: when `layers` is not provided, treat all as ON (legacy).
  const showPins = layers ? layers.pins : true;
  const showRadiance = layers ? layers.radiance : true;
  const showPanels = layers ? layers.panels : true;
  const showPolygons = layers ? layers.polygons : true;

  // Centroid of currently-loaded leads (for first-scan flyout).
  const centroid = useMemo(() => {
    const pts = leads
      .map((l) => l.geo?.point?.coordinates)
      .filter((c): c is [number, number] => Array.isArray(c) && c.length === 2);
    if (pts.length === 0) return null;
    const sum = pts.reduce(
      (acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }),
      { lng: 0, lat: 0 },
    );
    return { lng: sum.lng / pts.length, lat: sum.lat / pts.length };
  }, [leads]);

  // Load SDK once
  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY) {
      setLoadErr("VITE_GOOGLE_MAPS_API_KEY missing in .env.local");
      return;
    }
    // Google's auth failure callback — fires when the API key is invalid,
    // restricted, or the API is not enabled. Caught BEFORE the SDK throws
    // its generic "didn't load correctly" UI overlay.
    window.gm_authFailure = () => {
      const last4 = GOOGLE_MAPS_API_KEY.slice(-4);
      setLoadErr(
        `gm_authFailure — Google rejected the key (...${last4}). Check GCP console:\n` +
          `  • Map Tiles API: enabled?\n` +
          `  • Maps JavaScript API: enabled?\n` +
          `  • Billing: enabled on the project?\n` +
          `  • Application restrictions: set to None (NOT HTTP referrer)?\n` +
          `  • Photorealistic 3D Tiles: project on the allowlist?`,
      );
    };
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

  // Two-finger swipe (vertical wheel events on Mac trackpads) → adjust tilt.
  // Plain wheel = tilt; Cmd/Ctrl+wheel = native zoom (preserved by stopping
  // event only when no modifier is held).
  useEffect(() => {
    if (!sdkReady || !mapRef.current) return;
    const root = mapRef.current;
    const onWheel = (ev: WheelEvent) => {
      // Let pinch-zoom + Cmd/Ctrl combos fall through to native zoom.
      if (ev.ctrlKey || ev.metaKey) return;
      // Only handle vertical scrolls (two-finger swipe up/down). Horizontal
      // scrolls are left to the SDK.
      if (Math.abs(ev.deltaY) < Math.abs(ev.deltaX)) return;
      ev.preventDefault();
      ev.stopPropagation();
      const m = root as unknown as { tilt?: number };
      const currentTilt = typeof m.tilt === "number" ? m.tilt : UK_TILT;
      // deltaY > 0 (swipe down) = look more down = tilt --
      // deltaY < 0 (swipe up)   = look more oblique = tilt ++
      const next = currentTilt + -ev.deltaY * TILT_PER_DELTA_PX * -1;
      const clamped = Math.max(TILT_MIN, Math.min(TILT_MAX, next));
      (root as unknown as Record<string, unknown>).tilt = clamped;
    };
    root.addEventListener("wheel", onWheel, { passive: false });
    return () => root.removeEventListener("wheel", onWheel);
  }, [sdkReady]);

  // Subscribe to camera changes → push into useCameraStore for HUDs.
  useEffect(() => {
    if (!sdkReady || !mapRef.current) return;
    const root = mapRef.current;
    const handler = () => {
      const m = root as unknown as {
        center?: { lat: number; lng: number };
        range?: number;
        tilt?: number;
        heading?: number;
      };
      // The alpha SDK exposes these as attributes; reading via getAttribute
      // is the most reliable cross-build path.
      const centerStr = root.getAttribute("center");
      const rangeAttr = root.getAttribute("range");
      const tiltAttr = root.getAttribute("tilt");
      const headingAttr = root.getAttribute("heading");
      let lat: number | null = null;
      let lng: number | null = null;
      if (centerStr) {
        const parts = centerStr.split(",").map((s) => parseFloat(s.trim()));
        if (parts.length >= 2 && !Number.isNaN(parts[0]) && !Number.isNaN(parts[1])) {
          lat = parts[0];
          lng = parts[1];
        }
      } else if (m.center) {
        lat = m.center.lat;
        lng = m.center.lng;
      }
      setCamera({
        lat,
        lng,
        range: rangeAttr ? parseFloat(rangeAttr) : (m.range ?? null),
        tilt: tiltAttr ? parseFloat(tiltAttr) : (m.tilt ?? null),
        heading: headingAttr ? parseFloat(headingAttr) : (m.heading ?? null),
      });
    };
    // Seed the store immediately with initial camera.
    handler();
    root.addEventListener("gmp-camerachange", handler);
    return () => root.removeEventListener("gmp-camerachange", handler);
  }, [sdkReady, setCamera]);

  // ── Search target (postcode-typed) → fly directly to that postcode ────
  // Independent of leads — even if 0 leads match the postcode, the camera
  // navigates to where the user pointed. Beats relying on the centroid of
  // the SSE stream which can fire late or empty.
  const searchTarget = useSearchStore((s) => s.target);
  useEffect(() => {
    if (!sdkReady || !mapRef.current || !searchTarget) return;
    flyOrSnap(mapRef.current, {
      lat: searchTarget.lat,
      lng: searchTarget.lng,
      alt: 60,
      range: SCAN_RANGE,
      tilt: SCAN_TILT,
      durationMs: FLY_BOOT_TO_SCAN_MS,
    });
  }, [sdkReady, searchTarget?.postcode, searchTarget?.lat, searchTarget?.lng]);

  // First-scan-complete: leads JUST populated → fly to centroid (once).
  useEffect(() => {
    if (!sdkReady || !mapRef.current) return;
    const prev = prevLeadsLenRef.current;
    const curr = leads.length;
    prevLeadsLenRef.current = curr;
    // Reset the latch if leads is wiped back to zero.
    if (curr === 0) {
      flewToScanRef.current = false;
      return;
    }
    if (
      !flewToScanRef.current &&
      prev === 0 &&
      curr > 0 &&
      centroid &&
      !selectedLeadId
    ) {
      flewToScanRef.current = true;
      flyOrSnap(mapRef.current, {
        lat: centroid.lat,
        lng: centroid.lng,
        range: SCAN_RANGE,
        tilt: SCAN_TILT,
        durationMs: FLY_BOOT_TO_SCAN_MS,
      });
    }
  }, [sdkReady, leads.length, centroid, selectedLeadId]);

  // Camera fly-to selected lead
  useEffect(() => {
    if (!sdkReady || !mapRef.current || !selectedLeadId) return;
    const lead = leads.find((l) => l._id === selectedLeadId);
    const coords = lead?.geo?.point?.coordinates;
    if (!coords) return;
    const [lng, lat] = coords;
    flyOrSnap(mapRef.current, {
      lat,
      lng,
      alt: LEAD_ALT,
      range: LEAD_RANGE,
      tilt: LEAD_TILT,
      durationMs: FLY_SCAN_TO_LEAD_MS,
    });
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
        ref={(el) => {
          mapRef.current = el;
          if (!el) return;
          // Alpha SDK requires JS-property assignment with structured Object
          // values for center/range/tilt — the HTML-attribute form throws
          // `InvalidValueError: Cannot set property "center" ... not an Object`.
          // We deliberately DO NOT set `mode` — the alpha enum is volatile
          // ("hybrid"/"satellite" both rejected on current build); the SDK's
          // default Photorealistic 3D rendering is what we want anyway.
          const m = el as unknown as Record<string, unknown>;
          m.center = {
            lat: UK_CENTER.lat,
            lng: UK_CENTER.lng,
            altitude: UK_CENTER.alt,
          };
          m.range = UK_RANGE;
          m.tilt = UK_TILT;
        }}
        style={{ width: "100%", height: "100%" }}
      >
        {showPins &&
          leads.map((lead) => {
            const c = lead.geo?.point?.coordinates;
            if (!c) return null;
            const [lng, lat] = c;
            const score = lead.scores?.composite_score ?? 0;
            const band = score >= 70 ? "high" : score >= 50 ? "mid" : "low";
            const isSelected = lead._id === selectedLeadId;
            return (
              <gmp-marker-3d-interactive-element
                key={lead._id}
                ref={(el) => {
                  if (!el) return;
                  const mk = el as unknown as Record<string, unknown>;
                  mk.position = { lat, lng, altitude: 30 };
                  mk.altitudeMode = "RELATIVE_TO_GROUND";
                  mk.label = String(score);
                  el.setAttribute("data-lead-id", lead._id);
                  el.setAttribute("data-score-band", band);
                  el.setAttribute("data-selected", isSelected ? "1" : "0");
                }}
              />
            );
          })}

        {/* Per-building radiance overlay — translucent rooftop polygon tinted
            by composite_score. This is the "solar radiance on top of every
            building" feel; pixel-accurate flux is in the drawer. */}
        {showPolygons &&
          leads.map((lead) => {
            const ring = lead.rooftop_polygon?.coordinates?.[0];
            if (!ring || ring.length < 3) return null;
            const score = lead.scores?.composite_score ?? 0;
            // Score → fill / stroke (Gotham-aligned cyan/amber/red, low alpha).
            const fill =
              score >= 70 ? "#20D08240" : score >= 50 ? "#FFB02040" : "#FF475740";
            const stroke =
              score >= 70 ? "#20D082" : score >= 50 ? "#FFB020" : "#FF4757";
            // gmp-polygon-3d-element wants an array of {lat, lng, altitude}.
            const outer = ring.map(([cLng, cLat]) => ({
              lat: cLat,
              lng: cLng,
              altitude: 6,
            }));
            return (
              <gmp-polygon-3d-element
                key={`bldg-${lead._id}`}
                ref={(el) => {
                  if (!el) return;
                  const p = el as unknown as Record<string, unknown>;
                  p.outerCoordinates = outer;
                  p.altitudeMode = "RELATIVE_TO_GROUND";
                  p.fillColor = fill;
                  p.strokeColor = stroke;
                  p.strokeWidth = 1;
                  p.extruded = false;
                  el.setAttribute("data-lead-id", lead._id);
                }}
              />
            );
          })}

        {/* Search target marker — drops at the postcode-typed coordinates
            (postcodes.io geocode), independent of how many leads match.
            Falls back to leads-centroid if the geocode failed. */}
        {(searchTarget || centroid) && (
          <gmp-marker-3d-interactive-element
            key="search-target"
            ref={(el) => {
              if (!el) return;
              const mk = el as unknown as Record<string, unknown>;
              const t = searchTarget ?? centroid!;
              mk.position = {
                lat: t.lat,
                lng: t.lng,
                altitude: 80,
              };
              mk.altitudeMode = "RELATIVE_TO_GROUND";
              mk.label = searchTarget
                ? `◎ ${searchTarget.postcode}`
                : "◎ SCAN TARGET";
              el.setAttribute("data-search-target", "1");
            }}
          />
        )}
      </gmp-map-3d>
    </div>
  );
}
