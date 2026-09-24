import React from "react";
import {
  Play,
  Pause,
  X,
  RotateCcw,
  FolderOpen,
  FileCheck,
  AlertCircle,
  Clock,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import { DownloadItem } from "../../types/download";
import { useQueueStore } from "../../stores/useQueueStore";
import { ProgressBar } from "../ui/ProgressBar";
import { Badge } from "../ui/Badge";
import { api } from "../../services/api";
import { formatBytes, cn } from "../../lib/utils";

interface QueueItemRowProps {
  item: DownloadItem;
}

export const QueueItemRow: React.FC<QueueItemRowProps> = ({ item }) => {
  const { pauseItem, resumeItem, cancelItem, retryItem, removeItem } = useQueueStore();

  const isDownloading = item.status === "Downloading";
  const isProcessing = item.status === "Processing";
  const isPaused = item.status === "Paused";
  const isCompleted = item.status === "Completed";
  const isFailed = item.status === "Failed";
  const isCancelled = item.status === "Cancelled";

  const getStatusBadge = () => {
    if (isCompleted) {
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="w-3 h-3" />
          <span>Completed</span>
        </Badge>
      );
    }
    if (isDownloading) {
      return (
        <Badge variant="cyan" className="gap-1 animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-ping" />
          <span>Downloading</span>
        </Badge>
      );
    }
    if (isProcessing) {
      return (
        <Badge variant="cyan" className="gap-1">
          <Sparkles className="w-3 h-3" />
          <span>Merging Audio/Video</span>
        </Badge>
      );
    }
    if (isPaused) {
      return (
        <Badge variant="warning" className="gap-1">
          <Pause className="w-3 h-3" />
          <span>Paused</span>
        </Badge>
      );
    }
    if (isFailed) {
      return (
        <Badge variant="danger" className="gap-1">
          <AlertCircle className="w-3 h-3" />
          <span>Failed</span>
        </Badge>
      );
    }
    if (isCancelled) {
      return (
        <Badge variant="outline" className="gap-1">
          <X className="w-3 h-3" />
          <span>Cancelled</span>
        </Badge>
      );
    }
    return (
      <Badge variant="default" className="gap-1">
        <Clock className="w-3 h-3" />
        <span>Queued</span>
      </Badge>
    );
  };

  const handleOpenFile = () => {
    if (item.file_path) {
      api.openFile(item.file_path);
    }
  };

  const handleOpenFolder = () => {
    if (item.file_path) {
      api.openFolder(item.file_path);
    } else {
      api.openFolder();
    }
  };

  return (
    <div
      className={cn(
        "w-full bg-surface border rounded-xl p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition-all duration-150 group shadow-sm",
        isDownloading
          ? "border-accent-cyan/40 bg-accent-cyan/[0.02]"
          : "border-border hover:border-border/80"
      )}
    >
      {/* Media Thumbnail & Meta Details */}
      <div className="flex items-center gap-3.5 min-w-0 w-full sm:w-auto flex-1">
        <div className="relative w-28 h-18 bg-black/40 rounded-lg overflow-hidden flex-shrink-0 border border-border/60">
          {item.thumbnail_url ? (
            <img
              src={item.thumbnail_url}
              alt={item.title}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-foreground-subtle text-[10px]">
              Thumbnail
            </div>
          )}

          {item.duration && (
            <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[9px] font-mono px-1 rounded">
              {item.duration}
            </span>
          )}
        </div>

        {/* Info Column */}
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-center gap-2">
            <h4
              className="text-xs sm:text-sm font-semibold text-foreground truncate max-w-lg"
              title={item.title}
            >
              {item.title}
            </h4>
            {getStatusBadge()}
          </div>

          {/* Subtitle Details */}
          <div className="flex items-center gap-2 text-[11px] text-foreground-muted flex-wrap">
            <span>{item.channel || "Media"}</span>
            <span>•</span>
            <span className="font-semibold uppercase text-foreground-subtle">
              {item.download_type}
            </span>
            {item.quality && (
              <>
                <span>•</span>
                <span className="text-primary font-medium">{item.quality}</span>
              </>
            )}
            {item.file_size ? (
              <>
                <span>•</span>
                <span>{formatBytes(item.file_size)}</span>
              </>
            ) : null}
          </div>

          {/* Progress Bar & Real-time Metrics (During download or paused) */}
          {(isDownloading || isProcessing || isPaused || item.progress > 0) && !isCompleted && (
            <div className="space-y-1 pt-1 max-w-md">
              <ProgressBar
                value={item.progress}
                variant={isPaused ? "warning" : "cyan"}
                animated={isDownloading}
              />
              <div className="flex items-center justify-between text-[10px] text-foreground-subtle font-mono">
                <span className="font-semibold text-foreground-muted">
                  {item.progress.toFixed(1)}%
                </span>
                {isDownloading && (
                  <div className="flex items-center gap-3">
                    <span>{item.speed || "Calculating…"}</span>
                    <span>ETA: {item.eta || "N/A"}</span>
                  </div>
                )}
                {isProcessing && <span>Merging formats via FFmpeg…</span>}
                {isPaused && <span className="text-warning">Paused</span>}
              </div>
            </div>
          )}

          {/* Error Message if Failed */}
          {isFailed && item.error && (
            <p className="text-[11px] text-danger truncate max-w-md" title={item.error}>
              Error: {item.error}
            </p>
          )}
        </div>
      </div>

      {/* Right Column: Context Action Controls */}
      <div className="flex items-center gap-1.5 flex-shrink-0 self-end sm:self-center">
        {/* Pause / Resume */}
        {isDownloading && (
          <button
            onClick={() => pauseItem(item.id)}
            title="Pause download"
            className="w-8 h-8 rounded-lg border border-border/80 flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
          >
            <Pause className="w-3.5 h-3.5" />
          </button>
        )}

        {isPaused && (
          <button
            onClick={() => resumeItem(item.id)}
            title="Resume download"
            className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center text-primary hover:bg-primary/20 transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-primary" />
          </button>
        )}

        {/* Retry Button */}
        {(isFailed || isCancelled) && (
          <button
            onClick={() => retryItem(item.id)}
            title="Retry download"
            className="w-8 h-8 rounded-lg border border-border/80 flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}

        {/* Completed actions: Open File / Open Folder */}
        {isCompleted && (
          <>
            <button
              onClick={handleOpenFile}
              title="Play downloaded media"
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface-elevated border border-border text-xs font-semibold text-foreground hover:bg-border/60 transition-colors"
            >
              <Play className="w-3 h-3 fill-foreground" />
              <span>Play</span>
            </button>

            <button
              onClick={handleOpenFolder}
              title="Reveal in File Explorer"
              className="w-8 h-8 rounded-lg border border-border/80 flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
            >
              <FolderOpen className="w-3.5 h-3.5" />
            </button>
          </>
        )}

        {/* Cancel / Remove Button */}
        <button
          onClick={() => (isCompleted || isFailed || isCancelled ? removeItem(item.id) : cancelItem(item.id))}
          title={isCompleted ? "Remove from list" : "Cancel download"}
          className="w-8 h-8 rounded-lg border border-border/80 flex items-center justify-center text-foreground-subtle hover:text-danger hover:border-danger/30 hover:bg-danger/10 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
