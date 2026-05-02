import { useEffect } from "react";
import { useVoiceStore, ConnectionStatus } from "@/stores/voiceStore";

type Props = {
  leadId?: string;
};

const STATUS_DOT: Record<ConnectionStatus, string> = {
  idle: "bg-gray-400",
  connecting: "bg-yellow-400 animate-pulse",
  connected: "bg-green-500",
  disconnected: "bg-gray-500",
  error: "bg-red-500",
};

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  idle: "Not connected",
  connecting: "Connecting…",
  connected: "Live",
  disconnected: "Disconnected",
  error: "Error",
};

export function VoiceRehearsalSection({ leadId = "demo-lead" }: Props) {
  const { status, transcript, errorMsg, setLeadId, startSession, endSession } = useVoiceStore();

  useEffect(() => {
    setLeadId(leadId);
  }, [leadId, setLeadId]);

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-xl font-semibold text-gray-800">Rehearse Pitch</h2>

      {/* Status badge */}
      <div className="mb-4 flex items-center gap-2">
        <span className={`h-3 w-3 rounded-full ${STATUS_DOT[status]}`} />
        <span className="text-sm text-gray-600">{STATUS_LABEL[status]}</span>
      </div>

      {/* Controls */}
      <div className="mb-6 flex gap-3">
        <button
          onClick={startSession}
          disabled={status === "connecting" || status === "connected"}
          className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Rehearse pitch
        </button>

        {status === "connected" && (
          <button
            onClick={endSession}
            className="rounded-lg border border-red-300 px-5 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-50"
          >
            End call
          </button>
        )}
      </div>

      {/* Error */}
      {errorMsg && (
        <p className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{errorMsg}</p>
      )}

      {/* Live transcript */}
      {transcript.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium uppercase tracking-wide text-gray-500">
            Live Transcript
          </h3>
          <div className="max-h-72 space-y-2 overflow-y-auto rounded-lg border border-gray-100 bg-gray-50 p-4">
            {transcript.map((chunk, i) => (
              <div
                key={i}
                className={`flex ${chunk.role === "agent" ? "justify-start" : "justify-end"}`}
              >
                <div
                  className={`max-w-xs rounded-lg px-3 py-2 text-sm ${
                    chunk.role === "agent"
                      ? "bg-indigo-100 text-indigo-900"
                      : "border border-gray-200 bg-white text-gray-800"
                  }`}
                >
                  <span className="mb-0.5 block text-xs font-semibold capitalize opacity-60">
                    {chunk.role}
                  </span>
                  {chunk.text}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
