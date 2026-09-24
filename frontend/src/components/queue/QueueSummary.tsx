import React from "react";
import { Play, Pause, Trash2, CheckCircle2, Clock, Radio, AlertCircle } from "lucide-react";
import { useQueueStore } from "../../stores/useQueueStore";
import { GlassSurface } from "../ui/GlassSurface";

export const QueueSummary: React.FC = () => {
  const { summary, pauseAll, resumeAll, clearCompleted } = useQueueStore();

  return (
    <GlassSurface
      variant="panel"
      className="p-3.5 px-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-glass-sm"
    >
      {/* Compact Contextual Status Indicators */}
      <div className="flex items-center gap-2 sm:gap-3 flex-wrap text-xs">
        <span className="font-semibold text-foreground-muted mr-1">Queue:</span>

        {summary.active > 0 && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-accent-cyan/15 text-accent-cyan font-bold border border-accent-cyan/25 animate-pulse">
            <Radio className="w-3 h-3" />
            <span>{summary.active} Downloading</span>
          </span>
        )}

        {summary.queued > 0 && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-warning/10 text-warning font-semibold border border-warning/20">
            <Clock className="w-3 h-3" />
            <span>{summary.queued} Queued</span>
          </span>
        )}

        {summary.completed > 0 && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-success/10 text-success font-semibold border border-success/20">
            <CheckCircle2 className="w-3 h-3" />
            <span>{summary.completed} Completed</span>
          </span>
        )}

        {summary.failed > 0 && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-danger/10 text-danger font-semibold border border-danger/20">
            <AlertCircle className="w-3 h-3" />
            <span>{summary.failed} Failed</span>
          </span>
        )}

        {summary.total === 0 && (
          <span className="text-foreground-subtle text-xs">No active items</span>
        )}
      </div>

      {/* Bulk Control Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        {summary.active > 0 && (
          <button
            onClick={pauseAll}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-card hover:bg-surface-elevated text-xs font-semibold text-foreground-muted hover:text-foreground transition-colors"
          >
            <Pause className="w-3.5 h-3.5" />
            <span>Pause All</span>
          </button>
        )}

        {summary.paused > 0 && (
          <button
            onClick={resumeAll}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary/15 hover:bg-primary/25 border border-primary/30 text-xs font-semibold text-primary transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-primary" />
            <span>Resume All</span>
          </button>
        )}

        {summary.completed > 0 && (
          <button
            onClick={clearCompleted}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl hover:bg-surface-elevated text-xs font-semibold text-foreground-subtle hover:text-foreground transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Completed</span>
          </button>
        )}
      </div>
    </GlassSurface>
  );
};
