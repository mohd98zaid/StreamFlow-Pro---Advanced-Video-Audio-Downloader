import React from "react";
import {
  Play,
  Pause,
  FolderOpen,
  Tv,
  CheckCircle2,
  Activity,
  HardDrive,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { useQueueStore } from "../../stores/useQueueStore";
import { useSettingsStore } from "../../stores/useSettingsStore";
import { api } from "../../services/api";
import { MediaArtwork } from "./MediaArtwork";
import { ProgressBar } from "../ui/ProgressBar";
import { extractVideoId } from "../../lib/helpers";
import { cn } from "../../lib/utils";

export const MiniPlayer: React.FC = () => {
  const { items, summary, statusMessage, pauseItem, resumeItem, retryItem } = useQueueStore();
  const { config } = useSettingsStore();

  // Find the most relevant active or recent media item
  const activeItem =
    items.find((i) => i.status === "Downloading") ||
    items.find((i) => i.status === "Processing") ||
    items.find((i) => i.status === "Paused") ||
    items.find((i) => i.status === "Completed") ||
    items[0];

  const handleLaunchPlayer = (urlOrId: string, title: string) => {
    const vId = extractVideoId(urlOrId) || urlOrId;
    api.openPlayer(vId, title);
  };

  const handleOpenFolder = () => {
    if (activeItem?.file_path) {
      api.openFolder(activeItem.file_path);
    } else {
      api.openFolder(config.download_path);
    }
  };

  const handleOpenFile = () => {
    if (activeItem?.file_path) {
      api.openFile(activeItem.file_path);
    }
  };

  if (!activeItem) {
    // Idle state: Clean, translucent system telemetry bar
    return (
      <div className="h-10 w-full glass-panel border-t border-border-glass flex items-center justify-between px-4 text-xs text-foreground-muted select-none flex-shrink-0 z-40 transition-all">
        <div className="flex items-center gap-2.5 truncate">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
          <span className="font-medium text-foreground tracking-tight">
            StreamFlow Engine Active
          </span>
          <span className="text-foreground-subtle">•</span>
          <span className="text-foreground-subtle text-[11px] truncate">
            {statusMessage || "Waiting for media input..."}
          </span>
        </div>

        <div className="flex items-center gap-4 text-foreground-subtle text-[11px]">
          <button
            onClick={() => api.openFolder(config.download_path)}
            title="Open default download directory"
            className="flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span className="truncate max-w-[180px]">
              {config.download_path ? config.download_path.split(/[\\/]/).pop() || "Downloads" : "Downloads"}
            </span>
          </button>
          <span className="px-2 py-0.5 rounded-full bg-surface-elevated border border-border-hairline text-[10px] font-mono">
            {config.concurrent_downloads || 3} Threads
          </span>
        </div>
      </div>
    );
  }

  const isDownloading = activeItem.status === "Downloading";
  const isPaused = activeItem.status === "Paused";
  const isCompleted = activeItem.status === "Completed";
  const isProcessing = activeItem.status === "Processing";

  return (
    <div className="h-16 w-full glass-panel border-t border-border-glass flex items-center justify-between px-4 select-none flex-shrink-0 z-40 transition-all shadow-glass">
      {/* Left: Thumbnail & Media Details */}
      <div className="flex items-center gap-3 min-w-0 max-w-sm sm:max-w-md">
        <MediaArtwork
          src={activeItem.thumbnail_url}
          alt={activeItem.title}
          type={activeItem.download_type}
          size="sm"
          glow={false}
          className="w-14 h-10 rounded-xl"
        />

        <div className="min-w-0 space-y-0.5">
          <div className="flex items-center gap-2">
            <h4
              className="text-xs font-bold text-foreground truncate max-w-[220px] sm:max-w-[280px]"
              title={activeItem.title}
            >
              {activeItem.title}
            </h4>
            {isDownloading && (
              <span className="flex-shrink-0 px-1.5 py-0.2 rounded-full bg-accent-cyan/15 text-accent-cyan text-[10px] font-bold border border-accent-cyan/30 animate-pulse">
                {activeItem.progress.toFixed(0)}%
              </span>
            )}
            {isCompleted && (
              <span className="flex-shrink-0 px-1.5 py-0.2 rounded-full bg-success/15 text-success text-[10px] font-bold border border-success/30 flex items-center gap-1">
                <CheckCircle2 className="w-2.5 h-2.5" /> Ready
              </span>
            )}
            {isProcessing && (
              <span className="flex-shrink-0 px-1.5 py-0.2 rounded-full bg-primary/15 text-primary text-[10px] font-bold border border-primary/30 flex items-center gap-1">
                <Sparkles className="w-2.5 h-2.5" /> Merging
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-[10px] text-foreground-muted">
            <span className="truncate">{activeItem.channel || "Media"}</span>
            <span>•</span>
            <span className="uppercase text-foreground-subtle font-semibold">
              {activeItem.download_type} ({activeItem.quality || "HQ"})
            </span>
          </div>
        </div>
      </div>

      {/* Center: Live Progress Bar (During active downloads) */}
      {(isDownloading || isPaused || isProcessing) && (
        <div className="hidden md:flex flex-col items-center justify-center max-w-xs w-full px-4 space-y-1">
          <ProgressBar
            value={activeItem.progress}
            variant={isPaused ? "warning" : "cyan"}
            animated={isDownloading}
            className="h-1.5 w-full rounded-full"
          />
          <div className="flex items-center justify-between w-full text-[10px] text-foreground-subtle font-mono">
            <span>{activeItem.speed || (isPaused ? "Paused" : "Connecting...")}</span>
            <span>ETA: {activeItem.eta || "N/A"}</span>
          </div>
        </div>
      )}

      {/* Right: Quick Action Controls */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* Pause / Resume */}
        {isDownloading && (
          <button
            onClick={() => pauseItem(activeItem.id)}
            title="Pause download"
            className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
          >
            <Pause className="w-3.5 h-3.5" />
          </button>
        )}

        {isPaused && (
          <button
            onClick={() => resumeItem(activeItem.id)}
            title="Resume download"
            className="w-8 h-8 rounded-xl bg-primary/20 border border-primary/40 flex items-center justify-center text-primary hover:bg-primary/30 transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-primary" />
          </button>
        )}

        {/* Play File (if completed) */}
        {isCompleted && activeItem.file_path && (
          <button
            onClick={handleOpenFile}
            title="Play downloaded media"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-sm transition-all active:scale-95"
          >
            <Play className="w-3 h-3 fill-white" />
            <span>Play</span>
          </button>
        )}

        {/* Stream in Ad-Free Cinema Player */}
        <button
          onClick={() => handleLaunchPlayer(activeItem.url, activeItem.title)}
          title="Open in Yuma Studio Ad-Free Player"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl glass-card hover:bg-accent-cyan/10 hover:border-accent-cyan/40 text-foreground-muted hover:text-accent-cyan transition-colors text-xs font-medium"
        >
          <Tv className="w-3.5 h-3.5 text-accent-cyan" />
          <span className="hidden sm:inline">Ad-Free Stream</span>
        </button>

        {/* Open Folder */}
        <button
          onClick={handleOpenFolder}
          title="Reveal file in Windows Explorer"
          className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-muted hover:text-foreground transition-colors"
        >
          <FolderOpen className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
