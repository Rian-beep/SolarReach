import { useEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { useScan, API_BASE } from "@/lib/api";
import { formatPostcode } from "@/lib/utils";
import { useLeadStore } from "@/stores/useLeadStore";
import type { Lead } from "@/lib/types";
import { SpendIndicator } from "./SpendIndicator";

// SSE reconnect tuning — covers Mongo blips / Atlas fail-overs mid-demo.
// Backoff: 1s → 2s → 4s → 8s → 8s, then give up.
const SSE_BACKOFFS_MS = [1_000, 2_000, 4_000, 8_000, 8_000] as const;

export type AppMode = "map" | "calculator" | "admin";

interface HeaderProps {
  mode: AppMode;
  onModeChange: (m: AppMode) => void;
  atlasStatus?: "live" | "degraded" | "offline";
}

export function Header({ mode, onModeChange, atlasStatus = "live" }: HeaderProps) {
  const [postcode, setPostcode] = useState("");
  const scan = useScan();
  const addLead = useLeadStore((s) => s.addLead);

  // Track the live EventSource + reconnect timer so unmount tears down cleanly
  // and a second SCAN click cancels the previous stream.
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      esRef.current?.close();
      esRef.current = null;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    },
    [],
  );

  const openScanStream = (streamUrl: string) => {
    // Tear down any prior stream before opening a new one.
    esRef.current?.close();
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    let attempt = 0; // reset to 0 on every successful event
    let done = false;

    const connect = () => {
      const es = new EventSource(streamUrl, { withCredentials: false });
      esRef.current = es;

      es.addEventListener("lead", (ev) => {
        attempt = 0; // healthy traffic — reset backoff
        try {
          const lead = JSON.parse((ev as MessageEvent).data) as Lead;
          addLead(lead);
        } catch {
          // ignore malformed event
        }
      });

      es.addEventListener("progress", () => {
        attempt = 0;
      });

      es.addEventListener("done", () => {
        done = true;
        es.close();
        esRef.current = null;
      });

      es.addEventListener("error", () => {
        // EventSource fires "error" on both transient drops (readyState=CONNECTING)
        // and permanent close (readyState=CLOSED). We treat both as a drop and
        // reconnect manually — gives us bounded retries instead of the browser's
        // unbounded default.
        if (done) return;
        es.close();
        esRef.current = null;

        if (attempt >= SSE_BACKOFFS_MS.length) {
          toast.error("Lost connection to scan stream — please retry");
          return;
        }
        const delay = SSE_BACKOFFS_MS[attempt];
        attempt += 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      });
    };

    connect();
  };

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = postcode.trim();
    if (!trimmed) {
      toast.error("Enter a postcode first");
      return;
    }
    const pretty = formatPostcode(trimmed);
    try {
      const res = await scan.mutateAsync({ postcode: pretty });
      toast.success(`Scan started — ${res.lead_count} leads incoming`);
      // Stream incoming leads into the store as the SSE emits them. This
      // gives the "markers stream in real-time" feel called out in the
      // demo runbook (Atlas Change Streams behind the SSE).
      const streamUrl = res.stream_url.startsWith("http")
        ? res.stream_url
        : `${API_BASE}${res.stream_url}`;
      openScanStream(streamUrl);
    } catch (err) {
      toast.error(`Scan failed: ${(err as Error).message}`);
    }
  };

  const statusColor =
    atlasStatus === "live"
      ? "text-emerald"
      : atlasStatus === "degraded"
        ? "text-amber"
        : "text-red";
  const statusLabel =
    atlasStatus === "live"
      ? "ATLAS LIVE"
      : atlasStatus === "degraded"
        ? "ATLAS DEGRADED"
        : "ATLAS OFFLINE";

  return (
    <header className="sticky top-0 z-40 flex h-12 items-center gap-4 border-b border-iron bg-app-surface px-4">
      {/* Wordmark */}
      <div className="flex items-center gap-3">
        <span className="font-mono text-md font-medium text-bone">
          <span className="text-cyan">solarreach</span>
          <span className="text-dim">://</span>
        </span>
      </div>

      {/* Mode switch */}
      <nav className="flex items-center gap-px border-l border-iron pl-4 ml-1">
        {(["map", "calculator", "admin"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => onModeChange(m)}
            className={
              "px-2 py-1 text-xs font-medium uppercase tracking-wide transition-colors duration-[80ms] " +
              (mode === m
                ? "text-cyan border-b-2 border-cyan -mb-px"
                : "text-mute hover:text-bone")
            }
          >
            {m === "map" ? "OPS" : m === "calculator" ? "CALC" : "ADMIN"}
          </button>
        ))}
      </nav>

      {/* Center: postcode + scan (terminal feel) */}
      <form
        onSubmit={onSubmit}
        className="flex flex-1 max-w-xl items-center gap-2 ml-auto"
        aria-label="Postcode scan"
      >
        <div className="flex flex-1 items-center gap-1.5 h-8 rounded-[2px] border border-iron bg-app-elev-1 px-2 focus-within:border-cyan transition-colors duration-[80ms]">
          <span className="font-mono text-xs text-cyan select-none">{">"}</span>
          <input
            value={postcode}
            onChange={(e) => setPostcode(e.target.value)}
            onBlur={(e) => setPostcode(formatPostcode(e.target.value))}
            placeholder="EC1Y 8AF"
            aria-label="Postcode"
            className="flex-1 bg-transparent font-mono text-sm text-bone placeholder:text-dim placeholder:uppercase uppercase outline-none"
            autoComplete="postal-code"
          />
          <span
            className="font-mono text-xs text-cyan animate-[caret-blink_1.1s_steps(2,end)_infinite] select-none"
            aria-hidden
          >
            _
          </span>
        </div>
        <Button type="submit" disabled={scan.isPending} size="sm">
          {scan.isPending ? "SCANNING…" : "SCAN"}
        </Button>
      </form>

      {/* Right: spend + status pill */}
      <div className="flex items-center gap-3 border-l border-iron pl-3">
        <SpendIndicator />
        <div className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wide">
          <span
            className={
              "inline-block size-1.5 rounded-full animate-[live-dot_1s_linear_infinite] " +
              (atlasStatus === "live"
                ? "bg-emerald"
                : atlasStatus === "degraded"
                  ? "bg-amber"
                  : "bg-red")
            }
          />
          <span className={statusColor}>{statusLabel}</span>
        </div>
      </div>
    </header>
  );
}
