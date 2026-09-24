import React from "react";
import { Play, Download, User, Eye, Tv } from "lucide-react";
import { SearchResult } from "../../types/download";
import { api } from "../../services/api";
import { useDownloadStore } from "../../stores/useDownloadStore";
import { MediaArtwork } from "../media/MediaArtwork";

interface SearchResultCardProps {
  result: SearchResult;
  onDownloadImmediately?: (result: SearchResult) => void;
}

export const SearchResultCard: React.FC<SearchResultCardProps> = ({
  result,
  onDownloadImmediately,
}) => {
  const { setUrlInput } = useDownloadStore();

  const handlePreview = () => {
    if (result.id) {
      api.openPlayer(result.id, result.title);
    }
  };

  const handleQueue = () => {
    if (onDownloadImmediately) {
      onDownloadImmediately(result);
    } else {
      setUrlInput(result.url);
    }
  };

  return (
    <div className="w-full glass-card border border-border-glass rounded-2xl p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3.5 hover:border-border-glass hover:bg-surface-elevated/40 transition-all duration-150 shadow-sm group">
      {/* Thumbnail + Details */}
      <div className="flex items-center gap-3.5 min-w-0 flex-1">
        <MediaArtwork
          src={result.thumbnail}
          alt={result.title}
          duration={result.duration_str}
          size="md"
          glow={false}
          onPreview={handlePreview}
          className="rounded-xl flex-shrink-0"
        />

        {/* Info */}
        <div className="min-w-0 space-y-1">
          <h4
            className="text-xs sm:text-sm font-bold text-foreground truncate max-w-md cursor-pointer hover:text-primary transition-colors"
            title={result.title}
            onClick={handlePreview}
          >
            {result.title}
          </h4>

          <div className="flex items-center gap-2.5 text-xs text-foreground-muted flex-wrap">
            <span className="flex items-center gap-1.5 truncate max-w-[180px]">
              <User className="w-3 h-3 text-foreground-subtle" />
              <span className="truncate">{result.channel}</span>
            </span>

            {result.views_str !== "N/A" && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1 text-[11px] text-foreground-subtle font-mono">
                  <Eye className="w-3 h-3" />
                  {result.views_str} views
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Action CTA Buttons */}
      <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-center">
        <button
          onClick={handlePreview}
          title="Watch in ad-free player"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-panel hover:bg-accent-cyan/10 hover:border-accent-cyan/40 text-xs font-semibold text-foreground-muted hover:text-accent-cyan transition-colors"
        >
          <Tv className="w-3.5 h-3.5 text-accent-cyan" />
          <span>Preview</span>
        </button>

        <button
          onClick={handleQueue}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-bold shadow-sm transition-all active:scale-95"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Download</span>
        </button>
      </div>
    </div>
  );
};
