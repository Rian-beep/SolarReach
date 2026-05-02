import { useEffect, useRef } from "react";

export interface SSEMessage {
  event: string;
  data: string;
  id?: string;
}

export interface SSEOptions {
  /** Disable auto-reconnect (default: enabled) */
  noReconnect?: boolean;
  /** Initial backoff in ms (default 500) */
  initialBackoff?: number;
  /** Max backoff in ms (default 8000) */
  maxBackoff?: number;
  /** Skip when null (lets the hook be conditional) */
  enabled?: boolean;
}

/**
 * useSSE — minimal EventSource wrapper with exponential backoff reconnect.
 * onMessage receives every event (named or default).
 */
export function useSSE(
  url: string | null,
  onMessage: (msg: SSEMessage) => void,
  opts: SSEOptions = {},
): void {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    if (!url || opts.enabled === false) return;
    let es: EventSource | null = null;
    let cancelled = false;
    let attempt = 0;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const initial = opts.initialBackoff ?? 500;
    const max = opts.maxBackoff ?? 8_000;

    const connect = () => {
      if (cancelled) return;
      es = new EventSource(url, { withCredentials: false });

      es.onopen = () => {
        attempt = 0;
      };

      es.onmessage = (ev) => {
        handlerRef.current({ event: "message", data: ev.data, id: ev.lastEventId });
      };

      // Listen for named events too — common SolarReach events:
      ["lead", "progress", "done", "error"].forEach((name) => {
        es?.addEventListener(name, (ev: MessageEvent) => {
          handlerRef.current({
            event: name,
            data: ev.data,
            id: ev.lastEventId,
          });
        });
      });

      es.onerror = () => {
        if (cancelled) return;
        es?.close();
        if (opts.noReconnect) return;
        attempt += 1;
        const wait = Math.min(initial * 2 ** (attempt - 1), max);
        timeoutId = setTimeout(connect, wait);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      es?.close();
    };
  }, [url, opts.enabled, opts.noReconnect, opts.initialBackoff, opts.maxBackoff]);
}
