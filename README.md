# StreamFlow Pro

StreamFlow Pro is a Windows-focused video and audio downloader with a React desktop interface, a Python/`yt-dlp` download engine, a local FastAPI bridge, and a separate embedded YouTube/music player.

The application is designed for local use: the frontend talks to the Python service over loopback, downloads are processed by a concurrent Python queue, and history/configuration are stored under the current user's home directory.

> **Important:** Only download or process media that you are authorized to use. Availability, playback, captions, lyrics, and ad behavior depend on the source platform, network access, and the installed `yt-dlp` version.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the application](#running-the-application)
- [Frontend development](#frontend-development)
- [Tauri development and packaging](#tauri-development-and-packaging)
- [Configuration and data files](#configuration-and-data-files)
- [REST API](#rest-api)
- [WebSocket protocol](#websocket-protocol)
- [Player and lyrics](#player-and-lyrics)
- [Project layout](#project-layout)
- [Testing and validation](#testing-and-validation)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

### Download engine

- Single URL and multi-URL downloads.
- Video, audio, and playlist download modes.
- Quality selection from 360p through 4K where the source provides it.
- Audio extraction through FFmpeg post-processors.
- MP3, M4A, and other format values supported by the configured `yt-dlp`/FFmpeg path.
- Optional thumbnail, metadata, and English subtitle embedding.
- Concurrent queue processing with pause, resume, cancel, retry, and bulk actions.
- Duplicate protection for active, queued, downloading, and processing URLs.
- SQLite-backed download history and statistics.
- Local file and folder actions through Windows Explorer/default applications.

### React workstation

- Download page with URL validation, metadata extraction, format selection, and advanced options.
- Live queue with progress, speed, ETA, status, and item actions.
- Search page backed by `yt-dlp` search extraction.
- History page with search, status filtering, pagination, delete, clear, open-file, and open-folder actions.
- Settings for download path, theme, retry behavior, concurrency, notifications, and media embedding options.
- Zustand stores for download workflow, queue state, history, and settings.
- Automatic WebSocket reconnect and periodic ping/pong keepalive.

### StreamFlow Studio player

- Separate pywebview player window launched from the desktop bridge or `run.bat`.
- Cinema/video view and music-focused Studio view.
- Queue-aware previous, next, shuffle, repeat-all, and repeat-one controls.
- Seek, volume, mute, fullscreen, equalizer, and MP3 queue actions.
- Right-side Studio deck with **Up Next** and **Lyrics** panels.
- Lyrics provider lookup modeled after BitChord's provider-first approach:
  - `lrc.red`
  - BiniLyrics
  - BetterLyrics
  - BetterLyrics Portato
  - LyricsPlus
  - Unison
  - LRCLIB
  - KuGou
  - Genius
- Provider responses are normalized from TTML, LRC, JSON envelopes, HTML/plain text, or timed lines.
- Word/syllable-timed results are preferred, then line-timed results, then plain lyrics.
- The winning lyrics provider is shown in the Lyrics panel when available.
- Embedded YouTube ad handling uses document-start cosmetic hiding plus runtime detection, mute, skip-button clicks, and accelerated playback. It is not a network-level guarantee and may change when the source platform changes its page/player implementation.

## Architecture

```text
                         Local Windows machine

  React/Vite UI or Tauri window
          │
          │ HTTP REST + WebSocket
          ▼
  FastAPI bridge: 127.0.0.1:47891
          │
          ▼
  BackendApiAdapter
          │
          ├── Downloader + ThreadPoolExecutor
          ├── EventBus
          ├── ConfigManager
          ├── DatabaseManager / SQLite
          └── PresetManager
          │
          ├── yt-dlp extractors
          ├── static-ffmpeg post-processing
          └── local download directory

  Separate Studio player:
  utils/player_process.py → pywebview → source platform/player page
                              ├── Studio UI injection
                              ├── queue/playback controls
                              ├── ad handling
                              └── lyrics provider bridge
```

### Runtime flow

1. `run_modern.py` checks for `frontend/dist/index.html` and builds the frontend if it is missing.
2. It starts Uvicorn on `127.0.0.1:47891`.
3. The backend exposes REST endpoints and `/ws`.
4. The frontend loads queue/config/preset state and subscribes to WebSocket events.
5. `BackendApiAdapter` translates API requests into calls to the core downloader, database, configuration, and preset managers.
6. Downloader events are converted into JSON WebSocket envelopes and broadcast to connected frontend clients.
7. The Studio player is launched as a separate pywebview process. MP3 requests from that process are written to the SQLite `inbox_queue`, where the main downloader can consume them.

### Local security boundary

The bridge binds to `127.0.0.1`, not a public interface. CORS is limited to the local development/bridge origins declared in `backend/server.py`. Do not change the host to `0.0.0.0` without adding authentication, authorization, and an intentional deployment design.

## Requirements

### Runtime

- Windows 10 or Windows 11.
- Python 3.10 or newer is recommended by the project configuration.
- A working `python` or `py` command on `PATH`.
- Microsoft WebView2 for the pywebview Edge/WebView2 player and modern launcher.
- Internet access for metadata extraction, downloads, search, player pages, and lyric providers.

### Frontend development

- Node.js and npm.
- Dependencies declared in `frontend/package.json` and locked in `frontend/package-lock.json`.

### Native Tauri builds

- Rust compatible with `rust-version = "1.77.2"` in `src-tauri/Cargo.toml`.
- Cargo and the Windows build tools required by Tauri.
- The Tauri CLI dependency installed through the frontend package.

## Installation

### 1. Clone the repository

```powershell
git clone <repository-url>
cd VideoDownloaderPython
```

### 2. Create a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script activation, use Command Prompt or call the Python executable directly:

```bat
.venv\Scripts\activate.bat
```

### 3. Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The current requirements include:

| Package | Role |
| --- | --- |
| `yt-dlp` | Metadata extraction, search, and media downloads |
| `static-ffmpeg` | Adds an FFmpeg distribution/path for post-processing |
| `pywebview` | Native Windows/WebView2 windows for the launcher and Studio player |
| `fastapi` | Local REST/WebSocket bridge |
| `uvicorn` | ASGI server |
| `pillow` | Image-related application support |
| `win10toast` | Optional Windows notifications |

### 4. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

## Running the application

### Recommended Windows launcher

From the repository root:

```bat
run.bat
```

The menu provides:

```text
[1] YouTube & Music Player (StreamFlow Studio)
[2] StreamFlow Pro Modern Downloader
[3] Exit
```

The player is the default when you press Enter.

### Launcher command shortcuts

```bat
run.bat player
run.bat music
run.bat yt
run.bat 1

run.bat modern
run.bat downloader
run.bat 2
```

The launcher automatically activates `venv`, `.venv`, or `env` when one exists beside the project.

### Python entry point

`main.py` starts the modern downloader by default:

```powershell
python main.py
```

Launch Studio directly with a player flag:

```powershell
python main.py --player
python main.py --music
```

### Modern downloader directly

```powershell
python run_modern.py
```

`run_modern.py`:

1. Builds `frontend/dist` when no production frontend bundle exists.
2. Starts FastAPI on `http://127.0.0.1:47891`.
3. Waits for `/api/status`.
4. Opens the application in a pywebview window.
5. Falls back to the default system browser if pywebview cannot create a window.

The backend can then be opened manually at:

```text
http://127.0.0.1:47891
```

## Frontend development

### Start the backend

From the repository root:

```powershell
python -c "import uvicorn; from backend.server import app; uvicorn.run(app, host='127.0.0.1', port=47891)"
```

### Start Vite

In a second terminal:

```powershell
cd frontend
npm run dev
```

Open the Vite URL shown in the terminal, normally:

```text
http://127.0.0.1:5173
```

The frontend API client is configured for `http://127.0.0.1:47891/api` and its WebSocket client uses `ws://127.0.0.1:47891/ws`.

### Frontend commands

Run these from `frontend/`:

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start Vite development server |
| `npm run build` | Run the TypeScript build and create Vite output |
| `npm run lint` | Run Oxlint |
| `npm run preview` | Preview the generated Vite build |

## Tauri development and packaging

The Tauri configuration is in `src-tauri/tauri.conf.json`. It uses `frontend/dist` as the production frontend directory, `http://localhost:5173` as the development URL, and runs the frontend build before packaging.

The project does not define dedicated `tauri` npm scripts, so invoke the installed CLI through npm from the repository root:

```powershell
npm exec --prefix frontend -- tauri dev
```

To build native bundles:

```powershell
npm exec --prefix frontend -- tauri build
```

The Tauri window is configured with:

- Product name: `StreamFlow Pro`
- Identifier: `com.streamflow.pro`
- Default size: `1180 × 780`
- Minimum size: `960 × 640`
- Resizable window
- Bundle targets: all targets supported by the installed Tauri toolchain

The current Python launcher (`run_modern.py`) uses pywebview directly. Tauri is the configured native shell/build path for the frontend; the Python bridge still needs to be running when the UI makes API requests.

## Configuration and data files

StreamFlow stores user data under:

```text
%USERPROFILE%\.VideoDownloader\
```

### Files

| Path | Purpose |
| --- | --- |
| `%USERPROFILE%\.VideoDownloader\config.json` | Persistent application configuration |
| `%USERPROFILE%\.VideoDownloader\history.db` | SQLite downloads, statistics, and player inbox queue |
| `%USERPROFILE%\.VideoDownloader\history.json` | Legacy history source used during migration if present |
| `downloader.log` | Root-level runtime log created by `main.py` |
| `frontend/dist/` | Vite production bundle used by the local backend/Tauri configuration |

### Default configuration

The defaults are defined in `core/config.py`:

| Key | Default | Meaning |
| --- | --- | --- |
| `download_path` | `%USERPROFILE%\Downloads` | Output directory |
| `theme` | `dark` | Frontend theme |
| `window_size` | `1150x800` | Stored window preference |
| `last_position` | `+100+100` | Stored window position |
| `auto_retry` | `true` | Enable retry behavior |
| `max_retries` | `3` | Maximum retries |
| `embed_thumbnail` | `true` | Embed thumbnails when supported |
| `embed_metadata` | `true` | Embed metadata when supported |
| `embed_subtitles` | `false` | Embed English subtitles when supported |
| `last_download_type` | `Video` | Last selected download type |
| `last_quality` | `1080p (Full HD)` | Last selected video quality |
| `last_format_type` | `mp4` | Last selected format |
| `concurrent_downloads` | `3` | Maximum concurrent downloader workers |
| `notifications_enabled` | `true` | Windows notification preference |
| `taskbar_progress` | `true` | Taskbar progress preference |
| `system_tray` | `false` | System tray preference |
| `auto_update_check` | `true` | Update-check preference |
| `last_preset` | `Default` | Last selected preset |
| `show_statistics` | `true` | Statistics visibility preference |
| `db_migration_done` | `false` | Legacy history migration marker |

### Built-in presets

The current preset names are defined in `utils/presets.py`:

- `Default`
- `High Quality Video (4K)`
- `Quick Video (720p)`
- `Mobile Video (480p)`
- `Music (MP3 High Quality)`
- `Music (M4A)`
- `Podcast/Audio Book (MP3)`
- `Video with Subtitles`
- `Best Quality Available`

## REST API

The backend listens on `127.0.0.1:47891`. JSON requests should use `Content-Type: application/json`.

### Health, configuration, and presets

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health status |
| `GET` | `/api/status` | Alias for health status |
| `GET` | `/api/config` | Read configuration |
| `POST` | `/api/config` | Merge and save configuration values |
| `GET` | `/api/presets` | List format presets |

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:47891/api/status
```

### Validation and metadata

| Method | Route | Request body |
| --- | --- | --- |
| `POST` | `/api/validate` | `{ "text": "<one or more URLs>" }` |
| `POST` | `/api/metadata` | `{ "url": "https://..." }` |

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:47891/api/validate `
  -ContentType 'application/json' `
  -Body '{"text":"https://www.youtube.com/watch?v=..."}'
```

### Downloads and queue

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/queue` | Current queue and summary |
| `POST` | `/api/downloads/add` | Add one or more URLs |
| `POST` | `/api/queue/{item_id}/pause` | Pause one item |
| `POST` | `/api/queue/{item_id}/resume` | Resume one item |
| `POST` | `/api/queue/{item_id}/cancel` | Cancel one item |
| `POST` | `/api/queue/{item_id}/retry` | Retry one failed item |
| `POST` | `/api/queue/{item_id}/remove` | Remove one item |
| `POST` | `/api/queue/pause_all` | Pause all eligible items |
| `POST` | `/api/queue/resume_all` | Resume all paused items |
| `POST` | `/api/queue/clear_completed` | Remove completed/failed/cancelled queue entries |

Example add request:

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=example"
  ],
  "download_type": "video",
  "quality": "1080p (Full HD)",
  "format_type": "mp4",
  "options": {
    "embed_thumbnail": true,
    "embed_metadata": true,
    "embed_subtitles": false
  },
  "save_path": "C:\Users\you\Downloads"
}
```

### History and statistics

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/history` | Paginated history; supports `search`, `status`, `limit`, and `offset` |
| `DELETE` | `/api/history/{item_id}` | Delete one history record |
| `POST` | `/api/history/clear` | Clear history |
| `GET` | `/api/stats` | Download counts, bytes, success rate, channels, and categories |

Example history query:

```text
GET http://127.0.0.1:47891/api/history?status=Completed&limit=50&offset=0
```

### Search and operating-system actions

| Method | Route | Request |
| --- | --- | --- |
| `POST` | `/api/search` | `{ "query": "search text", "limit": 15 }` |
| `POST` | `/api/actions/open_file` | `{ "file_path": "C:\...\file.mp4" }` |
| `POST` | `/api/actions/open_folder` | `{ "path": "C:\..." }` or `{}` |
| `POST` | `/api/actions/open_player` | `{ "video_id": "...", "title": "..." }` |
| `POST` | `/api/actions/browse_directory` | No body; opens a native folder picker |
| `POST` | `/api/system/shutdown` | Stops the downloader engine |

Operating-system actions are intended for the local desktop application. Do not expose this bridge to a network or untrusted browser.

## WebSocket protocol

Connect to:

```text
ws://127.0.0.1:47891/ws
```

On connection, the server sends a `connected` snapshot containing queue, config, and presets. The client may send the text message `ping`; the server replies with `pong`.

Event envelopes use this shape:

```json
{
  "event": "download_progress",
  "timestamp": "2026-10-26T12:00:00",
  "data": {
    "id": "download-item-id",
    "status": "Downloading",
    "progress": 42.5,
    "speed": "8.4 MB/s",
    "eta": "00:21"
  }
}
```

The event names are defined in `core/events.py`:

- `download_started`
- `download_progress`
- `download_completed`
- `download_failed`
- `download_paused`
- `download_resumed`
- `download_cancelled`
- `queue_updated`
- `history_updated`
- `status_message`
- `log_message`

## Player and lyrics

### Launching Studio

The REST route `/api/actions/open_player` starts `utils/player_process.py` in a separate process. The standalone launcher starts the same module with the YouTube home page:

```bat
run.bat player
```

The player supports a direct video ID or URL when launched from Python code. The main player window uses pywebview and the native JavaScript bridge exposed by `PlayerApi`.

### Studio layout

The music-focused view contains:

- Artwork and transport deck on the right side.
- Up Next/recommendations on the left side.
- Seek, volume, mute, shuffle, repeat, equalizer, fullscreen, and MP3 queue controls.
- An Up Next/Lyrics switch.

### Lyrics lookup rules

The native `PlayerApi.get_lyrics()` method performs the provider lookup because the embedded WebView cannot reliably reach every lyrics origin directly. The implementation follows the provider-selection model used by the BitChord reference:

1. Search title and artist strings are cleaned before lookup.
2. Providers are queried concurrently.
3. The declared provider priority order is applied after responses arrive.
4. Word/syllable-timed lyrics win over line-timed lyrics.
5. Line-timed lyrics win over plain text.
6. The panel parses the selected result and synchronizes timed lines to the playing video.
7. The selected provider name is shown in the panel status.

Provider availability is not guaranteed. A provider may rate-limit, change its response format, require a reachable network, or have no match for a recording.

### Ad handling

The player injects CSS at document creation and after page load to hide known ad overlays, sponsored cards, and selected promotional dialogs. A runtime observer checks for active ad classes/state and may mute the video, accelerate detected ad playback, click native skip controls, remove overlays, and restore normal playback settings after the ad state ends.

This is page-level handling, not a network proxy or a promise that every advertisement will be removed. Source-platform changes can make selectors or behavior obsolete.

## Project layout

```text
.
├── backend/
│   ├── server.py          # FastAPI app, REST routes, WebSocket endpoint
│   └── api_adapter.py     # Adapter around the core engine
├── core/
│   ├── config.py          # JSON configuration manager
│   ├── database.py        # SQLite history/statistics/inbox queue
│   ├── downloader.py      # yt-dlp queue and worker orchestration
│   ├── events.py          # Event enum and thread-safe EventBus
│   └── models.py          # Queue, download, stats, and preset models
├── frontend/
│   ├── src/
│   │   ├── components/    # Layout, download, queue, media, search, UI
│   │   ├── pages/         # Download, queue, history, search, settings views
│   │   ├── services/      # REST and WebSocket clients
│   │   ├── stores/        # Zustand state stores
│   │   └── types/         # TypeScript API/domain types
│   ├── package.json
│   └── vite.config.ts
├── src-tauri/
│   ├── src/               # Tauri Rust entry points
│   ├── Cargo.toml
│   └── tauri.conf.json
├── utils/
│   ├── player_process.py  # Studio player, ad handling, lyrics bridge
│   ├── presets.py         # Built-in format presets
│   ├── validators.py      # URL/platform validation
│   ├── notifications.py   # Windows notifications
│   └── studio_assets.py   # Embedded player visual assets
├── docs/                  # Architecture and migration notes
├── tests/                 # Python unit/integration tests
├── main.py                # Python entry point
├── run_modern.py          # Backend + modern UI launcher
├── run.bat                # Windows menu launcher
└── requirements.txt
```

## Testing and validation

### Python tests

Run all repository tests from the root:

```powershell
python -m unittest discover tests -v
```

The test suite covers model behavior and backend adapter operations, including queue transitions, configuration, presets, URL validation, event-bus integration, and bulk queue actions.

### Python syntax check

```powershell
python -m compileall -q backend core utils main.py run_modern.py
```

### Frontend lint and build

```powershell
cd frontend
npm run lint
npm run build
```

### Generated Studio payload check

The Studio UI is assembled into a JavaScript payload at runtime. After changing `utils/player_process.py`, validate Python syntax and, if Node.js is available, validate the generated payload:

```powershell
python -m py_compile utils/player_process.py
python -c "from pathlib import Path; from utils.player_process import get_cinema_payload; Path('player-payload.js').write_text(get_cinema_payload(), encoding='utf-8')"
node --check player-payload.js
Remove-Item player-payload.js
```

The generated file is temporary and should not be committed.

## Troubleshooting

### `python` or `py` is not found

Install Python and enable **Add Python to PATH**, then open a new terminal. The Windows launcher checks both `python` and `py`.

```powershell
python --version
py --version
```

### Dependencies are missing

Activate the virtual environment and reinstall:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### The modern UI cannot reach the backend

Check the health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:47891/api/status
```

If it fails, start the modern launcher:

```powershell
python run_modern.py
```

Check that another process is not using port `47891`:

```powershell
Get-NetTCPConnection -LocalPort 47891 -ErrorAction SilentlyContinue
```

### The frontend opens but shows no data

Confirm that:

1. The backend is running on `127.0.0.1:47891`.
2. The browser/dev server is using `127.0.0.1:5173` or `localhost:5173`.
3. The frontend API client still points to `http://127.0.0.1:47891/api`.
4. The browser console does not show a CORS or WebSocket connection error.

### The frontend build fails

From `frontend/`:

```powershell
Remove-Item -Recurse -Force node_modules
npm install
npm run lint
npm run build
```

### Downloads fail during audio/video merging

`static-ffmpeg` is responsible for making FFmpeg available to the Python process. Reinstall it and verify the Python import:

```powershell
python -m pip install --upgrade static-ffmpeg
python -c "import static_ffmpeg; static_ffmpeg.add_paths(); print('FFmpeg path configured')"
```

### A URL is rejected

Use the application validation step or call:

```text
POST /api/validate
{"text":"https://example.com/media"}
```

Support depends on the `yt-dlp` extractor installed in the current environment. Update `yt-dlp` before reporting a source-specific extraction issue:

```powershell
python -m pip install --upgrade yt-dlp
```

### History or settings appear to reset

Inspect `%USERPROFILE%\.VideoDownloader\config.json` and `%USERPROFILE%\.VideoDownloader\history.db`. The application creates the directory automatically. If the files are moved or deleted, the application starts with defaults and a new SQLite database.

### Studio player does not open

Check that pywebview and Microsoft WebView2 are installed:

```powershell
python -c "import webview; print('pywebview import ok')"
```

The player also needs network access to the source page. If the page layout changes, the injected Studio controls or ad selectors may require maintenance in `utils/player_process.py`.

### Lyrics are unavailable

Lyrics are best-effort and depend on external providers. Check:

1. The track title and artist were extracted correctly.
2. The player has network access.
3. The lyrics provider has a matching recording.
4. The provider has not rate-limited or changed its API response.

No lyrics result does not indicate a download failure.

## Contributing

Before submitting a change:

1. Keep the local-only bridge boundary intact unless the change includes an explicit security design.
2. Preserve existing queue, history, and playback behavior.
3. Update affected documentation and API examples.
4. Run the narrowest relevant checks, then the full Python test suite and frontend build when applicable.
5. Avoid committing generated files such as `frontend/dist`, `__pycache__`, logs, temporary player payloads, or Tauri build output unless the project explicitly requires them.

For UI changes, inspect the rendered desktop/browser result at both desktop and narrow widths. For player changes, validate the generated JavaScript payload with `node --check` in addition to Python syntax checks.

## License

No `LICENSE` file is currently present in this repository. Add a license file before distributing the project or publishing a definitive license statement.

## Related documentation

- [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md)
- [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md)
- [`docs/TAURI_PYTHON_BRIDGE.md`](docs/TAURI_PYTHON_BRIDGE.md)
- [`docs/UI_MIGRATION_AUDIT.md`](docs/UI_MIGRATION_AUDIT.md)
- [`docs/MIGRATION_STATUS.md`](docs/MIGRATION_STATUS.md)
