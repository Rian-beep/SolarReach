/**
 * Global RADIANCE heat-map canvas — paints inferno gradient blobs at every
 * lead's geo location ON TOP OF the entire visible map area. Camera-coupled:
 * pan/zoom moves blobs, oblique tilt foreshortens them along the look
 * direction so they stay locked to the ground.
 *
 * Why a custom canvas instead of using <gmp-polygon-3d> per-lead polygons?
 *   - Polygons sit ON the rooftop (per-building tint, owned by ROOFS layer).
 *   - This layer paints a CITY-SCALE gradient — overlapping radial blobs
 *     blend (`globalCompositeOperation = 'lighter'`) so dense lead clusters
 *     glow brighter than isolated outliers. That communicates "where is the
 *     solar opportunity hottest" at a glance.
 *
 * Projection model — pinhole perspective camera:
 *   The alpha gmp-map-3d SDK does NOT expose a public projection method
 *   (verified by walking Map3DElement.prototype on 2026-05-02 — only
 *   flyCameraTo / flyCameraAround / stopCameraAnimation / update are stable;
 *   the minified two-letter methods are internal & break across builds).
 *
 *   So we replicate the camera math:
 *     1. Camera target (look-at) is `center` (lat,lng,altitude). Camera eye
 *        sits `range` metres away at angle (90° − tilt) above the ground,
 *        rotated by `heading` about the vertical.
 *     2. Each lead's lat/lng → east/north metres relative to target
 *        (equirectangular at this lat — accurate to <1m within a 5km radius).
 *     3. Rotate world coords into camera-local frame: undo heading about
 *        the up axis, then undo tilt about the camera's local east axis.
 *     4. Perspective divide: x/z, y/z scaled by viewport_height / (2·tan(fov/2)).
 *     5. Map to canvas pixels using the map element's bounding rect (NOT the
 *        parent — there can be UI chrome).
 *
 *   FOV is empirically calibrated. The alpha 3D Maps photoreal renderer uses
 *   roughly a 35° vertical FOV (telephoto-ish) — wider values misalign blobs
 *   visibly at high tilt. Tune via DEFAULT_FOV_DEG if SDK behaviour shifts.
 *
 * Redraw cadence:
 *   We attach a direct `gmp-camerachange` listener so we redraw on every
 *   camera tick the SDK emits — not waiting on React re-render scheduling
 *   which can lag a frame behind under load. The store is still used as a
 *   fallback (initial render before the element mounts).
 */
import { useEffect, useRef } from "react";
import { useCameraStore } from "@/stores/useCameraStore";
import { useLeadStore } from "@/stores/useLeadStore";
import type { Lead } from "@/lib/types";

interface RadianceCanvasProps {
  /** When false, the canvas hides itself (RADIANCE layer toggled off). */
  enabled: boolean;
  className?: string;
}

// Inferno colormap stops aligned with MapSlot's per-rooftop tint so the
// heatmap reads as the same visual language. Higher score → hotter colour.
function infernoForScore(score: number): { r: number; g: number; b: number } {
  // Stops chosen from matplotlib inferno at 0.1 / 0.4 / 0.6 / 0.8 / 0.95.
  if (score >= 80) return { r: 0xfc, g: 0xff, b: 0xa4 }; // pale yellow
  if (score >= 65) return { r: 0xf3, g: 0x78, b: 0x19 }; // orange
  if (score >= 50) return { r: 0xdd, g: 0x51, b: 0x3a }; // red-orange
  if (score >= 35) return { r: 0x93, g: 0x26, b: 0x67 }; // magenta
  return { r: 0x42, g: 0x0a, b: 0x68 }; // deep purple
}

// Earth radius (metres) — used in the equirectangular projection.
const EARTH_R = 6_378_137;
const DEG2RAD = Math.PI / 180;
// Empirically calibrated vertical FOV for the alpha gmp-map-3d photoreal
// renderer. If the SDK ever exposes a real FOV getter, prefer that.
const DEFAULT_FOV_DEG = 35;

interface CameraSnapshot {
  lat: number;
  lng: number;
  /** Effective camera-to-target distance in metres. */
  range: number;
  /** Tilt in degrees (0 = top-down, 90 = looking at horizon). */
  tilt: number;
  /** Heading in degrees (0 = north up, +ve = clockwise). */
  heading: number;
}

/**
 * Read the live camera state directly from the <gmp-map-3d> element. The
 * alpha SDK keeps `center`, `range`, `tilt`, `heading` in sync as both
 * properties AND attributes; we prefer attributes since they update on
 * every camerachange tick (properties are getters that can throw during
 * the boot window). Falls back to store-derived values when the element
 * isn't in the DOM yet (initial render).
 */
function readCamera(
  mapEl: Element | null,
  fallback: { lat: number | null; lng: number | null; range: number | null; tilt: number | null; heading: number | null },
): CameraSnapshot | null {
  let lat: number | null = null;
  let lng: number | null = null;
  let altitude = 0;
  let range: number | null = null;
  let tilt: number | null = null;
  let heading: number | null = null;

  if (mapEl) {
    const centerStr = mapEl.getAttribute("center");
    if (centerStr) {
      const parts = centerStr.split(",").map((s) => parseFloat(s.trim()));
      if (parts.length >= 2 && Number.isFinite(parts[0]) && Number.isFinite(parts[1])) {
        lat = parts[0];
        lng = parts[1];
        if (parts.length >= 3 && Number.isFinite(parts[2])) altitude = parts[2];
      }
    }
    const rangeAttr = mapEl.getAttribute("range");
    const tiltAttr = mapEl.getAttribute("tilt");
    const headingAttr = mapEl.getAttribute("heading");
    range = rangeAttr ? parseFloat(rangeAttr) : null;
    tilt = tiltAttr ? parseFloat(tiltAttr) : null;
    heading = headingAttr ? parseFloat(headingAttr) : null;
  }

  // Fall back to store for any field still missing.
  if (lat === null) lat = fallback.lat;
  if (lng === null) lng = fallback.lng;
  if (range === null) range = fallback.range;
  if (tilt === null) tilt = fallback.tilt;
  if (heading === null) heading = fallback.heading;

  if (lat === null || lng === null) return null;

  // The SDK reports `range = 0` when the camera is in its default boot
  // state (no flyCameraTo issued yet). In that mode the camera-to-ground
  // distance is `center.altitude`. Use whichever is positive.
  const effectiveRange = range && range > 0 ? range : altitude > 0 ? altitude : 1500;

  return {
    lat,
    lng,
    range: effectiveRange,
    tilt: tilt ?? 0,
    heading: heading ?? 0,
  };
}

interface ProjectArgs {
  lat: number;
  lng: number;
  cam: CameraSnapshot;
  viewportW: number;
  viewportH: number;
}

interface ProjectResult {
  x: number;
  y: number;
  /** Camera-space depth in metres. <= 0 means point is behind/at camera. */
  depth: number;
  /** Pixel scale at this depth — used to size blobs so they stay ~120m on the ground. */
  pxPerMetreAtPoint: number;
}

/**
 * Project a world lat/lng to canvas pixels using a pinhole camera model.
 * Returns null when the point is behind the camera (depth <= 0).
 */
function projectLatLng(args: ProjectArgs): ProjectResult | null {
  const { lat, lng, cam, viewportW, viewportH } = args;

  // 1. World deltas in metres relative to the camera's look-at point.
  //    Equirectangular: dE east, dN north.
  const dE = (lng - cam.lng) * DEG2RAD * EARTH_R * Math.cos(cam.lat * DEG2RAD);
  const dN = (lat - cam.lat) * DEG2RAD * EARTH_R;

  // 2. Rotate world into camera's azimuth frame: we want a coordinate
  //    system where +X = camera-right, +Y_world = forward-on-ground (the
  //    direction the camera is pointing in plan view).
  //    heading=0 ⇒ camera looks north ⇒ forward = +N. heading rotates
  //    clockwise looking down, so forward direction in world (E, N) is
  //    (sin(h), cos(h)). Right is (cos(h), -sin(h)).
  const h = cam.heading * DEG2RAD;
  const cosH = Math.cos(h);
  const sinH = Math.sin(h);
  const xRight = dE * cosH - dN * sinH;
  const yForward = dE * sinH + dN * cosH;

  // 3. Apply tilt about the camera's local east axis. The camera target is
  //    on the ground at (xRight=0, yForward=0, height=0). Camera eye sits
  //    behind the target at distance `range` along the look direction:
  //      eye = target + range * (−forward·sin(tilt) − up·cos(tilt) ... wait)
  //    Easier: define the look vector. With tilt=0 (top-down) the camera
  //    looks straight down (−Z). With tilt=90 it looks horizontally along
  //    +Y_forward. So the camera's view direction in world is:
  //      look = (0, sin(tilt), −cos(tilt))
  //    The camera position is at target − range·look:
  //      eye = (0, −range·sin(tilt), range·cos(tilt))
  //    A world point P = (xRight, yForward, 0). In camera-local frame
  //    (where +Z_cam = forward into scene, +X_cam = right, +Y_cam = up)
  //    we project P − eye onto the camera basis:
  //      cam_forward = look = (0, sin(tilt), −cos(tilt))
  //      cam_right   = (1, 0, 0)
  //      cam_up      = cross(cam_forward, cam_right) ... use right-handed:
  //                  = (0, cos(tilt), sin(tilt))
  //    P − eye = (xRight, yForward + range·sin(tilt), −range·cos(tilt))
  //    cam_x = (P-eye)·right    = xRight
  //    cam_y = (P-eye)·up       = (yForward + range·sin(tilt))·cos(tilt)
  //                              + (−range·cos(tilt))·sin(tilt)
  //                            = yForward·cos(tilt)
  //                              + range·sin(tilt)·cos(tilt)
  //                              − range·sin(tilt)·cos(tilt)
  //                            = yForward·cos(tilt)
  //    cam_z = (P-eye)·forward  = (yForward + range·sin(tilt))·sin(tilt)
  //                              + (−range·cos(tilt))·(−cos(tilt))
  //                            = yForward·sin(tilt)
  //                              + range·sin²(tilt)
  //                              + range·cos²(tilt)
  //                            = yForward·sin(tilt) + range
  const t = cam.tilt * DEG2RAD;
  const sinT = Math.sin(t);
  const cosT = Math.cos(t);
  const camX = xRight;
  const camY = yForward * cosT;
  const camZ = yForward * sinT + cam.range;

  // 4. Behind-camera cull. depth must be strictly positive.
  if (camZ <= 1) return null;

  // 5. Perspective: focal length f (in pixels) such that a point on the
  //    image plane at half-FOV maps to viewport_height/2 pixels:
  //      f = (viewportH / 2) / tan(fov/2)
  //    Screen X = centerX + f · camX / camZ
  //    Screen Y = centerY − f · camY / camZ   (Y inverted for canvas)
  const f = viewportH / 2 / Math.tan((DEFAULT_FOV_DEG * DEG2RAD) / 2);
  const cx = viewportW / 2;
  const cy = viewportH / 2;
  const x = cx + (f * camX) / camZ;
  const y = cy - (f * camY) / camZ;

  // 6. pxPerMetre AT this point = f / camZ, so a 1m-on-ground feature near
  //    this point spans `f / camZ` pixels. Used to size blobs so they
  //    foreshorten with distance — far blobs shrink, near blobs grow.
  const pxPerMetreAtPoint = f / camZ;

  return { x, y, depth: camZ, pxPerMetreAtPoint };
}

/** Draw one inferno radial blob at (x, y). */
function drawBlob(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  score: number,
  radiusPx: number,
) {
  const { r, g, b } = infernoForScore(score);
  // Inner alpha modulated by score so high-scoring leads burn brighter even
  // before blending. Outer alpha = 0 so blobs fade into the dark map.
  const innerA = Math.min(0.85, 0.35 + score / 200); // 0.35..0.85
  const grad = ctx.createRadialGradient(x, y, 0, x, y, radiusPx);
  grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${innerA.toFixed(3)})`);
  grad.addColorStop(0.6, `rgba(${r}, ${g}, ${b}, ${(innerA * 0.4).toFixed(3)})`);
  grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(x, y, radiusPx, 0, Math.PI * 2);
  ctx.fill();
}

export function RadianceCanvas({ enabled, className }: RadianceCanvasProps) {
  // ── ALL hooks before any conditional return (cardinal rule) ──────────
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // schedule() lives in the main effect's closure — expose via ref so the
  // store-driven nudge effect (and any future caller) can request a redraw.
  const scheduleRef = useRef<(() => void) | null>(null);

  // Keep a ref to the latest leads so the camerachange listener (which is
  // bound once) always sees current data without resubscribing.
  const leads = useLeadStore((s) => s.leads);
  const leadsRef = useRef(leads);
  leadsRef.current = leads;

  // Store-derived camera fallback (used until the gmp-map-3d element is in
  // the DOM and we can read its attributes directly).
  const camLat = useCameraStore((s) => s.lat);
  const camLng = useCameraStore((s) => s.lng);
  const camRange = useCameraStore((s) => s.range);
  const camTilt = useCameraStore((s) => s.tilt);
  const camHeading = useCameraStore((s) => s.heading);
  const fallbackRef = useRef({
    lat: camLat,
    lng: camLng,
    range: camRange,
    tilt: camTilt,
    heading: camHeading,
  });
  fallbackRef.current = {
    lat: camLat,
    lng: camLng,
    range: camRange,
    tilt: camTilt,
    heading: camHeading,
  };

  useEffect(() => {
    if (!enabled) return;
    const cv = canvasRef.current;
    if (!cv) return;
    const parent = cv.parentElement;
    if (!parent) return;

    let frameRaf: number | null = null;

    const draw = () => {
      frameRaf = null;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      // Use the map element's optical rect when available — that's the
      // viewport the camera math is calibrated against. When the element
      // isn't in the DOM yet, fall back to the parent's CSS box.
      const mapEl = document.querySelector("gmp-map-3d");
      const mapRect = mapEl?.getBoundingClientRect();
      const useMapRect = mapRect && mapRect.width > 0 && mapRect.height > 0;

      const cssW = useMapRect ? mapRect.width : parent.clientWidth;
      const cssH = useMapRect ? mapRect.height : parent.clientHeight;
      if (cssW === 0 || cssH === 0) return;

      // Resize backing store if needed.
      const needW = Math.round(cssW * dpr);
      const needH = Math.round(cssH * dpr);
      if (cv.width !== needW || cv.height !== needH) {
        cv.width = needW;
        cv.height = needH;
        cv.style.width = `${cssW}px`;
        cv.style.height = `${cssH}px`;
      }

      // Align canvas with the map element when the map doesn't fill the
      // parent (e.g. a side drawer offsets the map). Without this the
      // canvas's pixel-space origin (top-left of parent) drifts from the
      // map's origin and blobs land in the wrong column of pixels.
      if (useMapRect) {
        const parentRect = parent.getBoundingClientRect();
        const offsetX = mapRect.left - parentRect.left;
        const offsetY = mapRect.top - parentRect.top;
        cv.style.left = `${offsetX}px`;
        cv.style.top = `${offsetY}px`;
        cv.style.right = "auto";
        cv.style.bottom = "auto";
      } else {
        cv.style.left = "0";
        cv.style.top = "0";
        cv.style.right = "0";
        cv.style.bottom = "0";
      }

      const ctx = cv.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cssW, cssH);

      const cam = readCamera(mapEl, fallbackRef.current);
      if (!cam) return;
      const currentLeads = leadsRef.current;
      if (currentLeads.length === 0) return;

      // Use 'lighter' so overlapping blobs additively brighten — dense
      // lead clusters glow hotter than isolated outliers, communicating
      // city-wide solar density.
      ctx.globalCompositeOperation = "lighter";

      // Target ground footprint per blob (metres). Blob pixel radius is
      // recomputed PER BLOB using the projection's pxPerMetreAtPoint so a
      // blob far from the camera shrinks (perspective foreshortening) and
      // blobs near the camera grow — keeps them locked to the ground.
      const groundRadiusM = 120;

      for (const lead of currentLeads as Lead[]) {
        const c = lead.geo?.point?.coordinates;
        if (!c) continue;
        const [lng, lat] = c;
        const proj = projectLatLng({
          lat,
          lng,
          cam,
          viewportW: cssW,
          viewportH: cssH,
        });
        if (!proj) continue; // behind camera
        // Per-point radius — clamped so heatmap stays visible at extreme
        // zooms and never eats the screen at point-blank range.
        const radiusPx = Math.max(
          18,
          Math.min(220, groundRadiusM * proj.pxPerMetreAtPoint),
        );
        // Off-screen culling with 1× radius pad.
        if (
          proj.x < -radiusPx ||
          proj.x > cssW + radiusPx ||
          proj.y < -radiusPx ||
          proj.y > cssH + radiusPx
        ) {
          continue;
        }
        const score = lead.scores?.composite_score ?? 0;
        drawBlob(ctx, proj.x, proj.y, score, radiusPx);
      }

      // Reset comp op so subsequent draws (none currently) aren't affected.
      ctx.globalCompositeOperation = "source-over";
    };

    const schedule = () => {
      if (frameRaf !== null) return;
      frameRaf = window.requestAnimationFrame(draw);
    };
    scheduleRef.current = schedule;

    // First paint.
    schedule();

    // ── Camera tick — redraw on every gmp-camerachange the SDK emits ────
    // The element may not be in the DOM yet (MapSlot lazy-loads the SDK),
    // so we poll briefly until it appears, then attach the listener.
    let mapEl: Element | null = document.querySelector("gmp-map-3d");
    let attachInterval: number | null = null;
    const camHandler = () => schedule();

    const attach = (el: Element) => {
      el.addEventListener("gmp-camerachange", camHandler);
      // Some camera updates (e.g. attribute mutation by MapSlot's flyOrSnap
      // before the first user interaction) don't dispatch camerachange.
      // A MutationObserver on the element's attributes catches those.
      const mo = new MutationObserver(() => schedule());
      mo.observe(el, {
        attributes: true,
        attributeFilter: ["center", "range", "tilt", "heading"],
      });
      detachers.push(() => {
        el.removeEventListener("gmp-camerachange", camHandler);
        mo.disconnect();
      });
    };

    const detachers: Array<() => void> = [];

    if (mapEl) {
      attach(mapEl);
    } else {
      attachInterval = window.setInterval(() => {
        mapEl = document.querySelector("gmp-map-3d");
        if (mapEl) {
          attach(mapEl);
          if (attachInterval !== null) {
            window.clearInterval(attachInterval);
            attachInterval = null;
          }
          schedule();
        }
      }, 200);
    }

    // Window resize — viewport changes need a redraw even if camera holds.
    window.addEventListener("resize", schedule);

    return () => {
      if (frameRaf !== null) window.cancelAnimationFrame(frameRaf);
      if (attachInterval !== null) window.clearInterval(attachInterval);
      for (const d of detachers) d();
      window.removeEventListener("resize", schedule);
      scheduleRef.current = null;
    };
    // We INTENTIONALLY only depend on `enabled` here. Camera + leads are
    // read via refs/queries inside draw(), and redraw is triggered by the
    // element's own camerachange / mutation events. This avoids
    // re-creating the listener on every camera tick (which would race the
    // event) and also re-runs draw immediately when the user toggles the
    // RADIANCE layer.
  }, [enabled]);

  // Also nudge a redraw when the store-backed camera or leads change —
  // covers initial render before the gmp-map-3d element exists, plus any
  // case where the element fires neither camerachange nor an attribute
  // mutation. The scheduleRef will be null on first render (main effect
  // hasn't run yet); that's fine — schedule() will fire from the main
  // effect's first-paint call.
  useEffect(() => {
    if (!enabled) return;
    scheduleRef.current?.();
  }, [enabled, camLat, camLng, camRange, camTilt, camHeading, leads]);

  if (!enabled) return null;

  return (
    <canvas
      ref={canvasRef}
      className={
        "pointer-events-none absolute z-10 " + (className ?? "")
      }
      // Subtle blend so the heat reads as a haze over the buildings rather
      // than a flat overlay that hides them. 'screen' on the CSS layer (in
      // addition to canvas-internal 'lighter') brightens the underlying
      // map only where blobs are painted.
      style={{ mixBlendMode: "screen", left: 0, top: 0, right: 0, bottom: 0 }}
      aria-hidden="true"
    />
  );
}
