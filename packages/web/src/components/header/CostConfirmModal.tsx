import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { gbp } from "@/lib/utils";

interface CostConfirmContextValue {
  /**
   * Open the modal — returns a Promise that resolves true if the user confirmed,
   * false otherwise. Calls under 10 cents auto-resolve true.
   */
  confirm: (estimateCents: number, label?: string) => Promise<boolean>;
}

const CostConfirmContext = createContext<CostConfirmContextValue | null>(null);

interface PendingPrompt {
  estimateCents: number;
  label: string;
  resolve: (ok: boolean) => void;
}

export function CostConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingPrompt | null>(null);
  const pendingRef = useRef<PendingPrompt | null>(null);
  pendingRef.current = pending;

  const confirm = useCallback(
    (estimateCents: number, label?: string): Promise<boolean> => {
      if (estimateCents < 10) return Promise.resolve(true);
      return new Promise<boolean>((resolve) => {
        setPending({
          estimateCents,
          label: label ?? "this action",
          resolve,
        });
      });
    },
    [],
  );

  const handleResolve = (ok: boolean) => {
    const p = pendingRef.current;
    if (p) p.resolve(ok);
    setPending(null);
  };

  return (
    <CostConfirmContext.Provider value={{ confirm }}>
      {children}
      <Dialog
        open={!!pending}
        onOpenChange={(open) => {
          if (!open) handleResolve(false);
        }}
      >
        <DialogContent className="max-w-[320px]">
          <DialogHeader>
            <DialogTitle>CONFIRM SPEND</DialogTitle>
            <DialogDescription>
              This action will spend{" "}
              <span className="font-mono text-bone">
                {pending ? gbp(pending.estimateCents, { cents: true }) : "—"}
              </span>{" "}
              from session budget.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-[2px] border border-iron bg-app-elev-1 p-2">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-mute uppercase tracking-wide">
                {pending?.label}
              </span>
              <span className="font-mono text-md text-amber tabular-nums">
                {pending ? gbp(pending.estimateCents, { cents: true }) : "—"}
              </span>
            </div>
            <p className="mt-1 text-xs text-dim leading-relaxed">
              Estimates are best-effort. Actual cost recorded in audit log.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleResolve(false)}
            >
              CANCEL
            </Button>
            <Button size="sm" onClick={() => handleResolve(true)}>
              CONFIRM
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </CostConfirmContext.Provider>
  );
}

export function useCostConfirm(): CostConfirmContextValue {
  const ctx = useContext(CostConfirmContext);
  if (!ctx) {
    throw new Error(
      "useCostConfirm must be used inside <CostConfirmProvider>",
    );
  }
  return ctx;
}
