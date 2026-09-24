import React, { useEffect, useState } from "react";
import { Search, Trash2, FolderOpen, RefreshCw, Film, CheckCircle2, AlertTriangle, X } from "lucide-react";
import { useHistoryStore } from "../stores/useHistoryStore";
import { HistoryItemRow } from "../components/history/HistoryItemRow";
import { DownloadItem } from "../types/download";
import { GlassSurface } from "../components/ui/GlassSurface";
import { useToastStore } from "../stores/useToastStore";

export const HistoryPage: React.FC = () => {
  const {
    items,
    stats,
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    fetchHistory,
    fetchStats,
    clearAll,
    openFolder,
    isLoading,
  } = useHistoryStore();

  const toast = useToastStore();
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  useEffect(() => {
    fetchHistory();
    fetchStats();
  }, []);

  const handleConfirmClear = async () => {
    await clearAll();
    setShowClearConfirm(false);
    toast.info("Media history has been cleared", "History Cleared");
  };

  const statusOptions = ["All", "Completed", "Failed", "Cancelled"];

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto animate-fade-in select-none">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>Media Library</span>
            <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-surface-elevated text-foreground-muted border border-border-hairline uppercase">
              SQLite Archive
            </span>
          </h1>
          <p className="text-xs text-foreground-muted">
            Locally indexed vault of completed and processed media downloads.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => openFolder()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-card hover:bg-surface-elevated text-xs font-semibold text-foreground transition-colors"
          >
            <FolderOpen className="w-3.5 h-3.5 text-foreground-subtle" />
            <span>Open Folder</span>
          </button>

          {items.length > 0 && (
            <button
              onClick={() => setShowClearConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-danger/10 hover:bg-danger/20 border border-danger/20 text-xs font-semibold text-danger transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear History</span>
            </button>
          )}
        </div>
      </div>

      {/* Subtle Compact Stats Bar (YDS Media Workstation Style) */}
      {stats && (
        <GlassSurface
          variant="panel"
          className="p-3.5 px-5 flex items-center justify-between flex-wrap gap-4 text-xs shadow-glass-sm"
        >
          <div className="flex items-center gap-6 flex-wrap">
            <div>
              <span className="text-foreground-subtle text-[11px] block">Total Downloads</span>
              <span className="font-bold text-foreground text-sm">{stats.total_downloads}</span>
            </div>

            <div className="h-6 w-[1px] bg-border-hairline hidden sm:block" />

            <div>
              <span className="text-foreground-subtle text-[11px] block">Completed Files</span>
              <span className="font-bold text-primary text-sm">{stats.successful_downloads}</span>
            </div>

            <div className="h-6 w-[1px] bg-border-hairline hidden sm:block" />

            <div>
              <span className="text-foreground-subtle text-[11px] block">Total Size</span>
              <span className="font-bold text-accent-cyan text-sm">{stats.total_size_formatted}</span>
            </div>

            <div className="h-6 w-[1px] bg-border-hairline hidden sm:block" />

            <div>
              <span className="text-foreground-subtle text-[11px] block">Success Rate</span>
              <span className="font-bold text-success text-sm">{stats.success_rate.toFixed(0)}%</span>
            </div>
          </div>
        </GlassSurface>
      )}

      {/* Search & Status Filters */}
      <GlassSurface
        variant="panel"
        className="p-3 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-glass-sm"
      >
        {/* Search input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search downloads or channel…"
            className="w-full h-8.5 pl-8 pr-3 bg-surface-elevated/70 border border-border-glass rounded-xl text-xs text-foreground placeholder:text-foreground-subtle focus:outline-none focus:border-primary transition-colors"
          />
        </div>

        {/* Status Filter Chips */}
        <div className="flex items-center gap-1.5 self-start sm:self-center">
          {statusOptions.map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all ${
                statusFilter === st
                  ? "bg-primary text-white shadow-sm font-bold"
                  : "glass-card text-foreground-muted hover:text-foreground"
              }`}
            >
              {st}
            </button>
          ))}

          <button
            onClick={() => fetchHistory()}
            title="Refresh history list"
            className="w-8 h-8 rounded-xl glass-card text-foreground-muted hover:text-foreground flex items-center justify-center ml-1 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </GlassSurface>

      {/* Media Items List */}
      {items.length === 0 ? (
        <GlassSurface
          variant="panel"
          className="border-dashed border-border-glass p-12 text-center space-y-3"
        >
          <div className="w-14 h-14 rounded-2xl bg-surface-elevated/80 border border-border-glass flex items-center justify-center mx-auto text-foreground-subtle shadow-inner">
            <Film className="w-7 h-7 text-primary/60" />
          </div>
          <h3 className="text-sm font-bold text-foreground">
            No history entries found
          </h3>
          <p className="text-xs text-foreground-muted max-w-sm mx-auto leading-relaxed">
            {searchQuery
              ? `No download matched query "${searchQuery}"`
              : "Completed media downloads will automatically be preserved here."}
          </p>
        </GlassSurface>
      ) : (
        <div className="space-y-2.5">
          {items.map((item: DownloadItem) => (
            <HistoryItemRow key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* In-App Clear Confirmation Modal (Replaces browser confirm) */}
      {showClearConfirm && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in">
          <GlassSurface variant="panel" glow={true} className="max-w-md w-full p-6 space-y-4 shadow-glass">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-danger/10 border border-danger/20 flex items-center justify-center text-danger">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-foreground">Clear Download History?</h3>
                <p className="text-xs text-foreground-muted">
                  This will remove all logged records from the local SQLite database. Downloaded files on disk will not be deleted.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setShowClearConfirm(false)}
                className="px-4 py-2 rounded-xl glass-card hover:bg-surface-elevated text-xs font-semibold text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmClear}
                className="px-4 py-2 rounded-xl bg-danger hover:bg-danger/90 text-white text-xs font-semibold shadow-sm transition-colors"
              >
                Clear All History
              </button>
            </div>
          </GlassSurface>
        </div>
      )}
    </div>
  );
};
