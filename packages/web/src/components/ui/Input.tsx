import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, type = "text", ...props }: InputProps) {
  return (
    <input
      type={type}
      className={cn(
        "flex h-8 w-full rounded-[2px] border border-iron bg-app-elev-1 px-2 py-1",
        "text-sm text-bone placeholder:text-dim",
        "transition-colors duration-[80ms] ease-out",
        "focus-visible:outline-none focus-visible:border-cyan focus-visible:ring-1 focus-visible:ring-cyan",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium",
        className,
      )}
      {...props}
    />
  );
}
