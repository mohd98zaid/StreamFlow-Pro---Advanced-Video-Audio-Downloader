import { DownloadItem, QueueSummary } from "./download";

export type WebSocketEventType =
  | "connected"
  | "download_started"
  | "download_progress"
  | "download_completed"
  | "download_failed"
  | "download_paused"
  | "download_resumed"
  | "download_cancelled"
  | "queue_updated"
  | "history_updated"
  | "status_message"
  | "log_message";

export interface WebSocketEnvelope<T = any> {
  event: WebSocketEventType;
  timestamp: string;
  data: T;
}

export interface ConnectedEventData {
  queue: {
    items: DownloadItem[];
    summary: QueueSummary;
  };
  config: Record<string, any>;
  presets: any[];
}
