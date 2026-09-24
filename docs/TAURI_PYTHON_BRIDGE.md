# StreamFlow Pro — Tauri & Python Communication Protocol

**Document Version:** 1.0.0  
**Security Boundary:** Localhost Only (`127.0.0.1`), Session-Bound  
**Protocol:** REST Commands + Asynchronous WebSocket Event Stream  

---

## 1. Overview

StreamFlow Pro operates as a decoupled architecture:
1. **Frontend (Tauri + React + TypeScript):** Handles presentation, view transitions, user input, audio/video preview playback, and optimistic state updates.
2. **Backend Engine (Python Service):** Manages `yt-dlp` execution, multi-threaded worker pools, FFmpeg transmuxing/encoding, SQLite historical archives, and operating system file operations.

```
┌──────────────────────────────────────────────┐
│        React UI (Zustand Stores)             │
│   • useDownloadStore   • useQueueStore       │
│   • useHistoryStore    • useSettingsStore    │
└──────────────┬───────────────────────────────┘
               │  HTTP (REST) / WebSocket
┌──────────────▼───────────────────────────────┐
│     Local Python Bridge (backend/server.py)  │
│     FastAPI / Uvicorn (127.0.0.1:47891)      │
└──────────────┬───────────────────────────────┘
               │
┌──────────────▼───────────────────────────────┐
│    Existing Python Core Engine               │
│  • Downloader (ThreadPoolExecutor)           │
│  • EventBus (pub-sub)                        │
│  • DatabaseManager (SQLite)                  │
│  • ConfigManager (JSON)                      │
└──────────────────────────────────────────────┘
```

---

## 2. WebSocket Event Stream (`/ws`)

When the React frontend mounts, it establishes a persistent WebSocket connection to `ws://127.0.0.1:47891/ws`. The Python engine maps internal `core.events.Event` emissions into structured JSON envelopes:

### 2.1 Event Schema

```typescript
export interface WebSocketMessage<T = unknown> {
  event: 
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
  data: T;
  timestamp: string;
}
```

### 2.2 Payload Examples

#### `download_progress`
```json
{
  "event": "download_progress",
  "data": {
    "id": "7f8b9a2c-1234-4a5b-bce9-9f8e7d6c5b4a",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "status": "Downloading",
    "progress": 72.4,
    "speed": "8.4 MB/s",
    "eta": "00:21",
    "download_type": "video",
    "quality": "1080p (Full HD)",
    "file_path": null,
    "error": null
  },
  "timestamp": "2026-09-24T11:30:00.000Z"
}
```

#### `download_completed`
```json
{
  "event": "download_completed",
  "data": {
    "id": "7f8b9a2c-1234-4a5b-bce9-9f8e7d6c5b4a",
    "title": "Rick Astley - Never Gonna Give You Up",
    "file_path": "C:\\Users\\mohd9\\Downloads\\Rick Astley - Never Gonna Give You Up.mp4",
    "file_size": 45182904,
    "completed_at": "2026-09-24T11:30:21.000Z"
  },
  "timestamp": "2026-09-24T11:30:21.000Z"
}
```

---

## 3. REST API Endpoints

All REST routes are strictly bound to `127.0.0.1:47891`.

### 3.1 Metadata & Validation
- `POST /api/validate`: Validates syntax and detects platform domain (YouTube, Vimeo, SoundCloud, etc.).
- `POST /api/metadata`: Fast metadata extraction using `yt-dlp` (`title`, `uploader`, `duration`, `thumbnail`, `formats`, `is_playlist`).

### 3.2 Downloads & Queue Management
- `GET /api/queue`: Returns all active, paused, queued, and completed items in memory.
- `POST /api/downloads/add`: Accepts one or multiple URLs with target options and format presets. Auto-expands playlists into numbered queue items.
- `POST /api/queue/:id/pause`: Pauses active download.
- `POST /api/queue/:id/resume`: Resumes paused download.
- `POST /api/queue/:id/cancel`: Cancels item and releases thread.
- `POST /api/queue/:id/retry`: Re-queues a failed download.
- `POST /api/queue/pause_all`: Bulk pause.
- `POST /api/queue/resume_all`: Bulk resume.
- `POST /api/queue/clear_completed`: Clears completed/cancelled items from queue.

### 3.3 History & Analytics
- `GET /api/history?search=&status=&limit=100&offset=0`: Paginated SQLite history query.
- `DELETE /api/history/:id`: Removes single history entry.
- `POST /api/history/clear`: Clears entire history table.
- `GET /api/stats`: Returns total downloaded bytes, success count, failure count, and top channels.

### 3.4 YouTube Search & Media Actions
- `POST /api/search`: Invokes yt-dlp `ytsearch15:` and returns array of results with titles, channels, view counts, duration, and thumbnail URLs.
- `POST /api/actions/open_file`: Reveals or plays downloaded file in Windows default player.
- `POST /api/actions/open_folder`: Opens containing directory in Windows File Explorer.
- `POST /api/actions/open_player`: Triggers ad-free player or Yuma Studio via `utils/player_process.py`.
- `POST /api/actions/browse_directory`: Opens native folder dialog for download path selection.

### 3.5 Configuration & Presets
- `GET /api/config`: Reads `ConfigManager` configuration.
- `POST /api/config`: Updates application settings (directory, concurrency limit, notifications, theme).
- `GET /api/presets`: Returns all format preset configurations.
