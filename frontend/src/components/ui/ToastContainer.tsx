import React from "react";
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-react";
import { useToastStore, ToastItem } from "../../stores/useToastStore";
import { cn } from "../../lib/utils";

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-12 right-6 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast: ToastItem) => (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto flex items-start gap-3 p-3.5 rounded-2xl glass-panel shadow-glass border animate-fade-in transition-all select-text",
            toast.type === "success" && "border-success/30 bg-surface/90 text-foreground",
            toast.type === "error" && "border-danger/30 bg-surface/90 text-foreground",
            toast.type === "warning" && "border-warning/30 bg-surface/90 text-foreground",
            toast.type === "info" && "border-primary/30 bg-surface/90 text-foreground"
          )}
        >
          {/* Icon */}
          <div className="flex-shrink-0 mt-0.5">
            {toast.type === "success" && <CheckCircle2 className="w-4 h-4 text-success" />}
            {toast.type === "error" && <AlertCircle className="w-4 h-4 text-danger" />}
            {toast.type === "warning" && <AlertTriangle className="w-4 h-4 text-warning" />}
            {toast.type === "info" && <Info className="w-4 h-4 text-primary" />}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-0.5">
            {toast.title && (
              <h5 className="text-xs font-bold text-foreground tracking-tight">
                {toast.title}
              </h5>
            )}
            <p className="text-xs text-foreground-muted leading-relaxed break-words">
              {toast.message}
            </p>
          </div>

          {/* Dismiss */}
          <button
            onClick={() => removeToast(toast.id)}
            className="flex-shrink-0 text-foreground-subtle hover:text-foreground p-0.5 rounded-lg hover:bg-surface-elevated transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
};
