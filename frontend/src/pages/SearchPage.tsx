import React, { useState } from "react";
import { Search, Tv, CheckCircle2, Sparkles, Film } from "lucide-react";
import { SearchResult } from "../types/download";
import { SearchResultCard } from "../components/search/SearchResultCard";
import { api } from "../services/api";
import { useDownloadStore } from "../stores/useDownloadStore";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useQueueStore } from "../stores/useQueueStore";
import { useToastStore } from "../stores/useToastStore";
import { GlassSurface } from "../components/ui/GlassSurface";

interface SearchPageProps {
  onGoToQueue: () => void;
}

export const SearchPage: React.FC<SearchPageProps> = ({ onGoToQueue }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const { config } = useSettingsStore();
  const { fetchQueue } = useQueueStore();
  const { downloadType, quality, formatType } = useDownloadStore();
  const toast = useToastStore();

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setHasSearched(true);
    try {
      const data = await api.searchYouTube(query.trim(), 15);
      setResults(data.results);
    } catch (err: any) {
      toast.error(err.message || "Failed to search media", "Search Error");
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
        toast.success(`Queued "${res.title}" for download!`, "Download Added");
        fetchQueue();
      } else {
        toast.error(addRes.error || "Failed to queue media item", "Queue Error");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to queue item", "Engine Error");
    }
  };

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto animate-fade-in select-none">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <span>Media Discovery</span>
            <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/25 uppercase">
              Fast Engine
            </span>
          </h1>
          <p className="text-xs text-foreground-muted">
            Search videos, music, and channels directly with instant ad-free preview and one-click queueing.
          </p>
        </div>

        <button
          onClick={() => api.openPlayer("https://www.youtube.com", "YouTube Browser")}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl glass-panel hover:bg-accent-cyan/10 hover:border-accent-cyan/40 text-xs font-semibold text-foreground-muted hover:text-accent-cyan transition-colors"
        >
          <Tv className="w-4 h-4 text-accent-cyan" />
          <span>Launch YouTube Studio</span>
        </button>
      </div>

      {/* Search Input Bar */}
      <form onSubmit={handleSearch} className="flex items-center gap-2.5">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-subtle" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search videos, music tracks, artists, or keywords..."
            className="w-full h-11 pl-10 pr-4 glass-panel border border-border-glass rounded-2xl text-sm text-foreground placeholder:text-foreground-subtle focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 shadow-glass-sm transition-all"
          />
        </div>

        <button
          type="submit"
          disabled={isSearching || !query.trim()}
          className="h-11 px-5 rounded-2xl bg-gradient-to-r from-primary to-primary-hover hover:brightness-105 text-white font-bold text-xs shadow-glass-sm disabled:opacity-40 transition-all flex items-center gap-1.5 active:scale-95"
        >
          {isSearching ? (
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>Search</span>
            </>
          )}
        </button>
      </form>

      {/* Results Container */}
      {isSearching ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <GlassSurface
              key={i}
              variant="card"
              className="p-3 flex items-center gap-4 animate-pulse"
            >
              <div className="w-32 h-20 bg-surface-elevated rounded-xl flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-surface-elevated rounded w-2/3" />
                <div className="h-3 bg-surface-elevated rounded w-1/4" />
              </div>
            </GlassSurface>
          ))}
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-foreground-muted px-1">
            <span>Results for "{query}"</span>
            <span className="font-mono">{results.length} items found</span>
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
        <GlassSurface
          variant="panel"
          className="border-dashed border-border-glass p-12 text-center space-y-2"
        >
          <p className="text-sm font-bold text-foreground">
            No results found for "{query}"
          </p>
          <p className="text-xs text-foreground-muted max-w-sm mx-auto">
            Try different search keywords or paste the direct video link in the New Download page.
          </p>
        </GlassSurface>
      ) : (
        <GlassSurface
          variant="panel"
          className="border-dashed border-border-glass p-12 text-center space-y-3"
        >
          <div className="w-14 h-14 rounded-2xl bg-surface-elevated/80 border border-border-glass flex items-center justify-center mx-auto text-foreground-subtle shadow-inner">
            <Film className="w-7 h-7 text-primary/60" />
          </div>
          <h3 className="text-sm font-bold text-foreground">
            Discover Media Directly
          </h3>
          <p className="text-xs text-foreground-muted max-w-sm mx-auto leading-relaxed">
            Search YouTube for music, podcasts, tutorials, and full playlists with instant ad-free previewing and download queueing.
          </p>
        </GlassSurface>
      )}
    </div>
  );
};
