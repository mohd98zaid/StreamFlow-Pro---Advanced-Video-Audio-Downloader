import React from "react";
import { DownloadCloud, Sparkles } from "lucide-react";
import { QueueSummary } from "../components/queue/QueueSummary";
import { QueueItemRow } from "../components/queue/QueueItemRow";
import { useQueueStore } from "../stores/useQueueStore";
import { DownloadItem } from "../types/download";
import { GlassSurface } from "../components/ui/GlassSurface";

interface DownloadsPageProps {
  onNewDownload: () => void;
}

export const DownloadsPage: React.FC<DownloadsPageProps> = ({ onNewDownload }) => {
  const { items } = useQueueStore();

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto animate-fade-in select-none">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <span>Downloads & Active Queue</span>
          </h1>
          <p className="text-xs text-foreground-muted">
            Monitor real-time download telemetry, multi-threaded progress, speeds, and FFmpeg multiplexing.
          </p>
        </div>

        <button
          onClick={onNewDownload}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-sm transition-all active:scale-95"
        >
          <DownloadCloud className="w-4 h-4" />
          <span>New Download</span>
        </button>
      </div>

      {/* 1. Contextual Summary Bar */}
      <QueueSummary />

      {/* 2. Download Items List */}
      {items.length === 0 ? (
        <GlassSurface
          variant="panel"
          className="border-dashed border-border-glass p-12 text-center space-y-3"
        >
          <div className="w-14 h-14 rounded-2xl bg-surface-elevated/80 border border-border-glass flex items-center justify-center mx-auto text-foreground-subtle shadow-inner">
            <DownloadCloud className="w-7 h-7 text-primary/60" />
          </div>
          <h3 className="text-sm font-bold text-foreground">
            Download queue is clear
          </h3>
          <p className="text-xs text-foreground-muted max-w-sm mx-auto leading-relaxed">
            Paste any video or audio link to begin high-speed multi-threaded downloading.
          </p>
          <div className="pt-2">
            <button
              onClick={onNewDownload}
              className="px-4 py-2 rounded-xl bg-surface-elevated hover:bg-border/40 border border-border-glass text-xs font-semibold text-foreground transition-colors"
            >
              Paste Link to Download
            </button>
          </div>
        </GlassSurface>
      ) : (
        <div className="space-y-3">
          {items.map((item: DownloadItem) => (
            <QueueItemRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
};
