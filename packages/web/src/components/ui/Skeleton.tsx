import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "shimmer rounded-[2px] bg-app-elev-1 overflow-hidden",
        className,
      )}
      aria-hidden="true"
      {...props}
    />
  );
}
