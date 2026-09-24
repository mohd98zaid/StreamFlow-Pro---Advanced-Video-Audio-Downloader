import React from "react";
import { Play, FolderOpen, Trash2, CheckCircle2, AlertCircle, Clock, Video, Music } from "lucide-react";
import { DownloadItem } from "../../types/download";
import { useHistoryStore } from "../../stores/useHistoryStore";
import { formatBytes } from "../../lib/utils";

interface HistoryItemRowProps {
  item: DownloadItem;
}

export const HistoryItemRow: React.FC<HistoryItemRowProps> = ({ item }) => {
  const { deleteItem, openFile, openFolder } = useHistoryStore();

  const isCompleted = item.status === "Completed";
  const formattedDate = item.completed_at
    ? new Date(item.completed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : item.created_at
    ? new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <div className="w-full bg-surface border border-border rounded-xl p-3 flex items-center justify-between gap-4 hover:border-border/80 transition-all shadow-sm group">
      {/* Left: Thumbnail & Details */}
      <div className="flex items-center gap-3.5 min-w-0 flex-1">
        <div className="relative w-24 h-15 bg-black/40 rounded-lg overflow-hidden flex-shrink-0 border border-border/60">
          {item.thumbnail_url ? (
            <img
              src={item.thumbnail_url}
              alt={item.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-foreground-subtle text-xs">
              {item.download_type === "audio" ? <Music className="w-5 h-5" /> : <Video className="w-5 h-5" />}
            </div>
          )}

          {item.duration && (
            <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[9px] font-mono px-1 rounded">
              {item.duration}
            </span>
          )}
        </div>

        {/* Info */}
        <div className="min-w-0 space-y-1">
          <h4
            className="text-xs sm:text-sm font-semibold text-foreground truncate max-w-md cursor-pointer hover:text-primary transition-colors"
            title={item.title}
            onClick={() => item.file_path && openFile(item.file_path)}
          >
            {item.title}
          </h4>

          <div className="flex items-center gap-2 text-[11px] text-foreground-muted flex-wrap">
            <span className="uppercase font-semibold text-[10px] text-primary">
              {item.download_type}
            </span>
            <span>•</span>
            <span>{item.quality || "Default"}</span>
            {item.file_size ? (
              <>
                <span>•</span>
                <span>{formatBytes(item.file_size)}</span>
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
      <div className="flex items-center gap-1 flex-shrink-0">
        {isCompleted && item.file_path && (
          <>
            <button
              onClick={() => openFile(item.file_path!)}
              title="Play media"
              className="w-8 h-8 rounded-lg bg-surface-elevated hover:bg-border/60 border border-border flex items-center justify-center text-foreground hover:text-primary transition-colors"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
            </button>

            <button
              onClick={() => openFolder(item.file_path!)}
              title="Open folder in File Explorer"
              className="w-8 h-8 rounded-lg border border-border/80 flex items-center justify-center text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
            >
              <FolderOpen className="w-3.5 h-3.5" />
            </button>
          </>
        )}

        <button
          onClick={() => deleteItem(item.id)}
          title="Delete history entry"
          className="w-8 h-8 rounded-lg border border-border/80 flex items-center justify-center text-foreground-subtle hover:text-danger hover:border-danger/30 hover:bg-danger/10 transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
