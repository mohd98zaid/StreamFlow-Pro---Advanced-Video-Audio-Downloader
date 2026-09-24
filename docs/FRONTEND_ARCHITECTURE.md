# StreamFlow Pro — Frontend Architecture & Component Specification

**Version:** 1.0.0  
**Stack:** React 19 / 18 + TypeScript + Vite + Tailwind CSS + Lucide React + Zustand  

---

## 1. Directory Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
└── src/
    ├── main.tsx                  # React DOM bootstrap
    ├── App.tsx                   # Main layout shell with custom titlebar & sidebar
    ├── index.css                 # CSS variables, root reset, typography styles
    ├── types/
    │   ├── download.ts           # DownloadItem, DownloadStatus, Preset, Metadata
    │   ├── config.ts             # SettingsConfig schema
    │   └── events.ts             # WebSocket envelope & event types
    ├── services/
    │   ├── api.ts                # REST API client wrapper
    │   └── websocket.ts          # Resilient WebSocket connection manager
    ├── stores/
    │   ├── useDownloadStore.ts   # Active input URL, format, quality, presets, metadata
    │   ├── useQueueStore.ts      # Active queue items, stats, filters
    │   ├── useHistoryStore.ts    # Download history, pagination, search query
    │   └── useSettingsStore.ts   # User settings, theme mode, download path
    ├── components/
    │   ├── layout/
    │   │   ├── Titlebar.tsx      # Window title, drag region, minimize/maximize/close
    │   │   ├── Sidebar.tsx       # Primary navigation, engine status indicator
    │   │   └── StatusFooter.tsx  # Download rate, active tasks count, engine status
    │   ├── ui/
    │   │   ├── Button.tsx        # Styled variants: primary, secondary, ghost, danger
    │   │   ├── Input.tsx         # Text & search inputs with focus ring
    │   │   ├── Select.tsx        # Styled dropdowns
    │   │   ├── Badge.tsx         # Status & quality tags
    │   │   ├── ProgressBar.tsx   # Precision progress track with smooth animation
    │   │   ├── Modal.tsx         # Backdrop modal container
    │   │   └── Toast.tsx         # Modern toast notifications
    │   ├── downloads/
    │   │   ├── UrlHeroInput.tsx  # Dominant URL box with paste & clear shortcuts
    │   │   ├── MetadataCard.tsx  # Live preview of entered URL (title, thumb, duration)
    │   │   ├── FormatOptions.tsx # Quality and format selector pills
    │   │   └── AdvancedModal.tsx # Collapsible subtitles, codecs, metadata embed
    │   ├── queue/
    │   │   ├── QueueSummary.tsx  # Active, queued, paused counts with bulk actions
    │   │   ├── QueueItemRow.tsx  # Media card with progress, speed, ETA, pause/cancel
    │   │   └── EmptyQueue.tsx    # Clean state when queue is idle
    │   ├── history/
    │   │   ├── HistoryList.tsx   # Searchable media history cards
    │   │   └── HistoryFilter.tsx # Filter by status, search title, clear history
    │   ├── search/
    │   │   ├── SearchInput.tsx   # YouTube search box
    │   │   └── SearchCard.tsx    # Card with thumbnail, duration, view count, queue/download CTA
    │   └── player/
    │       └── VideoModal.tsx    # In-app media player modal + ad-free stream launch
    └── pages/
        ├── DownloadPage.tsx      # Default view: Paste -> Options -> Download
        ├── QueuePage.tsx         # Real-time downloads queue & metrics
        ├── HistoryPage.tsx       # Media library & history
        ├── SearchPage.tsx        # Direct YouTube search & discovery
        └── SettingsPage.tsx      # Preferences, download paths, themes
```

---

## 2. State Management (Zustand Stores)

### 2.1 `useDownloadStore`
Manages the primary hero download workflow:
- `url`: Current input text (supports single or multi-line batch).
- `metadata`: Extracted metadata for URL (thumbnail, title, author, duration).
- `isExtracting`: Loading spinner flag during yt-dlp metadata inspection.
- `downloadType`: `"video" | "audio" | "playlist"`.
- `quality`: Selected resolution (`"2160p (4K)"`, `"1080p (Full HD)"`, etc.).
- `format`: Target extension (`"mp4"`, `"mp3"`, etc.).
- `options`: `{ embedThumbnail: true, embedMetadata: true, embedSubtitles: false }`.

### 2.2 `useQueueStore`
Subscribed directly to WebSocket `/ws`:
- `items`: Dictionary/array of active and queued `DownloadItem`s.
- `summary`: `{ total: number, active: number, paused: number, completed: number }`.
- Actions: `pauseItem(id)`, `resumeItem(id)`, `cancelItem(id)`, `retryItem(id)`, `pauseAll()`, `resumeAll()`, `clearCompleted()`.

### 2.3 `useHistoryStore`
- `records`: List of downloaded files loaded from SQLite.
- `query`, `statusFilter`: Filter states.
- Actions: `fetchHistory()`, `deleteRecord(id)`, `clearAll()`, `openFile(path)`, `openFolder(path)`.

### 2.4 `useSettingsStore`
- `theme`: `"dark" | "light" | "system"`.
- `downloadPath`: Directory path string.
- `concurrentDownloads`: Number of worker threads (1–10).
- `notificationsEnabled`: Boolean.
- Actions: `saveSettings(partialConfig)`, `setTheme(theme)`.
