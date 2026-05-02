import { useEffect, useRef } from "react";
import { Mic, MicOff, Radio } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { useVoiceSignedUrl } from "@/lib/api";
import { useVoiceStore } from "@/stores/useVoiceStore";
import { useCostConfirm } from "@/components/header/CostConfirmModal";
import { startConversation } from "@/lib/elevenlabs";
import type { Lead, TranscriptChunk } from "@/lib/types";

interface VoiceTabProps {
  lead: Lead;
}

const VOICE_COST_CENTS = 15;

export function VoiceTab({ lead }: VoiceTabProps) {
  const signedUrl = useVoiceSignedUrl();
  const status = useVoiceStore((s) => s.status);
  const transcript = useVoiceStore((s) => s.transcript);
  const start = useVoiceStore((s) => s.start);
  const stop = useVoiceStore((s) => s.stop);
  const setStatus = useVoiceStore((s) => s.setStatus);
  const setError = useVoiceStore((s) => s.setError);
  const appendChunk = useVoiceStore((s) => s.appendChunk);
  const { confirm } = useCostConfirm();
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [transcript]);

  // Best-effort cleanup on unmount
  useEffect(() => {
    return () => {
      void stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onRehearse = async () => {
    const ok = await confirm(
      VOICE_COST_CENTS,
      "Voice rehearsal (ElevenLabs ConvAI)",
    );
    if (!ok) return;
    try {
      setStatus("connecting");
      const { signed_url } = await signedUrl.mutateAsync(lead._id);
      const session = await startConversation({
        signedUrl: signed_url,
        onConnect: () => setStatus("connected"),
        onDisconnect: () => setStatus("ended"),
        onError: (err) => {
          setError((err as Error)?.message ?? "voice error");
        },
        onMessage: (msg) => {
          const role: TranscriptChunk["role"] =
            msg.source === "user" || msg.role === "user"
              ? "user"
              : msg.source === "ai" || msg.role === "agent"
                ? "agent"
                : "system";
          const text = msg.message ?? "";
          if (!text) return;
          appendChunk({
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            role,
            text,
            ts: Date.now(),
          });
        },
        onModeChange: (m) => {
          if (m.mode === "speaking") setStatus("speaking");
          else if (m.mode === "listening") setStatus("listening");
        },
      });
      start(session);
      toast.success("Voice session live");
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      if (msg.includes("503") || msg.toLowerCase().includes("disclosure")) {
        toast.error(
          "Voice unavailable — check ELEVENLABS_API_KEY + AI disclosure",
        );
      } else {
        toast.error(`Voice start failed: ${msg}`);
      }
    }
  };

  const isLive =
    status === "connected" ||
    status === "speaking" ||
    status === "listening";

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-1.5">
              <Mic className="size-3.5 text-cyan" strokeWidth={1.5} />
              REHEARSE PITCH
            </CardTitle>
            {isLive && (
              <Badge variant="emerald" className="gap-1.5">
                <span className="size-1.5 rounded-full bg-emerald animate-live-dot" />
                {status.toUpperCase()}
              </Badge>
            )}
          </div>
          <CardDescription>
            ElevenLabs ConvAI duplex audio. Transcript persists to{" "}
            <span className="font-mono text-cyan">calls_ts</span>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!isLive ? (
            <Button
              onClick={onRehearse}
              disabled={signedUrl.isPending || status === "connecting"}
              className="w-full"
            >
              <Mic className="size-3.5" strokeWidth={1.5} />
              {status === "connecting" ? "CONNECTING…" : "[REHEARSE PITCH]"}
            </Button>
          ) : (
            <Button
              onClick={() => void stop()}
              variant="destructive"
              className="w-full"
            >
              <MicOff className="size-3.5" strokeWidth={1.5} />
              [END CALL]
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-1.5">
              <Radio className="size-3.5 text-mute" strokeWidth={1.5} />
              CONVERSATION FEED
            </CardTitle>
            <span className="font-mono text-xs text-dim tabular-nums">
              {transcript.length} chunks
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div
            ref={transcriptRef}
            className="h-64 overflow-y-auto rounded-[2px] border border-iron bg-app-void p-2 font-mono text-xs leading-relaxed"
          >
            {transcript.length === 0 ? (
              <div className="grid h-full place-items-center text-grid">
                <div className="text-center">
                  <div className="mb-1 text-md text-iron-bright">[ -- ]</div>
                  <div className="uppercase tracking-wide">
                    no transcript yet
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-1">
                {transcript.map((chunk) => (
                  <div key={chunk.id} className="flex gap-2">
                    <span
                      className={
                        "shrink-0 " +
                        (chunk.role === "agent"
                          ? "text-cyan"
                          : chunk.role === "user"
                            ? "text-bone"
                            : "text-dim")
                      }
                    >
                      {chunk.role === "agent"
                        ? "AGENT:"
                        : chunk.role === "user"
                          ? "USER: "
                          : "SYS:  "}
                    </span>
                    <span className="text-bone">{chunk.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>SIMILAR PAST CALLS</CardTitle>
          <CardDescription>
            Atlas Vector Search · top-3 cosine similarity
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-1 font-mono text-xs">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-[2px] border border-iron bg-app-elev-1 px-2 py-1"
              >
                <span className="text-mute">[ pending vector index ]</span>
                <span className="text-grid tabular-nums">cos —</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
