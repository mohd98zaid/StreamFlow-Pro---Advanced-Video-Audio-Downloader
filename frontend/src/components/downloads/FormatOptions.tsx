import React, { useState } from "react";
import {
  Video,
  Music,
  ListVideo,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Folder,
  SlidersHorizontal,
} from "lucide-react";
import { useDownloadStore } from "../../stores/useDownloadStore";
import { useSettingsStore } from "../../stores/useSettingsStore";
import { GlassSurface } from "../ui/GlassSurface";
import { cn } from "../../lib/utils";

export const FormatOptions: React.FC = () => {
  const {
    downloadType,
    setDownloadType,
    quality,
    setQuality,
    formatType,
    setFormatType,
    metadata,
    presets,
    activePreset,
    applyPreset,
    embedThumbnail,
    setEmbedThumbnail,
    embedMetadata,
    setEmbedMetadata,
    embedSubtitles,
    setEmbedSubtitles,
  } = useDownloadStore();

  const { config, browseFolder } = useSettingsStore();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const videoQualities = [
    "Best Available",
    "2160p (4K)",
    "1440p (2K)",
    "1080p (Full HD)",
    "720p (HD)",
    "480p",
    "360p",
  ];

  const audioFormats = ["mp3", "m4a", "wav", "flac"];
  const videoFormats = ["mp4", "mkv", "webm"];

  return (
    <GlassSurface variant="panel" className="p-5 space-y-4">
      {/* Top Segmented Media Type Switcher & Presets */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border-hairline">
        {/* Segmented Media Pill */}
        <div className="flex items-center gap-1 p-1 bg-surface-elevated/80 rounded-2xl border border-border-hairline shadow-inner">
          <button
            onClick={() => setDownloadType("video")}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150",
              downloadType === "video"
                ? "bg-primary text-white shadow-sm font-bold"
                : "text-foreground-muted hover:text-foreground"
            )}
          >
            <Video className="w-3.5 h-3.5" />
            <span>Video</span>
          </button>

          <button
            onClick={() => setDownloadType("audio")}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150",
              downloadType === "audio"
                ? "bg-primary text-white shadow-sm font-bold"
                : "text-foreground-muted hover:text-foreground"
            )}
          >
            <Music className="w-3.5 h-3.5" />
            <span>Audio (Lossless/MP3)</span>
          </button>

          <button
            onClick={() => setDownloadType("playlist")}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150",
              downloadType === "playlist"
                ? "bg-primary text-white shadow-sm font-bold"
                : "text-foreground-muted hover:text-foreground"
            )}
          >
            <ListVideo className="w-3.5 h-3.5" />
            <span>Playlist</span>
          </button>
        </div>

        {/* Preset Selector */}
        {presets.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-foreground-subtle flex items-center gap-1 font-medium">
              <Sparkles className="w-3 h-3 text-primary" /> Preset:
            </span>
            <div className="relative inline-flex items-center">
              <select
                value={activePreset}
                onChange={(e) => applyPreset(e.target.value)}
                className="bg-[#161C27] dark:bg-[#161C27] border border-white/12 text-xs rounded-xl pl-3 pr-8 py-1.5 text-foreground font-semibold focus:outline-none focus:border-primary appearance-none cursor-pointer shadow-sm"
              >
                {presets.map((p) => (
                  <option key={p.name} value={p.name} className="bg-[#10141D] text-foreground">
                    {p.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3 h-3 text-foreground-muted pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2" />
            </div>
          </div>
        )}
      </div>

      {/* Primary Progressive Disclosure Options Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {/* Quality Selector */}
        <div>
          <label className="block text-[11px] font-bold text-foreground-muted uppercase tracking-wider mb-1.5">
            {downloadType === "audio" ? "Audio Bitrate" : "Resolution / Quality"}
          </label>
          {downloadType === "audio" ? (
            <div className="h-10 px-3.5 bg-[#161C27] dark:bg-[#161C27] border border-white/12 rounded-xl text-xs flex items-center justify-between text-foreground shadow-sm">
              <span className="font-semibold">Studio 320 kbps (HQ)</span>
              <span className="text-[10px] text-accent-cyan font-bold px-1.5 py-0.5 rounded bg-accent-cyan/15 border border-accent-cyan/25">
                Pristine Audio
              </span>
            </div>
          ) : (
            <div className="relative w-full">
              <select
                value={quality}
                onChange={(e) => setQuality(e.target.value)}
                className="w-full h-10 bg-[#161C27] dark:bg-[#161C27] border border-white/12 rounded-xl pl-3 pr-9 text-xs text-foreground font-semibold focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all appearance-none cursor-pointer shadow-sm"
              >
                {(metadata?.available_qualities || videoQualities).map((q) => (
                  <option key={q} value={q} className="bg-[#10141D] text-foreground py-1">
                    {q}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-foreground-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2" />
            </div>
          )}
        </div>

        {/* Format Selector */}
        <div>
          <label className="block text-[11px] font-bold text-foreground-muted uppercase tracking-wider mb-1.5">
            Container / Extension
          </label>
          <div className="relative w-full">
            <select
              value={formatType}
              onChange={(e) => setFormatType(e.target.value)}
              className="w-full h-10 bg-[#161C27] dark:bg-[#161C27] border border-white/12 rounded-xl pl-3 pr-9 text-xs text-foreground font-semibold uppercase focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all appearance-none cursor-pointer shadow-sm"
            >
              {(downloadType === "audio" ? audioFormats : videoFormats).map((f) => (
                <option key={f} value={f} className="bg-[#10141D] text-foreground py-1">
                  {f.toUpperCase()}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-foreground-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2" />
          </div>
        </div>

        {/* Save Folder Selection */}
        <div>
          <label className="block text-[11px] font-bold text-foreground-muted uppercase tracking-wider mb-1.5">
            Save Directory
          </label>
          <div className="flex items-center gap-2">
            <div
              className="flex-1 h-10 px-3 bg-[#161C27] dark:bg-[#161C27] border border-white/12 rounded-xl text-xs flex items-center text-foreground-muted truncate cursor-pointer hover:border-primary/50 transition-colors shadow-sm"
              onClick={browseFolder}
              title={config.download_path}
            >
              <Folder className="w-3.5 h-3.5 text-foreground-subtle mr-2 flex-shrink-0" />
              <span className="truncate text-foreground font-medium">
                {config.download_path ? config.download_path.split(/[\\/]/).pop() || "Downloads" : "Downloads"}
              </span>
            </div>
            <button
              onClick={browseFolder}
              className="h-10 px-3.5 bg-[#161C27] dark:bg-[#161C27] hover:bg-surface-elevated border border-white/12 rounded-xl text-xs font-semibold text-foreground transition-colors shadow-sm"
            >
              Browse
            </button>
          </div>
        </div>
      </div>

      {/* Secondary Options Collapsible */}
      <div className="pt-2 border-t border-border-hairline">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1.5 text-xs font-semibold text-foreground-muted hover:text-foreground transition-colors py-1 select-none"
        >
          <SlidersHorizontal className="w-3.5 h-3.5" />
          <span>Advanced options</span>
          {showAdvanced ? (
            <ChevronUp className="w-3.5 h-3.5 ml-0.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 ml-0.5" />
          )}
        </button>

        {showAdvanced && (
          <div className="mt-3 p-3.5 bg-[#161C27] dark:bg-[#161C27] border border-white/12 rounded-2xl grid grid-cols-1 sm:grid-cols-3 gap-3 animate-fade-in shadow-sm">
            <label className="flex items-center gap-2.5 text-xs text-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={embedThumbnail}
                onChange={(e) => setEmbedThumbnail(e.target.checked)}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-white/20 cursor-pointer accent-primary"
              />
              <span className="font-medium">Embed Cover Thumbnail</span>
            </label>

            <label className="flex items-center gap-2.5 text-xs text-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={embedMetadata}
                onChange={(e) => setEmbedMetadata(e.target.checked)}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-white/20 cursor-pointer accent-primary"
              />
              <span className="font-medium">Embed ID3 / Title Tags</span>
            </label>

            <label className="flex items-center gap-2.5 text-xs text-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={embedSubtitles}
                onChange={(e) => setEmbedSubtitles(e.target.checked)}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-white/20 cursor-pointer accent-primary"
              />
              <span className="font-medium">Embed Subtitles (.srt/en)</span>
            </label>
          </div>
        )}
      </div>
    </GlassSurface>
  );
};
