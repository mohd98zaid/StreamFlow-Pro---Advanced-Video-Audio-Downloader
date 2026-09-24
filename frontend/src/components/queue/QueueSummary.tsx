import React from "react";
import { Play, Pause, Trash2, CheckCircle2, Clock, Activity, Radio } from "lucide-react";
import { useQueueStore } from "../../stores/useQueueStore";
import { Button } from "../ui/Button";

export const QueueSummary: React.FC = () => {
  const { summary, pauseAll, resumeAll, clearCompleted } = useQueueStore();

  return (
    <div className="w-full bg-surface border border-border rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
      {/* Metrics Row */}
      <div className="flex items-center gap-4 sm:gap-6 flex-wrap">
        <div>
          <span className="block text-[11px] font-semibold text-foreground-muted uppercase tracking-wider">
            Total Queue
          </span>
          <span className="text-xl font-bold text-foreground tracking-tight">
            {summary.total}
          </span>
        </div>

        <div className="h-8 w-[1px] bg-border/60 hidden sm:block" />

        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-accent-cyan animate-pulse" />
          <div>
            <span className="block text-[11px] font-semibold text-foreground-muted uppercase tracking-wider">
              Active
            </span>
            <span className="text-xl font-bold text-accent-cyan tracking-tight">
              {summary.active}
            </span>
          </div>
        </div>

        <div className="h-8 w-[1px] bg-border/60 hidden sm:block" />

        <div className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-warning" />
          <div>
            <span className="block text-[11px] font-semibold text-foreground-muted uppercase tracking-wider">
              Queued
            </span>
            <span className="text-xl font-bold text-warning tracking-tight">
              {summary.queued}
            </span>
          </div>
        </div>

        <div className="h-8 w-[1px] bg-border/60 hidden sm:block" />

        <div className="flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-success" />
          <div>
            <span className="block text-[11px] font-semibold text-foreground-muted uppercase tracking-wider">
              Completed
            </span>
            <span className="text-xl font-bold text-success tracking-tight">
              {summary.completed}
            </span>
          </div>
        </div>
      </div>

      {/* Bulk Control Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        {summary.active > 0 && (
          <Button
            size="sm"
            variant="secondary"
            onClick={pauseAll}
            className="text-xs"
          >
            <Pause className="w-3.5 h-3.5 mr-1" />
            <span>Pause All</span>
          </Button>
        )}

        {summary.paused > 0 && (
          <Button
            size="sm"
            variant="secondary"
            onClick={resumeAll}
            className="text-xs text-accent-cyan"
          >
            <Play className="w-3.5 h-3.5 mr-1 fill-accent-cyan" />
            <span>Resume All</span>
          </Button>
        )}

        {summary.completed > 0 && (
          <Button
            size="sm"
            variant="ghost"
            onClick={clearCompleted}
            className="text-xs text-foreground-muted hover:text-foreground"
          >
            <Trash2 className="w-3.5 h-3.5 mr-1 text-foreground-subtle" />
            <span>Clear Completed</span>
          </Button>
        )}
      </div>
    </div>
  );
};
