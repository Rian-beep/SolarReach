import { Conversation } from "@elevenlabs/client";

const VOICE_API_BASE = import.meta.env.VITE_VOICE_API_URL ?? "http://localhost:8000";

export type TranscriptChunk = {
  role: "agent" | "user";
  text: string;
};

export type SessionCallbacks = {
  onMessage: (chunk: TranscriptChunk) => void;
  onDisconnect: () => void;
  onError: (err: unknown) => void;
};

export async function startVoiceSession(callbacks: SessionCallbacks): Promise<Conversation> {
  const res = await fetch(`${VOICE_API_BASE}/voice/signed-url`);
  if (!res.ok) {
    throw new Error(`Failed to get signed URL: ${res.status} ${await res.text()}`);
  }
  const { signed_url: signedUrl } = await res.json();

  const session = await Conversation.startSession({
    signedUrl,
    onMessage: (msg: { message: string; source: "agent" | "user" }) => {
      callbacks.onMessage({ role: msg.source, text: msg.message });
    },
    onDisconnect: callbacks.onDisconnect,
    onError: callbacks.onError,
  });

  return session;
}

export async function persistTranscriptChunk(
  leadId: string,
  role: "agent" | "user",
  text: string
): Promise<void> {
  await fetch(`${VOICE_API_BASE}/voice/transcript`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lead_id: leadId, role, text }),
  });
}
