import { create } from "zustand";
import type { TranscriptChunk } from "@/lib/types";
import type { ConversationSession } from "@/lib/elevenlabs";

export type VoiceStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "speaking"
  | "listening"
  | "error"
  | "ended";

interface VoiceStore {
  session: ConversationSession | null;
  transcript: TranscriptChunk[];
  status: VoiceStatus;
  error: string | null;
  start: (session: ConversationSession) => void;
  stop: () => Promise<void>;
  appendChunk: (chunk: TranscriptChunk) => void;
  setStatus: (status: VoiceStatus) => void;
  setError: (msg: string | null) => void;
  reset: () => void;
}

export const useVoiceStore = create<VoiceStore>((set, get) => ({
  session: null,
  transcript: [],
  status: "idle",
  error: null,
  start: (session) =>
    set({ session, status: "connected", error: null, transcript: [] }),
  stop: async () => {
    const s = get().session;
    if (s) {
      try {
        await s.endSession();
      } catch {
        // ignore
      }
    }
    set({ session: null, status: "ended" });
  },
  appendChunk: (chunk) =>
    set((state) => ({ transcript: [...state.transcript, chunk] })),
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error, status: error ? "error" : get().status }),
  reset: () =>
    set({ session: null, transcript: [], status: "idle", error: null }),
}));
