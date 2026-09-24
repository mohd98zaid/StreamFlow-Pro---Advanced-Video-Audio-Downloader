import React from "react";
import { Activity, HardDrive, CheckCircle2 } from "lucide-react";
import { useQueueStore } from "../../stores/useQueueStore";
import { useSettingsStore } from "../../stores/useSettingsStore";

export const StatusFooter: React.FC = () => {
  const { statusMessage, summary } = useQueueStore();
  const { config } = useSettingsStore();

  return (
    <footer className="h-7 w-full bg-surface border-t border-border flex items-center justify-between px-3 text-[11px] text-foreground-muted select-none flex-shrink-0 z-40">
      <div className="flex items-center gap-2 truncate max-w-[60%]">
        <Activity className="w-3.5 h-3.5 text-primary animate-pulse flex-shrink-0" />
        <span className="truncate">{statusMessage || "Engine Ready"}</span>
      </div>

      <div className="flex items-center gap-4 text-foreground-subtle text-[10px]">
        {summary.active > 0 && (
          <span className="text-accent-cyan font-medium">
            {summary.active} Active Download{summary.active > 1 ? "s" : ""}
          </span>
        )}
        <div className="flex items-center gap-1">
          <HardDrive className="w-3 h-3 text-foreground-subtle" />
          <span className="truncate max-w-[200px]" title={config.download_path}>
            {config.download_path ? config.download_path.split(/[\\/]/).pop() || "Downloads" : "Downloads"}
          </span>
        </div>
        <span className="text-foreground-subtle">Ready</span>
      </div>
    </footer>
  );
};
