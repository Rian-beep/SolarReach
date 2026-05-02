/**
 * Live camera state lifted out of `<gmp-map-3d>` so HUDs (coords, scale)
 * can re-render whenever the camera moves — not just on lead select.
 *
 * MapSlot owns the mutator: it reads the `gmp-camerachange` event off the
 * web component and calls `set(...)` on every frame Google emits one.
 *
 * Consumers (HUDCoords / HUDScale) subscribe to slices to avoid
 * re-rendering the whole tree on every camera tick.
 */
import { create } from "zustand";

export interface CameraState {
  lat: number | null;
  lng: number | null;
  /** Range = look-at distance in metres (Google Maps 3D semantic). */
  range: number | null;
  /** Tilt in degrees (0 = top-down, 90 = horizontal). */
  tilt: number | null;
  /** Heading in degrees (0 = north). */
  heading: number | null;
  set: (next: Partial<Omit<CameraState, "set">>) => void;
}

export const useCameraStore = create<CameraState>((set) => ({
  lat: null,
  lng: null,
  range: null,
  tilt: null,
  heading: null,
  set: (next) => set(next),
}));
