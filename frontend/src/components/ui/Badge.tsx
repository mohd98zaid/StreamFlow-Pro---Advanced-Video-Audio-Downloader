import React from "react";
import { cn } from "../../lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "cyan" | "outline";
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = "default",
  children,
  ...props
}) => {
  const base =
    "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold select-none border transition-colors";

  const variants = {
    default: "bg-surface-elevated text-foreground-muted border-border",
    cyan: "bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30",
    success: "bg-success/15 text-success border-success/30",
    warning: "bg-warning/15 text-warning border-warning/30",
    danger: "bg-danger/15 text-danger border-danger/30",
    outline: "border-border text-foreground-muted",
  };

  return (
    <span className={cn(base, variants[variant], className)} {...props}>
      {children}
    </span>
  );
};
