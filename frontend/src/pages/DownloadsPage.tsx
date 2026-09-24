import React from "react";
import { DownloadCloud } from "lucide-react";
import { QueueSummary } from "../components/queue/QueueSummary";
import { QueueItemRow } from "../components/queue/QueueItemRow";
import { useQueueStore } from "../stores/useQueueStore";
import { DownloadItem } from "../types/download";
import { Button } from "../components/ui/Button";

interface DownloadsPageProps {
  onNewDownload: () => void;
}

export const DownloadsPage: React.FC<DownloadsPageProps> = ({ onNewDownload }) => {
  const { items } = useQueueStore();

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Downloads & Queue
          </h1>
          <p className="text-xs text-foreground-muted">
            Monitor real-time download progress, active worker threads, transfer speed, and completion status.
          </p>
        </div>

        <Button size="sm" onClick={onNewDownload}>
          <DownloadCloud className="w-4 h-4 mr-1.5" />
          <span>New Download</span>
        </Button>
      </div>

      {/* 1. Summary Bar */}
      <QueueSummary />

      {/* 2. Download Items List */}
      {items.length === 0 ? (
        <div className="w-full bg-surface border border-dashed border-border rounded-2xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-surface-elevated border border-border flex items-center justify-center mx-auto text-foreground-subtle">
            <DownloadCloud className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">
            Download queue is empty
          </h3>
          <p className="text-xs text-foreground-muted max-w-sm mx-auto">
            Paste a video or audio link to begin high-speed downloading.
          </p>
          <div className="pt-2">
            <Button size="sm" onClick={onNewDownload}>
              Paste Link to Download
            </Button>
          </div>
        </div>
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
