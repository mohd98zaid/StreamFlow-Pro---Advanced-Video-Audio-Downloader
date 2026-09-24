import { create } from "zustand";
import { DownloadType, FormatPreset, VideoMetadata } from "../types/download";
import { api } from "../services/api";

interface DownloadStore {
  urlInput: string;
  detectedUrls: string[];
  isExtracting: boolean;
  metadata: VideoMetadata | null;
  error: string | null;

  downloadType: DownloadType;
  quality: string;
  formatType: string;
  embedThumbnail: boolean;
  embedMetadata: boolean;
  embedSubtitles: boolean;

  presets: FormatPreset[];
  activePreset: string;

  setUrlInput: (text: string) => void;
  setDownloadType: (type: DownloadType) => void;
  setQuality: (quality: string) => void;
  setFormatType: (format: string) => void;
  setEmbedThumbnail: (val: boolean) => void;
  setEmbedMetadata: (val: boolean) => void;
  setEmbedSubtitles: (val: boolean) => void;
  applyPreset: (presetName: string) => void;

  extractMetadata: (url: string) => Promise<void>;
  loadPresets: () => Promise<void>;
  resetInput: () => void;
}

export const useDownloadStore = create<DownloadStore>((set, get) => ({
  urlInput: "",
  detectedUrls: [],
  isExtracting: false,
  metadata: null,
  error: null,

  downloadType: "video",
  quality: "1080p (Full HD)",
  formatType: "mp4",
  embedThumbnail: true,
  embedMetadata: true,
  embedSubtitles: false,

  presets: [],
  activePreset: "Default",

  setUrlInput: (text: string) => {
    set({ urlInput: text });
    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.startsWith("http://") || l.startsWith("https://"));
    set({ detectedUrls: lines });

    // Auto-extract metadata for single entered URL
    if (lines.length === 1 && lines[0] !== get().metadata?.url) {
      get().extractMetadata(lines[0]);
    } else if (lines.length === 0) {
      set({ metadata: null, error: null });
    }
  },

  setDownloadType: (type: DownloadType) => {
    set({ downloadType: type });
    if (type === "audio") {
      set({ formatType: "mp3" });
    }
  },

  setQuality: (quality: string) => set({ quality }),
  setFormatType: (formatType: string) => set({ formatType }),
  setEmbedThumbnail: (embedThumbnail: boolean) => set({ embedThumbnail }),
  setEmbedMetadata: (embedMetadata: boolean) => set({ embedMetadata }),
  setEmbedSubtitles: (embedSubtitles: boolean) => set({ embedSubtitles }),

  applyPreset: (presetName: string) => {
    const preset = get().presets.find((p) => p.name === presetName);
    if (!preset) return;
    set({
      activePreset: presetName,
      downloadType: preset.download_type,
      quality: preset.quality || (preset.download_type === "audio" ? "" : "1080p (Full HD)"),
      formatType: preset.format_type || (preset.download_type === "audio" ? "mp3" : "mp4"),
      embedThumbnail: preset.embed_thumbnail,
      embedMetadata: preset.embed_metadata,
      embedSubtitles: preset.embed_subtitles,
    });
  },

  extractMetadata: async (url: string) => {
    set({ isExtracting: true, error: null });
    try {
      const data = await api.fetchMetadata(url);
      set({ metadata: data, isExtracting: false });
      if (data.is_playlist) {
        set({ downloadType: "playlist" });
      }
      if (data.available_qualities && data.available_qualities.length > 0) {
        if (!data.available_qualities.includes(get().quality)) {
          set({ quality: data.available_qualities[0] });
        }
      }
    } catch (err: any) {
      set({ isExtracting: false, error: err.message || "Failed to inspect media info" });
    }
  },

  loadPresets: async () => {
    try {
      const presets = await api.getPresets();
      set({ presets });
    } catch (err) {
      console.error("Failed to load presets:", err);
    }
  },

  resetInput: () => {
    set({
      urlInput: "",
      detectedUrls: [],
      metadata: null,
      error: null,
      isExtracting: false,
    });
  },
}));
