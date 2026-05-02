// Typed wrappers around @elevenlabs/client.
// We intentionally keep the surface small — only what VoiceTab needs.

import { Conversation } from "@elevenlabs/client";

export { Conversation };

export interface ConversationCallbacks {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (err: unknown) => void;
  onMessage?: (msg: { source?: string; message?: string; role?: string }) => void;
  onStatusChange?: (prop: { status: string }) => void;
  onModeChange?: (mode: { mode: string }) => void;
}

export interface StartSessionArgs extends ConversationCallbacks {
  signedUrl: string;
}

/**
 * Wrapper around `Conversation.startSession` returning a session handle with
 * `endSession()` to disconnect cleanly.
 */
export async function startConversation(
  args: StartSessionArgs,
): Promise<Awaited<ReturnType<typeof Conversation.startSession>>> {
  return Conversation.startSession({
    signedUrl: args.signedUrl,
    onConnect: args.onConnect,
    onDisconnect: args.onDisconnect,
    onError: args.onError,
    onMessage: args.onMessage,
    onStatusChange: args.onStatusChange,
    onModeChange: args.onModeChange,
  });
}

export type ConversationSession = Awaited<
  ReturnType<typeof Conversation.startSession>
>;
