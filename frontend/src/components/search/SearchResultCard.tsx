import React from "react";
import { Play, Download, User, Eye, Plus } from "lucide-react";
import { SearchResult } from "../../types/download";
import { api } from "../../services/api";
import { useDownloadStore } from "../../stores/useDownloadStore";

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
    <div className="w-full bg-surface border border-border rounded-xl p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3.5 hover:border-border/80 transition-all shadow-sm group">
      {/* Thumbnail + Details */}
      <div className="flex items-center gap-3.5 min-w-0 flex-1">
        <div className="relative w-32 h-20 bg-black/40 rounded-lg overflow-hidden flex-shrink-0 border border-border/60">
          {result.thumbnail ? (
            <img
              src={result.thumbnail}
              alt={result.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-foreground-subtle text-xs">
              No Preview
            </div>
          )}

          {result.duration_str && (
            <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[10px] font-mono px-1 rounded font-medium">
              {result.duration_str}
            </span>
          )}

          <button
            onClick={handlePreview}
            title="Preview in ad-free player"
            className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity"
          >
            <div className="w-8 h-8 rounded-full bg-primary/90 flex items-center justify-center shadow-lg">
              <Play className="w-4 h-4 fill-white ml-0.5" />
            </div>
          </button>
        </div>

        {/* Info */}
        <div className="min-w-0 space-y-1">
          <h4
            className="text-xs sm:text-sm font-semibold text-foreground truncate max-w-md cursor-pointer hover:text-primary transition-colors"
            title={result.title}
            onClick={handlePreview}
          >
            {result.title}
          </h4>

          <div className="flex items-center gap-2.5 text-xs text-foreground-muted flex-wrap">
            <span className="flex items-center gap-1 truncate">
              <User className="w-3 h-3 text-foreground-subtle" />
              <span className="truncate">{result.channel}</span>
            </span>

            {result.views_str !== "N/A" && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1 text-[11px] text-foreground-subtle">
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
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border/80 text-xs font-semibold text-foreground-muted hover:text-accent-cyan hover:border-accent-cyan/40 hover:bg-accent-cyan/10 transition-colors"
        >
          <Play className="w-3 h-3 fill-current" />
          <span>Preview</span>
        </button>

        <button
          onClick={handleQueue}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-sm transition-colors"
        >
          <Download className="w-3 h-3" />
          <span>Download</span>
        </button>
      </div>
    </div>
  );
};
