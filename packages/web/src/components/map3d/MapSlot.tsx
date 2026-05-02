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
 * `<gmp-marker-3d-interactive>`. CSS in index.css targets these
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
      "gmp-marker-3d-interactive": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement>,
        HTMLElement
      > & {
        position?: string;
        "altitude-mode"?: string;
        label?: string;
      };
      "gmp-polygon-3d": React.DetailedHTMLProps<
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

  // Latch initial camera set so the ref callback doesn't keep resetting
  // center/range/tilt on every render (which would stomp the search-fly,
  // lead-fly, and user gesture moves).
  const initialCameraSetRef = useRef(false);

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

  // Wire marker click events imperatively.
  //
  // The alpha SDK fires `gmp-click` on the host map element BUT the
  // `event.target` is often the inner shadow-DOM child of the marker
  // (the SDK's pin sprite element), NOT the `<gmp-marker-3d-interactive>`
  // host that carries `data-lead-id`. Walking `composedPath()` retargets
  // the click to the first ancestor — across shadow boundaries — that
  // actually carries the lead id. `closest('[data-lead-id]')` would not
  // cross shadow roots so we cannot rely on it here.
  useEffect(() => {
    if (!sdkReady || !mapRef.current) return;
    const root = mapRef.current;
    const handler = (e: Event) => {
      const path = (e as Event & { composedPath?: () => EventTarget[] })
        .composedPath?.() ?? [];
      let id: string | null = null;
      for (const node of path) {
        if (
          node instanceof HTMLElement &&
          node.hasAttribute?.("data-lead-id")
        ) {
          id = node.getAttribute("data-lead-id");
          break;
        }
      }
      // Fallback for browsers without composedPath (older WebViews).
      if (!id) {
        const target = e.target as HTMLElement | null;
        id = target?.getAttribute?.("data-lead-id") ?? null;
      }
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

  // Resolve the flux PNG URL — handler returns "/static/flux/<id>.png"
  // (relative to API_BASE) so we need the absolute form for an <img src>.
  const fluxImgUrl = useMemo(() => {
    if (!fluxOverlay?.url) return null;
    if (fluxOverlay.url.startsWith("http")) return fluxOverlay.url;
    const apiBase =
      ((import.meta as unknown as { env?: Record<string, string> }).env
        ?.VITE_API_BASE ?? "http://localhost:8000") as string;
    return `${apiBase}${fluxOverlay.url}`;
  }, [fluxOverlay?.url]);

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
      {/* Live Solar Radiance HUD — appears when a lead is selected and the
          flux PNG has been auto-fetched. Floats above the 3D scene at the
          bottom-center, mono caption, inferno-gradient legend, dismissable
          via the layer toggle. */}
      {showRadiance && fluxImgUrl && (
        <div className="pointer-events-none absolute bottom-3 left-1/2 z-20 w-[300px] -translate-x-1/2 select-none rounded-[2px] border border-iron-bright bg-app-surface/90 p-2 backdrop-blur-sm">
          <div className="mb-1 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest">
            <span className="flex items-center gap-1.5 text-cyan">
              <span className="size-1.5 rounded-full bg-cyan animate-live-dot" />
              LIVE · GOOGLE SOLAR API
            </span>
            <span className="text-grid">RADIANCE</span>
          </div>
          <img
            src={fluxImgUrl}
            alt="Solar radiance"
            className="block h-32 w-full rounded-[2px] border border-iron object-cover"
          />
          <div className="mt-1 flex justify-between font-mono text-[10px] uppercase tracking-widest text-mute">
            <span>{(fluxOverlay?.vmin ?? 0).toFixed(0)} kWh/m²/yr</span>
            <span className="text-grid">annualFluxUrl</span>
            <span>{(fluxOverlay?.vmax ?? 0).toFixed(0)}</span>
          </div>
        </div>
      )}

      <gmp-map-3d
        ref={(el) => {
          mapRef.current = el;
          if (!el) return;
          // Set initial camera + mode ONCE per element, but ONLY after
          // customElements.whenDefined() resolves — the alpha SDK upgrades
          // gmp-map-3d via dynamic library import and the ref callback
          // can fire before that's done. Setting properties pre-upgrade
          // silently no-ops (the element is the un-upgraded HTMLElement).
          if (initialCameraSetRef.current) return;

          const applyInit = () => {
            if (initialCameraSetRef.current) return;
            const m = el as unknown as Record<string, unknown>;
            m.center = {
              lat: UK_CENTER.lat,
              lng: UK_CENTER.lng,
              altitude: UK_CENTER.alt,
            };
            m.range = UK_RANGE;
            m.tilt = UK_TILT;
            // HYBRID = Photorealistic 3D + labels (essential — without this
            // the SDK falls back to ROADMAP flat vector view).
            const g = (window as unknown as {
              google?: {
                maps?: { maps3d?: { MapMode?: Record<string, unknown> } };
              };
            }).google;
            const MapMode = g?.maps?.maps3d?.MapMode;
            if (MapMode && typeof MapMode.HYBRID !== "undefined") {
              m.mode = MapMode.HYBRID;
            }
            // Verify mode actually took. ROADMAP = the property assignment
            // happened before customElements.define ran. Retry next tick.
            if ((m.mode as string) === "ROADMAP" || m.mode == null) {
              setTimeout(applyInit, 50);
              return;
            }
            initialCameraSetRef.current = true;
          };

          if (window.customElements?.whenDefined) {
            window.customElements
              .whenDefined("gmp-map-3d")
              .then(applyInit)
              .catch(() => applyInit());
          } else {
            applyInit();
          }
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
            const owner = lead.owner?.company_name ?? "—";
            const ownerShort =
              owner.length > 22 ? owner.slice(0, 21) + "…" : owner;
            const labelText = `${score} · ${ownerShort}`;
            return (
              <gmp-marker-3d-interactive
                key={lead._id}
                ref={(el) => {
                  if (!el) return;
                  // Same upgrade-timing race that hits gmp-map-3d also hits
                  // the marker element: the alpha SDK upgrades the custom
                  // element via dynamic library import, and the React ref
                  // callback can fire BEFORE the upgrade resolves. Setting
                  // `position`/`altitudeMode`/etc on an un-upgraded
                  // HTMLElement silently no-ops (the property setters aren't
                  // installed yet), leaving the marker invisible. Defer via
                  // customElements.whenDefined so we set props on the
                  // upgraded element. Attributes (data-*) we set immediately
                  // so click resolution + CSS selectors work even pre-upgrade.
                  el.setAttribute("data-lead-id", lead._id);
                  el.setAttribute("data-score-band", band);
                  el.setAttribute("data-selected", isSelected ? "1" : "0");

                  const applyProps = () => {
                    const mk = el as unknown as Record<string, unknown>;
                    // Altitude 60m: above most low/mid buildings, below
                    // tower-block tops. extruded=true draws a stem to ground.
                    // The marker chip itself renders the SDK's default pin
                    // sprite (NOT just the label) — clearly visible.
                    mk.position = { lat, lng, altitude: 60 };
                    mk.altitudeMode = "RELATIVE_TO_GROUND";
                    mk.extruded = true;
                    mk.label = labelText;
                  };

                  if (window.customElements?.whenDefined) {
                    window.customElements
                      .whenDefined("gmp-marker-3d-interactive")
                      .then(applyProps)
                      .catch(() => applyProps());
                  } else {
                    applyProps();
                  }
                }}
              />
            );
          })}

        {/* Per-building radiance overlay — translucent rooftop polygon tinted
            by composite_score on a TRUE INFERNO gradient (purple → red →
            orange → yellow). Matches the per-pixel flux PNG colormap so
            the polygons read as 'how much radiance hits this roof' instead
            of arbitrary brand colours. Selected lead = brighter alpha so
            it pops while neighbouring buildings still tell the heat story.

            When RADIANCE is toggled on AND the lead carries cached
            flux_overlay vmin/vmax, we lift the band one stop towards the
            yellow end proportional to the flux dynamic range — so leads
            with real Solar API data visibly burn brighter than score-only
            neighbours. Falls back to score-only when flux data is absent. */}
        {showPolygons &&
          leads.map((lead) => {
            const ring = lead.rooftop_polygon?.coordinates?.[0];
            if (!ring || ring.length < 3) return null;
            const score = lead.scores?.composite_score ?? 0;
            const isSelected = lead._id === selectedLeadId;
            // Inferno stops (matplotlib-aligned). Higher score = brighter heat.
            // Selected lead uses CC alpha (80%); others use B0 (~70%) so the
            // demo audience can see the radiance grid even without a click.
            const aSel = "DD";
            const aIdle = "B0";
            const a = isSelected ? aSel : aIdle;
            // Flux brightness boost: (vmax - vmin) / vmax → 0..1 dynamic
            // range. We bucket into 3 boost levels so the inferno band
            // shifts deterministically and the audience sees a clear
            // brightness step instead of an imperceptible alpha tweak.
            const fx = lead.flux_overlay;
            const hasFlux = !!(showRadiance && fx?.vmax && fx.vmax > 0);
            let boost = 0;
            if (hasFlux) {
              const vmin = fx?.vmin ?? 0;
              const vmax = fx?.vmax ?? 1;
              const range = Math.max(0, (vmax - vmin) / vmax);
              boost = range >= 0.66 ? 2 : range >= 0.33 ? 1 : 0;
            }
            // Effective score = composite + flux boost (each step = one
            // inferno band brighter, capped at the top stop).
            const effective = Math.min(100, score + boost * 15);
            let fill: string;
            let stroke: string;
            if (effective >= 80) {
              fill = `#FCFFA4${a}`; // pale yellow — peak radiance
              stroke = "#FCA40D";
            } else if (effective >= 65) {
              fill = `#F37819${a}`; // orange
              stroke = "#F37819";
            } else if (effective >= 50) {
              fill = `#DD513A${a}`; // red-orange
              stroke = "#DD513A";
            } else if (effective >= 35) {
              fill = `#932667${a}`; // magenta
              stroke = "#932667";
            } else {
              fill = `#420A68${a}`; // deep purple — low radiance
              stroke = "#420A68";
            }
            // gmp-polygon-3d wants an array of {lat, lng, altitude}.
            // RELATIVE_TO_MESH: altitude is offset from the underlying 3D
            // mesh surface (i.e. directly on building rooftops). Altitude 2
            // sits just barely above the mesh so the tint paints on the
            // actual roof without z-fighting.
            const outer = ring.map(([cLng, cLat]) => ({
              lat: cLat,
              lng: cLng,
              altitude: 2,
            }));
            return (
              <gmp-polygon-3d
                key={`bldg-${lead._id}`}
                ref={(el) => {
                  if (!el) return;
                  const p = el as unknown as Record<string, unknown>;
                  p.outerCoordinates = outer;
                  // Prefer RELATIVE_TO_MESH when the alpha SDK exposes it
                  // (clamps to building mesh). Fall back to CLAMP_TO_MESH
                  // then RELATIVE_TO_GROUND for older SDK builds.
                  const AltMode = (window as unknown as {
                    google?: {
                      maps?: { maps3d?: { AltitudeMode?: Record<string, unknown> } };
                    };
                  }).google?.maps?.maps3d?.AltitudeMode;
                  p.altitudeMode =
                    AltMode && typeof AltMode.RELATIVE_TO_MESH !== "undefined"
                      ? "RELATIVE_TO_MESH"
                      : AltMode && typeof AltMode.CLAMP_TO_MESH !== "undefined"
                        ? "CLAMP_TO_MESH"
                        : "RELATIVE_TO_GROUND";
                  p.fillColor = fill;
                  p.strokeColor = stroke;
                  p.strokeWidth = 2;
                  p.extruded = false;
                  el.setAttribute("data-lead-id", lead._id);
                }}
              />
            );
          })}

        {/* Per-panel cyan polygons — only when PANELS layer toggled on AND
            the selected lead has a clipped panel layout from Solar API.
            RELATIVE_TO_MESH altitude 5: stacks 5m above the rooftop mesh
            so panels visibly sit on top of the radiance tint (which sits
            at +2m above the mesh). Panel fill solid-cyan so they read as
            engineered hardware. */}
        {showPanels &&
          panelLayout?.panels?.map((p, i) => {
            if (!p.corners || p.corners.length < 3) return null;
            const outer = p.corners.map(([cLng, cLat]) => ({
              lat: cLat,
              lng: cLng,
              altitude: 5, // 3m above the radiance polygon (+2m), on rooftop mesh
            }));
            return (
              <gmp-polygon-3d
                key={`panel-${selectedLeadId}-${i}`}
                ref={(el) => {
                  if (!el) return;
                  const pp = el as unknown as Record<string, unknown>;
                  pp.outerCoordinates = outer;
                  const AltMode = (window as unknown as {
                    google?: {
                      maps?: { maps3d?: { AltitudeMode?: Record<string, unknown> } };
                    };
                  }).google?.maps?.maps3d?.AltitudeMode;
                  pp.altitudeMode =
                    AltMode && typeof AltMode.RELATIVE_TO_MESH !== "undefined"
                      ? "RELATIVE_TO_MESH"
                      : AltMode && typeof AltMode.CLAMP_TO_MESH !== "undefined"
                        ? "CLAMP_TO_MESH"
                        : "RELATIVE_TO_GROUND";
                  pp.fillColor = "#1FB6FFD0"; // cyan, ~80% opaque
                  pp.strokeColor = "#0891B2"; // deeper cyan stroke
                  pp.strokeWidth = 1;
                }}
              />
            );
          })}

        {/* Search target marker — drops at the postcode-typed coordinates
            (postcodes.io geocode), independent of how many leads match.
            Falls back to leads-centroid if the geocode failed. */}
        {(searchTarget || centroid) && (
          <gmp-marker-3d-interactive
            key="search-target"
            ref={(el) => {
              if (!el) return;
              el.setAttribute("data-search-target", "1");
              const t = searchTarget ?? centroid!;
              const applyProps = () => {
                const mk = el as unknown as Record<string, unknown>;
                mk.position = {
                  lat: t.lat,
                  lng: t.lng,
                  altitude: 80,
                };
                mk.altitudeMode = "RELATIVE_TO_GROUND";
                mk.label = searchTarget
                  ? `◎ ${searchTarget.postcode}`
                  : "◎ SCAN TARGET";
              };
              if (window.customElements?.whenDefined) {
                window.customElements
                  .whenDefined("gmp-marker-3d-interactive")
                  .then(applyProps)
                  .catch(() => applyProps());
              } else {
                applyProps();
              }
            }}
          />
        )}
      </gmp-map-3d>
    </div>
  );
}
