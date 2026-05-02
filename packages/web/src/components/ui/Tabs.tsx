import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;

export function TabsList({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "inline-flex h-9 items-end gap-0 border-b border-iron text-mute w-full",
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap px-3 h-9",
        "text-md font-medium uppercase tracking-wide",
        "transition-colors duration-[80ms] ease-out",
        "border-b-2 border-transparent -mb-px",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan",
        "disabled:pointer-events-none disabled:opacity-50",
        "data-[state=active]:text-cyan data-[state=active]:border-cyan",
        "hover:text-bone",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn(
        "mt-3 focus-visible:outline-none",
        className,
      )}
      {...props}
    />
  );
}
