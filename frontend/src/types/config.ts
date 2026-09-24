export interface AppConfig {
  download_path: string;
  theme: "dark" | "light" | "system";
  window_size?: string;
  last_position?: string;
  auto_retry?: boolean;
  max_retries?: number;
  embed_thumbnail: boolean;
  embed_metadata: boolean;
  embed_subtitles: boolean;
  last_download_type?: string;
  last_quality?: string;
  last_format_type?: string;
  concurrent_downloads: number;
  notifications_enabled: boolean;
  taskbar_progress?: boolean;
  system_tray?: boolean;
  last_preset?: string;
  filename_pattern?: string;
}
