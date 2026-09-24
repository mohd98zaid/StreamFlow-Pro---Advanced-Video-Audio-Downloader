import React from "react";
import {
  Play,
  Pause,
  X,
  RotateCcw,
  FolderOpen,
  AlertCircle,
  Clock,
  Sparkles,
  CheckCircle2,
  Tv,
} from "lucide-react";
import { DownloadItem } from "../../types/download";
import { useQueueStore } from "../../stores/useQueueStore";
import { ProgressBar } from "../ui/ProgressBar";
import { Badge } from "../ui/Badge";
import { MediaArtwork } from "../media/MediaArtwork";
import { api } from "../../services/api";
import { extractVideoId } from "../../lib/helpers";
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
        <span className="flex items-center gap-1 text-[10px] font-bold text-success bg-success/15 px-2 py-0.5 rounded-full border border-success/30">
          <CheckCircle2 className="w-3 h-3" />
          <span>Completed</span>
        </span>
      );
    }
    if (isDownloading) {
      return (
        <span className="flex items-center gap-1.5 text-[10px] font-bold text-accent-cyan bg-accent-cyan/15 px-2 py-0.5 rounded-full border border-accent-cyan/30 animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-ping" />
          <span>Downloading</span>
        </span>
      );
    }
    if (isProcessing) {
      return (
        <span className="flex items-center gap-1 text-[10px] font-bold text-primary bg-primary/15 px-2 py-0.5 rounded-full border border-primary/30">
          <Sparkles className="w-3 h-3" />
          <span>Multiplexing</span>
        </span>
      );
    }
    if (isPaused) {
      return (
        <span className="flex items-center gap-1 text-[10px] font-bold text-warning bg-warning/15 px-2 py-0.5 rounded-full border border-warning/30">
          <Pause className="w-3 h-3" />
          <span>Paused</span>
        </span>
      );
    }
    if (isFailed) {
      return (
        <span className="flex items-center gap-1 text-[10px] font-bold text-danger bg-danger/15 px-2 py-0.5 rounded-full border border-danger/30">
          <AlertCircle className="w-3 h-3" />
          <span>Failed</span>
        </span>
      );
    }
    if (isCancelled) {
      return (
        <span className="flex items-center gap-1 text-[10px] font-medium text-foreground-subtle bg-surface-elevated px-2 py-0.5 rounded-full border border-border-hairline">
          <X className="w-3 h-3" />
          <span>Cancelled</span>
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[10px] font-medium text-foreground-subtle bg-surface-elevated px-2 py-0.5 rounded-full border border-border-hairline">
        <Clock className="w-3 h-3" />
        <span>Queued</span>
      </span>
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

  const handlePreview = () => {
    const vId = extractVideoId(item.url) || item.url;
    api.openPlayer(vId, item.title);
  };

  return (
    <div
      className={cn(
        "w-full glass-card border rounded-2xl p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition-all duration-200 group shadow-sm",
        isDownloading
          ? "border-accent-cyan/40 bg-accent-cyan/[0.03] shadow-glass-sm"
          : "border-border-glass hover:border-border-glass hover:bg-surface-elevated/40"
      )}
    >
      {/* Media Thumbnail & Meta Details */}
      <div className="flex items-center gap-4 min-w-0 w-full sm:w-auto flex-1">
        <MediaArtwork
          src={item.thumbnail_url}
          alt={item.title}
          type={item.download_type}
          duration={item.duration}
          size="md"
          glow={isDownloading}
          onPreview={handlePreview}
          className="rounded-xl flex-shrink-0"
        />

        {/* Info Column */}
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h4
              className="text-xs sm:text-sm font-bold text-foreground truncate max-w-md sm:max-w-lg cursor-pointer hover:text-primary transition-colors"
              title={item.title}
              onClick={isCompleted ? handleOpenFile : handlePreview}
            >
              {item.title}
            </h4>
            {getStatusBadge()}
          </div>

          {/* Subtitle Details */}
          <div className="flex items-center gap-2 text-[11px] text-foreground-muted flex-wrap">
            <span className="truncate max-w-[150px]">{item.channel || "Media"}</span>
            <span>•</span>
            <span className="font-semibold uppercase text-foreground-subtle">
              {item.download_type}
            </span>
            {item.quality && (
              <>
                <span>•</span>
                <span className="text-primary font-semibold">{item.quality}</span>
              </>
            )}
            {item.file_size ? (
              <>
                <span>•</span>
                <span className="font-mono">{formatBytes(item.file_size)}</span>
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
                className="h-1.5 rounded-full"
              />
              <div className="flex items-center justify-between text-[10px] text-foreground-subtle font-mono">
                <span className="font-bold text-foreground-muted">
                  {item.progress.toFixed(1)}%
                </span>
                {isDownloading && (
                  <div className="flex items-center gap-3">
                    <span className="text-accent-cyan">{item.speed || "Calculating…"}</span>
                    <span>ETA: {item.eta || "N/A"}</span>
                  </div>
                )}
                {isProcessing && <span className="text-primary">Merging audio & video…</span>}
                {isPaused && <span className="text-warning">Paused</span>}
              </div>
            </div>
          )}

          {/* Error Message if Failed */}
          {isFailed && item.error && (
            <p className="text-[11px] text-danger truncate max-w-md font-medium" title={item.error}>
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
            className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
          >
            <Pause className="w-3.5 h-3.5" />
          </button>
        )}

        {isPaused && (
          <button
            onClick={() => resumeItem(item.id)}
            title="Resume download"
            className="w-8 h-8 rounded-xl bg-primary/20 border border-primary/40 flex items-center justify-center text-primary hover:bg-primary/30 transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-primary" />
          </button>
        )}

        {/* Retry Button */}
        {(isFailed || isCancelled) && (
          <button
            onClick={() => retryItem(item.id)}
            title="Retry download"
            className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}

        {/* Completed actions: Play File / Open Folder */}
        {isCompleted && (
          <>
            <button
              onClick={handleOpenFile}
              title="Play downloaded media"
              className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-sm transition-all active:scale-95"
            >
              <Play className="w-3 h-3 fill-white" />
              <span>Play</span>
            </button>

            <button
              onClick={handleOpenFolder}
              title="Reveal in File Explorer"
              className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
            >
              <FolderOpen className="w-3.5 h-3.5" />
            </button>
          </>
        )}

        {/* Cancel / Remove Button */}
        <button
          onClick={() => (isCompleted || isFailed || isCancelled ? removeItem(item.id) : cancelItem(item.id))}
          title={isCompleted ? "Remove from list" : "Cancel download"}
          className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-subtle hover:text-danger hover:border-danger/30 hover:bg-danger/10 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
