import React, { useState } from "react";
import { Search, Tv, CheckCircle2 } from "lucide-react";
import { SearchResult } from "../types/download";
import { SearchResultCard } from "../components/search/SearchResultCard";
import { api } from "../services/api";
import { useDownloadStore } from "../stores/useDownloadStore";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useQueueStore } from "../stores/useQueueStore";
import { Button } from "../components/ui/Button";

interface SearchPageProps {
  onGoToQueue: () => void;
}

export const SearchPage: React.FC<SearchPageProps> = ({ onGoToQueue }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const { config } = useSettingsStore();
  const { fetchQueue } = useQueueStore();
  const { downloadType, quality, formatType } = useDownloadStore();

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setHasSearched(true);
    try {
      const data = await api.searchYouTube(query.trim(), 15);
      setResults(data.results);
    } catch (err: any) {
      alert(`Search error: ${err.message || "Failed to search YouTube"}`);
    } finally {
      setIsSearching(false);
    }
  };

  const handleDownloadDirectly = async (res: SearchResult) => {
    try {
      const addRes = await api.addDownloads({
        urls: [res.url],
        download_type: downloadType,
        quality: quality,
        format_type: formatType,
        save_path: config.download_path,
      });

      if (addRes.success) {
        setToastMessage(`Added "${res.title}" to download queue!`);
        fetchQueue();
        setTimeout(() => setToastMessage(null), 3500);
      }
    } catch (err: any) {
      alert(err.message || "Failed to queue item");
    }
  };

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>Search YouTube</span>
            <span className="text-[11px] font-semibold text-accent-cyan bg-accent-cyan/10 px-2 py-0.5 rounded-full border border-accent-cyan/20">
              Direct Engine
            </span>
          </h1>
          <p className="text-xs text-foreground-muted">
            Search videos, music, and channels directly with instant ad-free preview and one-click queueing.
          </p>
        </div>

        <button
          onClick={() => api.openPlayer("https://www.youtube.com", "YouTube Browser")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-elevated hover:bg-border/60 border border-border text-xs font-semibold text-foreground transition-colors"
        >
          <Tv className="w-3.5 h-3.5 text-accent-cyan" />
          <span>Open YouTube Studio</span>
        </button>
      </div>

      {/* Toast Banner */}
      {toastMessage && (
        <div className="w-full p-3 bg-success/10 border border-success/30 rounded-xl text-xs text-success font-semibold flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{toastMessage}</span>
          </div>
          <button
            onClick={onGoToQueue}
            className="underline hover:text-white font-bold transition-colors"
          >
            View in Queue →
          </button>
        </div>
      )}

      {/* Search Input Bar */}
      <form onSubmit={handleSearch} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-subtle" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search videos, music, artists, or keywords..."
            className="w-full h-11 pl-10 pr-4 bg-surface border border-border rounded-xl text-sm text-foreground placeholder:text-foreground-subtle focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 shadow-sm"
          />
        </div>

        <Button
          type="submit"
          disabled={isSearching || !query.trim()}
          size="lg"
          className="h-11 px-5"
        >
          {isSearching ? (
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              <Search className="w-4 h-4 mr-1.5" />
              <span>Search</span>
            </>
          )}
        </Button>
      </form>

      {/* Results Container */}
      {isSearching ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="w-full h-24 bg-surface border border-border rounded-xl p-3 flex items-center gap-4 animate-pulse"
            >
              <div className="w-32 h-18 bg-surface-elevated rounded-lg flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-surface-elevated rounded w-2/3" />
                <div className="h-3 bg-surface-elevated rounded w-1/4" />
              </div>
            </div>
          ))}
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-foreground-muted px-1">
            <span>Results for "{query}"</span>
            <span>{results.length} items found</span>
          </div>

          {results.map((res) => (
            <SearchResultCard
              key={res.id || res.url}
              result={res}
              onDownloadImmediately={handleDownloadDirectly}
            />
          ))}
        </div>
      ) : hasSearched ? (
        <div className="w-full bg-surface border border-dashed border-border rounded-2xl p-12 text-center space-y-2">
          <p className="text-sm font-semibold text-foreground">
            No results found for "{query}"
          </p>
          <p className="text-xs text-foreground-muted">
            Try different search keywords or paste the direct video URL in the New Download page.
          </p>
        </div>
      ) : (
        <div className="w-full bg-surface border border-dashed border-border rounded-2xl p-12 text-center space-y-2">
          <Search className="w-8 h-8 text-foreground-subtle mx-auto mb-2 opacity-60" />
          <h3 className="text-sm font-semibold text-foreground">
            Search YouTube directly
          </h3>
          <p className="text-xs text-foreground-muted max-w-sm mx-auto">
            Discover music, podcasts, tutorials, and videos with instant ad-free previewing and download queueing.
          </p>
        </div>
      )}
    </div>
  );
};
