import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  [
    "inline-flex items-center gap-1 rounded-[2px] border px-1.5 py-0.5",
    "text-xs font-medium uppercase tracking-wide",
    "transition-colors duration-[80ms]",
  ].join(" "),
  {
    variants: {
      variant: {
        default: "border-iron bg-app-elev-1 text-bone",
        cyan: "border-cyan/40 bg-cyan/10 text-cyan",
        amber: "border-amber/40 bg-amber/10 text-amber",
        emerald: "border-emerald/40 bg-emerald/10 text-emerald",
        red: "border-red/40 bg-red/10 text-red",
        magenta: "border-magenta/40 bg-magenta/10 text-magenta",
        outline: "border-iron text-mute bg-transparent",
        mono: "border-iron bg-app-elev-1 text-bone font-mono",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** When set, applies score-band tinting (red/amber/emerald) and overrides variant. */
  score?: number;
}

export function Badge({ className, variant, score, ...props }: BadgeProps) {
  if (typeof score === "number") {
    const cls =
      score >= 70
        ? "border-emerald/40 bg-emerald/10 text-emerald"
        : score >= 50
          ? "border-amber/40 bg-amber/10 text-amber"
          : "border-red/40 bg-red/10 text-red";
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-[2px] border px-1.5 py-0.5 text-xs font-mono font-medium tracking-wide",
          cls,
          className,
        )}
        {...props}
      />
    );
  }
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

/**
 * Square 32×32 score badge with mono numeral and segmented bar below.
 */
export interface ScoreBadgeProps {
  score: number;
  className?: string;
}

export function ScoreBadge({ score, className }: ScoreBadgeProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const tier =
    clamped >= 70
      ? { bg: "bg-emerald", text: "text-app-void", bar: "bg-emerald" }
      : clamped >= 50
        ? { bg: "bg-amber", text: "text-app-void", bar: "bg-amber" }
        : { bg: "bg-red", text: "text-bone", bar: "bg-red" };

  // Segmented bar — 10 segments, fill proportional to score
  const segments = 10;
  const filled = Math.round((clamped / 100) * segments);

  return (
    <div className={cn("inline-flex flex-col gap-0.5", className)}>
      <div
        className={cn(
          "size-8 grid place-items-center rounded-[2px] font-mono text-md font-semibold leading-none",
          tier.bg,
          tier.text,
        )}
      >
        {clamped}
      </div>
      <div className="flex gap-px h-1 w-8">
        {Array.from({ length: segments }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "flex-1",
              i < filled ? tier.bar : "bg-iron",
            )}
          />
        ))}
      </div>
    </div>
  );
}
