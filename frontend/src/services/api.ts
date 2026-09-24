import {
  DownloadItem,
  FormatPreset,
  QueueSummary,
  VideoMetadata,
  SearchResult,
  DownloadStats,
} from "../types/download";
import { AppConfig } from "../types/config";

const API_BASE = "http://127.0.0.1:47891/api";

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!res.ok) {
      let errorMsg = `Server error (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorMsg = errJson.detail;
      } catch {}
      throw new Error(errorMsg);
    }

    return await res.json();
  } catch (err: any) {
    console.error(`API Request failed: ${endpoint}`, err);
    throw err;
  }
}

export const api = {
  // Health
  checkHealth: () => request<{ status: string; engine_ready: boolean }>("/health"),

  // Config
  getConfig: () => request<AppConfig>("/config"),
  updateConfig: (config: Partial<AppConfig>) =>
    request<AppConfig>("/config", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  // Presets
  getPresets: () => request<FormatPreset[]>("/presets"),

  // Validation & Metadata
  validateInput: (text: string) =>
    request<{
      valid_urls: string[];
      detected_sites: { url: string; site: string; supported: boolean }[];
      errors: { url: string; message: string }[];
      is_valid: boolean;
      count: number;
    }>("/validate", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  fetchMetadata: (url: string) =>
    request<VideoMetadata>("/metadata", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  // Queue & Downloads
  getQueue: () =>
    request<{
      items: DownloadItem[];
      summary: QueueSummary;
    }>("/queue"),

  addDownloads: (payload: {
    urls: string[];
    download_type?: string;
    quality?: string;
    format_type?: string;
    options?: Record<string, any>;
    save_path?: string;
  }) =>
    request<{
      success: boolean;
      added_count: number;
      duplicate_count: number;
      items: DownloadItem[];
      error?: string;
    }>("/downloads/add", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  pauseItem: (id: string) =>
    request<{ success: boolean }>(`/queue/${id}/pause`, { method: "POST" }),
  resumeItem: (id: string) =>
    request<{ success: boolean }>(`/queue/${id}/resume`, { method: "POST" }),
  cancelItem: (id: string) =>
    request<{ success: boolean }>(`/queue/${id}/cancel`, { method: "POST" }),
  retryItem: (id: string) =>
    request<{ success: boolean }>(`/queue/${id}/retry`, { method: "POST" }),
  removeItem: (id: string) =>
    request<{ success: boolean }>(`/queue/${id}/remove`, { method: "POST" }),

  pauseAll: () => request<{ success: boolean; count: number }>("/queue/pause_all", { method: "POST" }),
  resumeAll: () => request<{ success: boolean; count: number }>("/queue/resume_all", { method: "POST" }),
  clearCompleted: () =>
    request<{ success: boolean; count: number }>("/queue/clear_completed", { method: "POST" }),

  // History & Stats
  getHistory: (params?: { search?: string; status?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.search) q.append("search", params.search);
    if (params?.status) q.append("status", params.status);
    if (params?.limit) q.append("limit", params.limit.toString());
    if (params?.offset) q.append("offset", params.offset.toString());
    return request<{
      items: DownloadItem[];
      count: number;
      limit: number;
      offset: number;
    }>(`/history?${q.toString()}`);
  },

  deleteHistoryItem: (id: string) =>
    request<{ success: boolean }>(`/history/${id}`, { method: "DELETE" }),
  clearHistory: () =>
    request<{ success: boolean }>("/history/clear", { method: "POST" }),
  getStatistics: () => request<DownloadStats>("/stats"),

  // YouTube Search
  searchYouTube: (query: string, limit = 15) =>
    request<{ results: SearchResult[]; count: number }>("/search", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    }),

  // Media Actions
  openFile: (filePath: string) =>
    request<{ success: boolean }>("/actions/open_file", {
      method: "POST",
      body: JSON.stringify({ file_path: filePath }),
    }),

  openFolder: (path?: string) =>
    request<{ success: boolean }>("/actions/open_folder", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),

  openPlayer: (videoId: string, title?: string) =>
    request<{ success: boolean }>("/actions/open_player", {
      method: "POST",
      body: JSON.stringify({ video_id: videoId, title: title || "Video Preview" }),
    }),

  browseDirectory: () =>
    request<{ success: boolean; selected_path?: string; cancelled?: boolean }>(
      "/actions/browse_directory",
      { method: "POST" }
    ),
};
