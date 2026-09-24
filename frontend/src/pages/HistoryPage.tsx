import React, { useEffect } from "react";
import { Search, Trash2, FolderOpen, RefreshCw, Film } from "lucide-react";
import { useHistoryStore } from "../stores/useHistoryStore";
import { HistoryItemRow } from "../components/history/HistoryItemRow";
import { DownloadItem } from "../types/download";
import { Button } from "../components/ui/Button";

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

  useEffect(() => {
    fetchHistory();
    fetchStats();
  }, []);

  const handleClearHistory = () => {
    if (window.confirm("Are you sure you want to clear your entire download history archive?")) {
      clearAll();
    }
  };

  const statusOptions = ["All", "Completed", "Failed", "Cancelled"];

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Media History
          </h1>
          <p className="text-xs text-foreground-muted">
            Locally archived SQLite database of completed and processed media downloads.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => openFolder()}>
            <FolderOpen className="w-3.5 h-3.5 mr-1" />
            <span>Open Folder</span>
          </Button>

          {items.length > 0 && (
            <Button
              size="sm"
              variant="danger"
              onClick={handleClearHistory}
              className="text-xs"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              <span>Clear History</span>
            </Button>
          )}
        </div>
      </div>

      {/* Analytics Metric Cards (Stats) */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-surface border border-border rounded-xl p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-foreground-muted uppercase tracking-wider block">
              Total Recorded
            </span>
            <span className="text-xl font-bold text-foreground">
              {stats.total_downloads}
            </span>
          </div>

          <div className="bg-surface border border-border rounded-xl p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-foreground-muted uppercase tracking-wider block">
              Success Rate
            </span>
            <span className="text-xl font-bold text-success">
              {stats.success_rate.toFixed(0)}%
            </span>
          </div>

          <div className="bg-surface border border-border rounded-xl p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-foreground-muted uppercase tracking-wider block">
              Downloaded Size
            </span>
            <span className="text-xl font-bold text-accent-cyan">
              {stats.total_size_formatted}
            </span>
          </div>

          <div className="bg-surface border border-border rounded-xl p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-foreground-muted uppercase tracking-wider block">
              Completed Files
            </span>
            <span className="text-xl font-bold text-primary">
              {stats.successful_downloads}
            </span>
          </div>
        </div>
      )}

      {/* Filters Toolbar */}
      <div className="w-full bg-surface border border-border rounded-xl p-3 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-sm">
        {/* Search input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search downloads or channel…"
            className="w-full h-8 pl-8 pr-3 bg-surface-elevated border border-border rounded-lg text-xs text-foreground placeholder:text-foreground-subtle focus:outline-none focus:border-primary"
          />
        </div>

        {/* Status Filter Chips */}
        <div className="flex items-center gap-1.5 self-start sm:self-center">
          {statusOptions.map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                statusFilter === st
                  ? "bg-primary text-white"
                  : "bg-surface-elevated text-foreground-muted hover:text-foreground hover:bg-border/40"
              }`}
            >
              {st}
            </button>
          ))}

          <button
            onClick={() => fetchHistory()}
            title="Refresh history list"
            className="w-8 h-8 rounded-lg border border-border text-foreground-muted hover:text-foreground hover:bg-surface-elevated flex items-center justify-center ml-1 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Media Items List */}
      {items.length === 0 ? (
        <div className="w-full bg-surface border border-dashed border-border rounded-2xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-surface-elevated border border-border flex items-center justify-center mx-auto text-foreground-subtle">
            <Film className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">
            No history entries found
          </h3>
          <p className="text-xs text-foreground-muted max-w-sm mx-auto">
            {searchQuery
              ? `No download matched query "${searchQuery}"`
              : "Completed media downloads will automatically appear here."}
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {items.map((item: DownloadItem) => (
            <HistoryItemRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
};
