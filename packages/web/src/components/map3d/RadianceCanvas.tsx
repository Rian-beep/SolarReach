/**
 * Global RADIANCE heat-map canvas — paints inferno gradient blobs at every
 * lead's geo location ON TOP OF the entire visible map area. Camera-coupled:
 * pan/zoom moves blobs, oblique tilt compresses them vertically.
 *
 * Why a custom canvas instead of using <gmp-polygon-3d> per-lead polygons?
 *   - Polygons sit ON the rooftop (per-building tint, owned by ROOFS layer).
 *   - This layer paints a CITY-SCALE gradient — overlapping radial blobs
 *     blend (`globalCompositeOperation = 'lighter'`) so dense lead clusters
 *     glow brighter than isolated outliers. That communicates "where is the
 *     solar opportunity hottest" at a glance.
 *
 * Projection model (pragmatic, no SDK projection API needed):
 *   The alpha gmp-map-3d SDK doesn't expose a stable coordinateToPixel.
 *   Instead we project lat/lng deltas from the camera centre onto screen
 *   pixels using:
 *     - Equirectangular dx/dy in metres relative to camera target.
 *     - metresPerPixel ≈ range × 2 / viewport_height (top-down approx).
 *     - Tilt compression: dy *= cos(tilt) — blobs flatten as the camera
 *       tilts oblique, mimicking ground-plane projection.
 *     - Heading rotation: rotate (dx, dy) by -heading so a heading of 0
 *       puts north up, matching the map.
 *   This is NOT a perfect 3D projection (no perspective) — but at the
 *   demo's typical range (200-2000m) and tilt (≤67°), blobs land within a
 *   building's width of where they "should" be. Good enough for a heat-map
 *   that communicates "city-wide solar potential" rather than per-pixel
 *   forensics (which is what the per-rooftop polygons + flux PNG HUD do).
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

interface ProjectArgs {
  lat: number;
  lng: number;
  camLat: number;
  camLng: number;
  metresPerPixel: number;
  tiltDeg: number;
  headingDeg: number;
  centerX: number;
  centerY: number;
}

/** Convert a lat/lng to a screen pixel relative to the canvas centre. */
function projectLatLng(args: ProjectArgs): { x: number; y: number } {
  const {
    lat,
    lng,
    camLat,
    camLng,
    metresPerPixel,
    tiltDeg,
    headingDeg,
    centerX,
    centerY,
  } = args;
  // Equirectangular: dx east, dy north, in metres.
  const dxM = (lng - camLng) * DEG2RAD * EARTH_R * Math.cos(camLat * DEG2RAD);
  const dyM = (lat - camLat) * DEG2RAD * EARTH_R;
  // Compress north/south by cos(tilt) — when the camera tilts oblique, the
  // ground plane foreshortens vertically.
  const tiltRad = tiltDeg * DEG2RAD;
  const dyMComp = dyM * Math.cos(tiltRad);
  // Rotate by -heading so heading=0 puts north up (matches Google Maps).
  const headRad = headingDeg * DEG2RAD;
  const cosH = Math.cos(headRad);
  const sinH = Math.sin(headRad);
  const xRot = dxM * cosH - dyMComp * sinH;
  const yRot = dxM * sinH + dyMComp * cosH;
  // Convert to pixels. Y inverted (canvas Y grows downward; map Y grows north).
  const x = centerX + xRot / metresPerPixel;
  const y = centerY - yRot / metresPerPixel;
  return { x, y };
}

/** Draw one inferno radial blob at (x, y). Radius scales with score. */
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

  // Subscribe to camera + leads. Slice subs so we re-render only when the
  // values we actually use change.
  const camLat = useCameraStore((s) => s.lat);
  const camLng = useCameraStore((s) => s.lng);
  const range = useCameraStore((s) => s.range);
  const tilt = useCameraStore((s) => s.tilt);
  const heading = useCameraStore((s) => s.heading);
  const leads = useLeadStore((s) => s.leads);

  // Resize the backing canvas to its CSS box (with DPR) on every paint.
  // Avoids stale viewport sizes after window resize and keeps the heatmap
  // crisp on hi-DPI displays.
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
      const cssW = parent.clientWidth;
      const cssH = parent.clientHeight;
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
      const ctx = cv.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cssW, cssH);

      // Bail early if camera not ready or no leads.
      if (
        camLat === null ||
        camLng === null ||
        range === null ||
        leads.length === 0
      ) {
        return;
      }

      // Metres-per-pixel approximation: gmp-map-3d's `range` is the
      // camera-to-target distance. With a typical FOV of ~60°, the visible
      // ground swath height ≈ range × 2 × tan(30°) ≈ range × 1.155.
      // metresPerPixel = swath / viewport_height. Top-down only — for tilted
      // views the swath grows along the look direction, but the centre
      // region (where most leads land for the demo) stays roughly correct.
      const FOV_HALF_TAN = Math.tan(30 * DEG2RAD); // ≈ 0.577
      const swathM = range * 2 * FOV_HALF_TAN;
      const metresPerPixel = swathM / cssH;
      const centerX = cssW / 2;
      const centerY = cssH / 2;

      // Use 'lighter' so overlapping blobs additively brighten — dense
      // lead clusters glow hotter than isolated outliers, communicating
      // city-wide solar density.
      ctx.globalCompositeOperation = "lighter";

      // Blob radius in pixels — scaled inversely with metres-per-pixel so
      // each blob covers ~120m on the ground regardless of zoom. Clamped so
      // the heatmap never disappears (zoomed way out) or eats the screen
      // (zoomed way in).
      const groundRadiusM = 120;
      const radiusPx = Math.max(
        24,
        Math.min(180, groundRadiusM / metresPerPixel),
      );

      const tiltDeg = tilt ?? 0;
      const headingDeg = heading ?? 0;

      for (const lead of leads as Lead[]) {
        const c = lead.geo?.point?.coordinates;
        if (!c) continue;
        const [lng, lat] = c;
        const { x, y } = projectLatLng({
          lat,
          lng,
          camLat,
          camLng,
          metresPerPixel,
          tiltDeg,
          headingDeg,
          centerX,
          centerY,
        });
        // Off-screen culling with 1× radius pad — avoids drawing thousands
        // of off-canvas blobs when zoomed deep.
        if (
          x < -radiusPx ||
          x > cssW + radiusPx ||
          y < -radiusPx ||
          y > cssH + radiusPx
        ) {
          continue;
        }
        const score = lead.scores?.composite_score ?? 0;
        drawBlob(ctx, x, y, score, radiusPx);
      }

      // Reset comp op so subsequent draws (none currently) aren't affected.
      ctx.globalCompositeOperation = "source-over";
    };

    const schedule = () => {
      if (frameRaf !== null) return;
      frameRaf = window.requestAnimationFrame(draw);
    };

    schedule();
    // Also redraw on window resize — the parent's CSS box will change but
    // none of the camera/leads slices will, so the effect's deps wouldn't
    // re-fire on their own.
    window.addEventListener("resize", schedule);
    return () => {
      if (frameRaf !== null) window.cancelAnimationFrame(frameRaf);
      window.removeEventListener("resize", schedule);
    };
  }, [enabled, camLat, camLng, range, tilt, heading, leads]);

  if (!enabled) return null;

  return (
    <canvas
      ref={canvasRef}
      className={
        "pointer-events-none absolute inset-0 z-10 " + (className ?? "")
      }
      // Subtle blend so the heat reads as a haze over the buildings rather
      // than a flat overlay that hides them. 'screen' on the CSS layer (in
      // addition to canvas-internal 'lighter') brightens the underlying
      // map only where blobs are painted.
      style={{ mixBlendMode: "screen" }}
      aria-hidden="true"
    />
  );
}
