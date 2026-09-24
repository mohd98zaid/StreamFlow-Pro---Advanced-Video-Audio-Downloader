export type DownloadStatus =
  | "Queued"
  | "Downloading"
  | "Processing"
  | "Completed"
  | "Paused"
  | "Failed"
  | "Cancelled";

export type DownloadType = "video" | "audio" | "playlist";

export interface DownloadItem {
  id: string;
  url: string;
  title: string;
  download_type: DownloadType;
  quality: string;
  status: DownloadStatus;
  progress: number;
  speed: string;
  eta: string;
  file_path?: string | null;
  file_size?: number | null;
  created_at: string;
  completed_at?: string | null;
  channel?: string | null;
  duration?: string | null;
  thumbnail_url?: string | null;
  error?: string | null;
  is_paused?: boolean;
  is_cancelled?: boolean;
}

export interface QueueSummary {
  total: number;
  active: number;
  queued: number;
  paused: number;
  completed: number;
  failed: number;
}

export interface FormatPreset {
  name: string;
  download_type: DownloadType;
  quality: string;
  format_type: string;
  embed_thumbnail: boolean;
  embed_metadata: boolean;
  embed_subtitles: boolean;
}

export interface VideoMetadata {
  success: boolean;
  url: string;
  title: string;
  uploader: string;
  duration?: number;
  duration_str: string;
  thumbnail?: string;
  view_count?: number;
  is_playlist?: boolean;
  playlist_count?: number;
  available_qualities?: string[];
  error?: string;
}

export interface SearchResult {
  id: string;
  title: string;
  channel: string;
  url: string;
  duration?: number;
  duration_str: string;
  views?: number;
  views_str: string;
  thumbnail?: string;
}

export interface DownloadStats {
  total_downloads: number;
  successful_downloads: number;
  failed_downloads: number;
  total_size_bytes: number;
  total_size_formatted: string;
  success_rate: number;
  channels: Record<string, number>;
  categories: Record<string, number>;
}
