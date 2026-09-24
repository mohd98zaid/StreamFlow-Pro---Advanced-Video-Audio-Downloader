import React from "react";
import { cn } from "../../lib/utils";

interface GlassSurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: "panel" | "card" | "floating" | "inset";
  glow?: boolean;
  className?: string;
}

export const GlassSurface: React.FC<GlassSurfaceProps> = ({
  children,
  variant = "panel",
  glow = false,
  className,
  ...props
}) => {
  return (
    <div
      className={cn(
        "relative transition-all duration-200",
        // Variants
        variant === "panel" && "glass-panel rounded-2xl sm:rounded-3xl shadow-glass",
        variant === "card" && "glass-card rounded-2xl shadow-glass-sm",
        variant === "floating" && "glass-panel rounded-3xl shadow-glass border border-border-glass",
        variant === "inset" && "bg-surface-elevated/70 border border-border-hairline rounded-2xl",
        className
      )}
      {...props}
    >
      {glow && (
        <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/15 via-accent-cyan/15 to-primary/10 rounded-3xl blur-xl opacity-60 pointer-events-none -z-10" />
      )}
      {children}
    </div>
  );
};
