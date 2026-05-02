import { useSpend } from "@/lib/api";
import { gbp, cn } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";

export function SpendIndicator() {
  const { data, isLoading, isError } = useSpend();

  const spentCents = data?.spent_cents ?? 0;
  const budgetCents = data?.budget_cents ?? 100;
  const pct =
    data?.budget_pct ?? (budgetCents > 0 ? spentCents / budgetCents : 0);
  const pctClamped = Math.max(0, Math.min(1, pct));

  // <60% mute, 60-90% amber, ≥90% magenta + pulse
  let tier: "ok" | "warn" | "critical" = "ok";
  if (pctClamped >= 0.9) tier = "critical";
  else if (pctClamped >= 0.6) tier = "warn";

  const textClass = {
    ok: "text-mute",
    warn: "text-amber",
    critical: "text-magenta animate-[pulse-soft_1s_linear_infinite]",
  }[tier];

  const barClass = {
    ok: "bg-mute",
    warn: "bg-amber",
    critical: "bg-magenta",
  }[tier];

  if (isError) {
    return (
      <span className="font-mono text-xs uppercase tracking-wide text-red">
        SPEND OFFLINE
      </span>
    );
  }

  return (
    <Tooltip
      content={
        <div className="space-y-0.5">
          <div className="font-mono uppercase tracking-wide">SESSION SPEND</div>
          <div className="text-dim">Polls every 4s</div>
        </div>
      }
      side="bottom"
    >
      <div className="flex flex-col gap-0.5 min-w-[100px]">
        <span
          className={cn(
            "font-mono text-xs tabular-nums leading-none",
            textClass,
          )}
        >
          {isLoading
            ? "—"
            : gbp(spentCents, { cents: true, decimals: 2 })}
          <span className="text-dim"> / </span>
          {gbp(budgetCents, { cents: true, decimals: 2 })}
        </span>
        <div className="relative h-px w-full bg-iron">
          <div
            className={cn("absolute inset-y-0 left-0", barClass)}
            style={{ width: `${pctClamped * 100}%` }}
          />
        </div>
      </div>
    </Tooltip>
  );
}
