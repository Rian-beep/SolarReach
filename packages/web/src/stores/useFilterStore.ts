import { create } from "zustand";
import type { PremisesType } from "@/lib/types";

interface FilterStore {
  scoreMin: number;
  premisesType: PremisesType | null;
  query: string;
  setScoreMin: (v: number) => void;
  setPremisesType: (v: PremisesType | null) => void;
  setQuery: (v: string) => void;
  reset: () => void;
}

export const useFilterStore = create<FilterStore>((set) => ({
  scoreMin: 0,
  premisesType: null,
  query: "",
  setScoreMin: (scoreMin) => set({ scoreMin }),
  setPremisesType: (premisesType) => set({ premisesType }),
  setQuery: (query) => set({ query }),
  reset: () => set({ scoreMin: 0, premisesType: null, query: "" }),
}));
