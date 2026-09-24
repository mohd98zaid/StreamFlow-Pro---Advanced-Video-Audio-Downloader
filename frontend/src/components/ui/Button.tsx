import React from "react";
import { cn } from "../../lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "sm" | "md" | "lg" | "icon";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, disabled, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 select-none focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]";

    const variants = {
      primary:
        "bg-primary text-white hover:bg-primary-hover shadow-sm hover:shadow",
      secondary:
        "bg-surface-elevated text-foreground hover:bg-border/50 border border-border/60",
      outline:
        "border border-border text-foreground hover:bg-surface-elevated/70",
      ghost:
        "text-foreground-muted hover:text-foreground hover:bg-surface-elevated/60",
      danger:
        "bg-danger/15 text-danger hover:bg-danger/25 border border-danger/30",
    };

    const sizes = {
      sm: "h-8 px-3 text-xs gap-1.5",
      md: "h-9 px-4 text-sm gap-2",
      lg: "h-11 px-5 text-base gap-2.5",
      icon: "h-9 w-9 p-0",
    };

    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
