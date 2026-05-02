import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "rounded-[2px] font-medium transition-colors duration-[80ms] ease-out",
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan focus-visible:ring-offset-1 focus-visible:ring-offset-app-void",
    "disabled:pointer-events-none disabled:opacity-50",
    "select-none uppercase tracking-wide",
  ].join(" "),
  {
    variants: {
      variant: {
        // Primary: cyan fill with subtle inner glow
        default:
          "bg-cyan text-app-void border border-cyan shadow-[inset_0_0_0_1px_rgba(31,182,255,0.3)] hover:bg-cyan/90",
        // Ghost: transparent w/ iron border, hover→cyan
        ghost:
          "bg-transparent border border-iron text-bone hover:border-cyan hover:text-cyan",
        // Outline alias
        outline:
          "bg-transparent border border-iron text-bone hover:border-iron-bright hover:bg-app-elev-1",
        // Danger
        destructive:
          "bg-transparent border border-red text-red hover:bg-red/10",
        // Magenta accent
        magenta:
          "bg-transparent border border-magenta text-magenta hover:bg-magenta/10",
        // Subtle inline
        subtle:
          "bg-app-elev-1 border border-iron text-bone hover:border-iron-bright",
        // Amber emphasis
        amber:
          "bg-transparent border border-amber text-amber hover:bg-amber/10",
      },
      size: {
        sm: "h-7 px-2 text-xs",
        default: "h-8 px-3 text-sm",
        lg: "h-10 px-4 text-md",
        icon: "h-8 w-8 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  children?: ReactNode;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  children,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {children}
    </Comp>
  );
}

export { buttonVariants };
