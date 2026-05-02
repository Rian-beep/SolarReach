import { create } from "zustand";

export interface SearchTarget {
  postcode: string;
  lat: number;
  lng: number;
}

interface SearchStore {
  target: SearchTarget | null;
  setTarget: (target: SearchTarget | null) => void;
}

/**
 * Holds the most-recent postcode-search target. Set by Header.tsx after
 * geocoding the typed postcode (postcodes.io). MapSlot.tsx subscribes and
 * flies the camera the moment this changes — independent of the SSE lead
 * stream so the user always sees navigation feedback even if 0 leads match.
 */
export const useSearchStore = create<SearchStore>((set) => ({
  target: null,
  setTarget: (target) => set({ target }),
}));
