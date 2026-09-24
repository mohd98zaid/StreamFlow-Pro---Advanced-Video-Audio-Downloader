import React from "react";
import { Play, FolderOpen, Trash2, CheckCircle2, AlertCircle, Video, Music } from "lucide-react";
import { DownloadItem } from "../../types/download";
import { useHistoryStore } from "../../stores/useHistoryStore";
import { MediaArtwork } from "../media/MediaArtwork";
import { formatBytes } from "../../lib/utils";

interface HistoryItemRowProps {
  item: DownloadItem;
}

export const HistoryItemRow: React.FC<HistoryItemRowProps> = ({ item }) => {
  const { deleteItem, openFile, openFolder } = useHistoryStore();

  const isCompleted = item.status === "Completed";
  const formattedDate = item.completed_at
    ? new Date(item.completed_at).toLocaleDateString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : item.created_at
    ? new Date(item.created_at).toLocaleDateString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div className="w-full glass-card border border-border-glass rounded-2xl p-3 flex items-center justify-between gap-4 hover:border-border-glass hover:bg-surface-elevated/40 transition-all duration-150 shadow-sm group">
      {/* Left: Media Artwork & Details */}
      <div className="flex items-center gap-3.5 min-w-0 flex-1">
        <MediaArtwork
          src={item.thumbnail_url}
          alt={item.title}
          type={item.download_type}
          duration={item.duration}
          size="sm"
          glow={false}
          onPreview={item.file_path ? () => openFile(item.file_path!) : undefined}
          className="rounded-xl flex-shrink-0"
        />

        {/* Info */}
        <div className="min-w-0 space-y-1">
          <h4
            className="text-xs sm:text-sm font-bold text-foreground truncate max-w-md cursor-pointer hover:text-primary transition-colors"
            title={item.title}
            onClick={() => item.file_path && openFile(item.file_path)}
          >
            {item.title}
          </h4>

          <div className="flex items-center gap-2 text-[11px] text-foreground-muted flex-wrap">
            <span className="uppercase font-bold text-[10px] text-primary">
              {item.download_type}
            </span>
            <span>•</span>
            <span className="font-medium">{item.quality || "Default"}</span>
            {item.file_size ? (
              <>
                <span>•</span>
                <span className="font-mono">{formatBytes(item.file_size)}</span>
              </>
            ) : null}
            <span>•</span>
            <span className="text-foreground-subtle flex items-center gap-1">
              {isCompleted ? (
                <>
                  <CheckCircle2 className="w-3 h-3 text-success inline" />
                  <span>{formattedDate}</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-3 h-3 text-danger inline" />
                  <span>{item.status}</span>
                </>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {isCompleted && item.file_path && (
          <>
            <button
              onClick={() => openFile(item.file_path!)}
              title="Play media file"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-sm transition-all active:scale-95"
            >
              <Play className="w-3 h-3 fill-white" />
              <span>Play</span>
            </button>

            <button
              onClick={() => openFolder(item.file_path!)}
              title="Reveal in File Explorer"
              className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-muted hover:text-foreground transition-colors"
            >
              <FolderOpen className="w-3.5 h-3.5" />
            </button>
          </>
        )}

        <button
          onClick={() => deleteItem(item.id)}
          title="Remove from history"
          className="w-8 h-8 rounded-xl glass-card flex items-center justify-center text-foreground-subtle hover:text-danger hover:border-danger/30 hover:bg-danger/10 transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
