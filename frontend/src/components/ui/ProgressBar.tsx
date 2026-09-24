import React from "react";
import { cn } from "../../lib/utils";

interface ProgressBarProps {
  value: number; // 0 to 100
  className?: string;
  variant?: "primary" | "cyan" | "success" | "warning";
  animated?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  className,
  variant = "cyan",
  animated = false,
}) => {
  const clamped = Math.min(100, Math.max(0, value));

  const variants = {
    primary: "bg-primary",
    cyan: "bg-gradient-to-r from-accent-cyan to-primary",
    success: "bg-success",
    warning: "bg-warning",
  };

  return (
    <div
      className={cn(
        "h-1.5 w-full bg-border/40 rounded-full overflow-hidden relative",
        className
      )}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-200 ease-out",
          variants[variant],
          animated && "animate-pulse"
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
};
