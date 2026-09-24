import React, { useState } from "react";
import { Download, CheckCircle2 } from "lucide-react";
import { UrlHeroInput } from "../components/downloads/UrlHeroInput";
import { MetadataCard } from "../components/downloads/MetadataCard";
import { FormatOptions } from "../components/downloads/FormatOptions";
import { useDownloadStore } from "../stores/useDownloadStore";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useQueueStore } from "../stores/useQueueStore";
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
    resetInput,
  } = useDownloadStore();

  const { config } = useSettingsStore();
  const { fetchQueue } = useQueueStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  const handleStartDownload = async () => {
    if (detectedUrls.length === 0) return;

    setIsSubmitting(true);
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
        setSuccessToast(
          `Added ${res.added_count} item${res.added_count > 1 ? "s" : ""} to download queue!`
        );
        resetInput();
        fetchQueue();
        setTimeout(() => setSuccessToast(null), 4000);
      }
    } catch (err: any) {
      alert(`Download Error: ${err.message || "Failed to start download"}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto animate-fade-in">
      {/* Hero Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <span>Download Media</span>
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
            Fast & High Quality
          </span>
        </h1>
        <p className="text-xs text-foreground-muted">
          Download high-resolution video up to 4K, extract pristine 320kbps audio, or archive entire playlists.
        </p>
      </div>

      {/* Success Notification Banner */}
      {successToast && (
        <div className="w-full p-3 bg-success/10 border border-success/30 rounded-xl text-xs text-success font-semibold flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{successToast}</span>
          </div>
          <button
            onClick={onGoToQueue}
            className="underline hover:text-white font-bold transition-colors"
          >
            View in Queue →
          </button>
        </div>
      )}

      {/* 1. Primary Dominant URL Input Hero */}
      <UrlHeroInput />

      {/* 2. Media Metadata Preview (Appears when single valid URL entered) */}
      <MetadataCard />

      {/* 3. Format, Quality, and Preset Options */}
      <FormatOptions />

      {/* 4. Primary Download CTA Button */}
      <div className="pt-2">
        <button
          onClick={handleStartDownload}
          disabled={detectedUrls.length === 0 || isSubmitting}
          className="w-full h-12 rounded-xl bg-primary text-white font-bold text-sm tracking-wide hover:bg-primary-hover shadow-md hover:shadow-lg disabled:opacity-40 disabled:pointer-events-none transition-all duration-150 flex items-center justify-center gap-2 select-none active:scale-[0.99]"
        >
          {isSubmitting ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Adding to Queue…</span>
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
