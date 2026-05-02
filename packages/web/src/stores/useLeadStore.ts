import { create } from "zustand";
import type { Lead } from "@/lib/types";

interface LeadStore {
  leads: Lead[];
  selectedLeadId: string | null;
  setLeads: (leads: Lead[]) => void;
  addLead: (lead: Lead) => void;
  select: (id: string | null) => void;
  clear: () => void;
}

export const useLeadStore = create<LeadStore>((set) => ({
  leads: [],
  selectedLeadId: null,
  setLeads: (leads) => set({ leads }),
  addLead: (lead) =>
    set((state) => {
      // de-dupe by _id
      if (state.leads.some((l) => l._id === lead._id)) return state;
      return { leads: [lead, ...state.leads] };
    }),
  select: (id) => set({ selectedLeadId: id }),
  clear: () => set({ leads: [], selectedLeadId: null }),
}));
