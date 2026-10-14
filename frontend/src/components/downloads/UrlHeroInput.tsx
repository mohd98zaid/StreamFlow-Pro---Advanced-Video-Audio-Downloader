import React, { useRef } from "react";
import { Link2, ClipboardPaste, X, CheckCircle2, AlertCircle, Sparkles, Globe } from "lucide-react";
import { useDownloadStore } from "../../stores/useDownloadStore";
import { Badge } from "../ui/Badge";
import { cn } from "../../lib/utils";

export const UrlHeroInput: React.FC = () => {
  const { urlInput, setUrlInput, detectedUrls, isExtracting, resetInput, error } = useDownloadStore();
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        const next = urlInput ? `${urlInput}\n${text.trim()}` : text.trim();
        setUrlInput(next);
      }
    } catch {
      inputRef.current?.focus();
    }
  };

  const getPlatformInfo = (url: string) => {
    const u = url.toLowerCase();
    if (u.includes("youtube.com") || u.includes("youtu.be")) {
      return { name: "YouTube", tag: "Video & Music", color: "text-red-400 bg-red-500/10 border-red-500/20" };
    }
    if (u.includes("instagram.com")) {
      return { name: "Instagram", tag: "Reels & Post", color: "text-pink-400 bg-pink-500/10 border-pink-500/20" };
    }
    if (u.includes("tiktok.com")) {
      return { name: "TikTok", tag: "Video & Sound", color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" };
    }
    if (u.includes("twitter.com") || u.includes("x.com")) {
      return { name: "Twitter / X", tag: "Clip", color: "text-sky-400 bg-sky-500/10 border-sky-500/20" };
    }
    if (u.includes("soundcloud.com")) {
      return { name: "SoundCloud", tag: "Lossless Audio", color: "text-orange-400 bg-orange-500/10 border-orange-500/20" };
    }
    if (u.includes("vimeo.com")) {
      return { name: "Vimeo", tag: "HD Video", color: "text-blue-400 bg-blue-500/10 border-blue-500/20" };
    }
    if (u.includes(".m3u8") || u.includes(".mp4")) {
      return { name: "Direct Stream", tag: "Media URL", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" };
    }
    return null;
  };

  const isMulti = detectedUrls.length > 1;
  const platform = detectedUrls.length === 1 ? getPlatformInfo(detectedUrls[0]) : null;

  return (
    <div
      className={cn(
        "w-full glass-panel border border-border-glass rounded-3xl p-5 shadow-glass transition-all duration-200 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/15 relative group",
        isExtracting && "border-accent-cyan/40 ring-2 ring-accent-cyan/15 animate-shimmer"
      )}
    >
      {/* Top Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center text-primary shadow-sm">
            <Link2 className="w-3.5 h-3.5" />
          </div>
          <div>
            <span className="text-xs font-bold text-foreground tracking-tight block">
              Media Stream URL
            </span>
            <span className="text-[10px] text-foreground-subtle hidden sm:inline">
              Supports YouTube, Reels, TikTok, Twitter/X, SoundCloud, Vimeo, & direct streams
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {platform && (
            <span className={cn("px-2.5 py-0.5 rounded-full text-[10px] font-bold border flex items-center gap-1", platform.color)}>
              <Globe className="w-3 h-3" />
              <span>{platform.name}</span>
            </span>
          )}

          {urlInput && (
            <button
              onClick={resetInput}
              className="text-xs text-foreground-subtle hover:text-foreground flex items-center gap-1 px-2.5 py-1 rounded-xl hover:bg-surface-elevated transition-colors"
            >
              <X className="w-3.5 h-3.5" />
              <span>Clear</span>
            </button>
          )}

          <button
            onClick={handlePaste}
            className="text-xs font-semibold text-primary hover:text-primary-hover flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-primary/10 hover:bg-primary/20 border border-primary/20 transition-all active:scale-95 shadow-sm"
          >
            <ClipboardPaste className="w-3.5 h-3.5" />
            <span>Paste Link</span>
          </button>
        </div>
      </div>

      {/* Main Multi-line Input */}
      <textarea
        ref={inputRef}
        value={urlInput}
        onChange={(e) => setUrlInput(e.target.value)}
        placeholder="Paste video, song, or playlist URL here (one link per line for batch downloading)..."
        rows={isMulti ? 3 : 2}
        className="w-full bg-transparent border-0 outline-none text-foreground placeholder:text-foreground-subtle text-sm font-normal resize-none font-sans leading-relaxed"
      />

      {/* Bottom Status Row */}
      <div className="flex items-center justify-between pt-3 border-t border-border-hairline mt-1.5">
        <div className="flex items-center gap-2">
          {isExtracting ? (
            <span className="text-xs text-accent-cyan flex items-center gap-1.5 animate-pulse font-semibold">
              <Sparkles className="w-3.5 h-3.5 animate-spin" />
              Inspecting media stream & extracting metadata...
            </span>
          ) : detectedUrls.length > 0 ? (
            <Badge variant="cyan" className="gap-1.5 px-3 py-0.5 rounded-full shadow-sm">
              <CheckCircle2 className="w-3 h-3 text-accent-cyan" />
              <span>
                {detectedUrls.length} {detectedUrls.length === 1 ? "Link verified" : "Links ready for batch queue"}
              </span>
            </Badge>
          ) : (
            <span className="text-[11px] text-foreground-subtle flex items-center gap-1.5">
              Press <kbd className="px-1.5 py-0.5 bg-surface-elevated/80 border border-border-glass rounded-md text-[10px] font-mono shadow-sm">Ctrl+V</kbd> to paste
            </span>
          )}

          {error && !isExtracting && (
            <span className="text-xs text-danger flex items-center gap-1 font-medium bg-danger/10 px-2.5 py-0.5 rounded-lg border border-danger/20">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{error}</span>
            </span>
          )}
        </div>

        {isMulti && (
          <span className="text-[10px] font-bold text-accent-cyan bg-accent-cyan/15 px-2.5 py-0.5 rounded-full border border-accent-cyan/25">
            Batch Mode Active ({detectedUrls.length})
          </span>
        )}
      </div>
    </div>
  );
};
