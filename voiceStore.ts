import { create } from "zustand";
import { Conversation } from "@elevenlabs/client";
import { startVoiceSession, persistTranscriptChunk, TranscriptChunk } from "@/lib/elevenlabs";

export type ConnectionStatus = "idle" | "connecting" | "connected" | "disconnected" | "error";

type VoiceState = {
  status: ConnectionStatus;
  transcript: TranscriptChunk[];
  errorMsg: string | null;
  leadId: string;
  _session: Conversation | null;
};

type VoiceActions = {
  setLeadId: (id: string) => void;
  startSession: () => Promise<void>;
  endSession: () => Promise<void>;
  clearTranscript: () => void;
};

export const useVoiceStore = create<VoiceState & VoiceActions>((set, get) => ({
  status: "idle",
  transcript: [],
  errorMsg: null,
  leadId: "demo-lead",
  _session: null,

  setLeadId: (id) => set({ leadId: id }),

  clearTranscript: () => set({ transcript: [] }),

  startSession: async () => {
    const { leadId } = get();
    set({ status: "connecting", errorMsg: null, transcript: [] });

    try {
      const session = await startVoiceSession({
        onMessage: async (chunk) => {
          set((s) => ({ transcript: [...s.transcript, chunk] }));
          try {
            await persistTranscriptChunk(leadId, chunk.role, chunk.text);
          } catch {
            // best-effort — don't interrupt the session
          }
        },
        onDisconnect: () => {
          set({ status: "disconnected", _session: null });
        },
        onError: (err) => {
          set({
            status: "error",
            errorMsg: err instanceof Error ? err.message : String(err),
            _session: null,
          });
        },
      });

      set({ status: "connected", _session: session });
    } catch (err) {
      set({
        status: "error",
        errorMsg: err instanceof Error ? err.message : String(err),
        _session: null,
      });
    }
  },

  endSession: async () => {
    const { _session } = get();
    if (_session) {
      await _session.endSession();
    }
    set({ status: "disconnected", _session: null });
  },
}));
