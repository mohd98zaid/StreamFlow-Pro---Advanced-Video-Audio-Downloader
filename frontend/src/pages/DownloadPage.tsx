import React, { useState } from "react";
import { Download, CheckCircle2, Sparkles, ArrowRight, AlertCircle } from "lucide-react";
import { UrlHeroInput } from "../components/downloads/UrlHeroInput";
import { MetadataCard } from "../components/downloads/MetadataCard";
import { FormatOptions } from "../components/downloads/FormatOptions";
import { useDownloadStore } from "../stores/useDownloadStore";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useQueueStore } from "../stores/useQueueStore";
import { useToastStore } from "../stores/useToastStore";
import { api } from "../services/api";

interface DownloadPageProps {
  onGoToQueue: () => void;
}

export const DownloadPage: React.FC<DownloadPageProps> = ({ onGoToQueue }) => {
  const {
    detectedUrls,
    downloadType,
    quality,
    formatType,
    embedThumbnail,
    embedMetadata,
    embedSubtitles,
    isExtracting,
    resetInput,
  } = useDownloadStore();

  const { config } = useSettingsStore();
  const { fetchQueue } = useQueueStore();
  const toast = useToastStore();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [downloadState, setDownloadState] = useState<"idle" | "success" | "error">("idle");

  const handleStartDownload = async () => {
    if (detectedUrls.length === 0) return;

    setIsSubmitting(true);
    setDownloadState("idle");
    try {
      const res = await api.addDownloads({
        urls: detectedUrls,
        download_type: downloadType,
        quality: quality,
        format_type: formatType,
        options: {
          embed_thumbnail: embedThumbnail,
          embed_metadata: embedMetadata,
          embed_subtitles: embedSubtitles,
        },
        save_path: config.download_path,
      });

      if (res.success) {
        setDownloadState("success");
        const count = res.added_count || detectedUrls.length;
        toast.success(
          `Successfully queued ${count} item${count > 1 ? "s" : ""} for download!`,
          "Downloads Queued"
        );
        resetInput();
        fetchQueue();
        setTimeout(() => setDownloadState("idle"), 3000);
      } else {
        setDownloadState("error");
        toast.error(res.error || "Failed to add items to queue", "Queue Error");
      }
    } catch (err: any) {
      setDownloadState("error");
      toast.error(err.message || "Could not connect to download engine", "Engine Error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const isIdle = !isSubmitting && !isExtracting && downloadState === "idle";

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto animate-fade-in select-none">
      {/* Hero Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
          <span>Download Media</span>
          <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 uppercase">
            Ultra-HD & Lossless
          </span>
        </h1>
        <p className="text-xs text-foreground-muted">
          Download high-resolution video up to 4K, extract pristine 320kbps audio, or batch archive full playlists.
        </p>
      </div>

      {/* 1. Primary Dominant URL Input Hero */}
      <UrlHeroInput />

      {/* 2. Media Metadata Preview (Appears when single valid URL entered) */}
      <MetadataCard />

      {/* 3. Format, Quality, and Preset Options */}
      <FormatOptions />

      {/* 4. Primary Download CTA Button with Animated States */}
      <div className="pt-2">
        <button
          onClick={handleStartDownload}
          disabled={detectedUrls.length === 0 || isSubmitting || isExtracting}
          className="w-full h-13 rounded-2xl bg-gradient-to-r from-primary to-primary-hover text-white font-bold text-sm tracking-wide shadow-glass hover:shadow-lg hover:brightness-105 disabled:opacity-40 disabled:pointer-events-none transition-all duration-200 flex items-center justify-center gap-2 select-none active:scale-[0.99] border border-white/15"
        >
          {isExtracting ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Analyzing Media Stream…</span>
            </>
          ) : isSubmitting ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Adding to Queue…</span>
            </>
          ) : downloadState === "success" ? (
            <>
              <CheckCircle2 className="w-4 h-4 text-white" />
              <span>Added to Queue!</span>
            </>
          ) : downloadState === "error" ? (
            <>
              <AlertCircle className="w-4 h-4 text-white" />
              <span>Try Again</span>
            </>
          ) : (
            <>
              <Download className="w-4 h-4" />
              <span>
                {detectedUrls.length > 1
                  ? `Download ${detectedUrls.length} Items (Batch Mode)`
                  : "Start Download"}
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
