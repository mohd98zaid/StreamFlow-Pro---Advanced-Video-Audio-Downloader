import React from "react";
import { Play, User, Clock, Layers, Eye, Tv, Sparkles } from "lucide-react";
import { useDownloadStore } from "../../stores/useDownloadStore";
import { api } from "../../services/api";
import { extractVideoId } from "../../lib/helpers";
import { MediaArtwork } from "../media/MediaArtwork";
import { GlassSurface } from "../ui/GlassSurface";

export const MetadataCard: React.FC = () => {
  const { metadata, isExtracting, error } = useDownloadStore();

  if (isExtracting) {
    return (
      <GlassSurface variant="panel" className="p-4 flex items-center gap-4 animate-pulse">
        <div className="w-36 h-22 sm:w-44 sm:h-26 bg-surface-elevated rounded-2xl flex-shrink-0" />
        <div className="flex-1 space-y-3">
          <div className="h-5 bg-surface-elevated rounded-lg w-3/4" />
          <div className="h-3.5 bg-surface-elevated rounded w-1/3" />
          <div className="h-3 bg-surface-elevated rounded w-1/4" />
        </div>
      </GlassSurface>
    );
  }

  if (error || !metadata) return null;

  const handleOpenPreview = () => {
    const vId = extractVideoId(metadata.url) || metadata.url;
    api.openPlayer(vId, metadata.title);
  };

  return (
    <GlassSurface
      variant="panel"
      glow={true}
      className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-fade-in group"
    >
      {/* Left: Dominant Media Artwork + Info Hierarchy */}
      <div className="flex items-center gap-4 min-w-0 flex-1">
        <MediaArtwork
          src={metadata.thumbnail}
          alt={metadata.title}
          duration={metadata.duration_str}
          type={metadata.is_playlist ? "playlist" : "video"}
          size="lg"
          glow={true}
          onPreview={handleOpenPreview}
          className="rounded-2xl"
        />

        {/* Info Column */}
        <div className="min-w-0 flex-1 space-y-1.5">
          <h3
            className="text-sm sm:text-base font-bold text-foreground leading-snug truncate max-w-lg cursor-pointer hover:text-primary transition-colors"
            title={metadata.title}
            onClick={handleOpenPreview}
          >
            {metadata.title}
          </h3>

          <div className="flex items-center gap-3 text-xs text-foreground-muted flex-wrap">
            <span className="flex items-center gap-1.5 font-medium text-foreground-muted">
              <User className="w-3.5 h-3.5 text-foreground-subtle" />
              <span className="truncate max-w-[200px]">{metadata.uploader}</span>
            </span>

            {metadata.view_count !== undefined && (
              <span className="flex items-center gap-1 text-[11px] text-foreground-subtle">
                <Eye className="w-3 h-3" />
                {metadata.view_count.toLocaleString()} views
              </span>
            )}

            {metadata.is_playlist && (
              <span className="flex items-center gap-1 text-[10px] font-bold text-accent-cyan bg-accent-cyan/15 px-2 py-0.5 rounded-full border border-accent-cyan/30">
                <Layers className="w-3 h-3" />
                Playlist ({metadata.playlist_count} items)
              </span>
            )}
          </div>

          {/* Formats snippet */}
          {metadata.available_qualities && metadata.available_qualities.length > 0 && (
            <div className="flex items-center gap-1.5 pt-1">
              <span className="text-[10px] uppercase tracking-wider text-foreground-subtle font-semibold">
                Available:
              </span>
              <div className="flex items-center gap-1 overflow-x-auto py-0.5">
                {metadata.available_qualities.slice(0, 4).map((q) => (
                  <span
                    key={q}
                    className="text-[10px] px-1.5 py-0.2 rounded-md bg-surface-elevated border border-border-hairline text-foreground-subtle"
                  >
                    {q.split(" ")[0]}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Yuma Ad-Free Player Quick Stream Button */}
      <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-center">
        <button
          onClick={handleOpenPreview}
          title="Watch without ads in Yuma Cinema Player"
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl glass-panel hover:bg-accent-cyan/10 hover:border-accent-cyan/40 text-foreground-muted hover:text-accent-cyan transition-all text-xs font-semibold shadow-sm active:scale-95"
        >
          <Tv className="w-3.5 h-3.5 text-accent-cyan" />
          <span>Ad-Free Stream</span>
        </button>
      </div>
    </GlassSurface>
  );
};
