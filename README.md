# 🎬 Advanced Video & Audio Downloader (Python + CustomTkinter)

A powerful, high-performance, and feature-rich desktop YouTube & media downloader built with Python, `yt-dlp`, `CustomTkinter`, and Microsoft Edge WebView2.

---

## ✨ Key Highlights

### ⚡ Core & Download Capabilities
- **Multi-Threaded Concurrent Downloads**: Download 3–5 videos simultaneously with maximum bandwidth utilization.
- **Ultra-HD Video & Lossless Audio**: Support for 4K, 2K, 1080p, 720p, 480p down to 144p, plus audio extraction in MP3, M4A, WAV, and FLAC.
- **YouTube In-App Search**: Search YouTube directly inside the app, inspect results, and download with a single click.
- **Ad-Free In-App Video Preview Player**: Preview any video or song before downloading with zero ads in an ultra-clean Chromium WebView window.
- **100% Song & Music Video Compatibility**: Plays restricted music videos and official VEVO/label songs without third-party embed errors.
- **Dual-View Switcher**: Seamlessly switch between **`🎬 Cinema Mode`** (distraction-free full window) and **`🌐 YouTube View`** (full interface with channel and comments).
- **Persistent User Preferences**: Automatically remembers your chosen theme (Dark/Light), default format, download directory, and quality preset across app restarts.
- **Smart Queue Management**: Batch add URLs, pause, resume, cancel, and track individual progress, speed, and ETA.
- **SQLite Download History**: Complete history tracking with search, filters, pagination, and one-click file playback.
- **Automatic FFmpeg Integration**: Integrated `static-ffmpeg` ensures flawless video and audio multiplexing without manual system PATH configuration.

---

## 📸 Interface & Player Controls

| Feature | Description |
| :--- | :--- |
| **🎬 Preview Video** | Double-click any search result or click `🎬 Preview Video (Ad-Free)` |
| **⛶ Maximize Screen** | Fullscreen toggle button located in the top floating bar |
| **🗗 Restore Window** | Press the physical **`Esc`** keyboard key anytime to exit fullscreen |
| **🌐 View Switcher** | Switch between pure Cinema player and full YouTube web view |
| **⚙️ Quality & Subtitles** | Access native YouTube 4K/1080p resolution picker and `[CC]` captions |
| **⏱️ Auto-Hide** | Player control bar automatically disappears after 2 seconds of mouse inactivity |

---

## 📦 Installation & Setup

### Prerequisites
- Python **3.8+** (Python 3.10 - 3.12 recommended)
- Windows 10 / 11 (WebView2 runtime is built-in)

### Quick Setup

1. **Clone the repository**:
   ```bash
   git clone <YOUR_REPO_URL>
   cd VideoDownloaderPython
   ```

2. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```
   *Alternatively, double-click `run.bat` on Windows.*

---

## 🛠️ Required Dependencies

```txt
customtkinter>=5.2.0
yt-dlp>=2024.0.0
pywebview>=5.0.0
static-ffmpeg>=2.5
Pillow>=10.0.0
win10toast>=0.9
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + N` | Focus URL Input |
| `Ctrl + S` | Start Download |
| `Ctrl + O` | Open Downloads Folder |
| `Ctrl + H` | Switch to History Tab |
| `Ctrl + Q` | Quit Application |
| `F5` | Refresh Active Tab |
| `Esc` | Exit Video Preview Fullscreen |

---

## 📂 Project Architecture

```
VideoDownloaderPython/
│
├── core/
│   ├── config.py             # User preferences & configuration persistence
│   ├── database.py           # SQLite download history database manager
│   ├── downloader.py         # yt-dlp download worker & thread orchestration
│   ├── events.py             # Event bus architecture
│   └── models.py             # Data models for downloads and queue items
│
├── gui/
│   ├── download_tab.py       # Main download & YouTube search interface
│   ├── history_tab.py        # Searchable download history & actions
│   ├── queue_tab.py          # Active queue manager with progress meters
│   ├── main_window.py        # CustomTkinter main application frame
│   ├── styles.py             # Themes, palettes, and styling tokens
│   └── video_preview_modal.py# Video preview launcher
│
├── utils/
│   ├── player_process.py     # Chromium WebView2 ad-free cinema player
│   ├── notifications.py      # Windows toast notifications
│   ├── presets.py            # Video & audio quality presets
│   ├── shortcuts.py          # Global keyboard shortcuts listener
│   └── validators.py         # URL and format validation helpers
│
├── main.py                   # Application entry point & dependency checks
├── requirements.txt          # Python dependencies
└── run.bat                   # Windows batch runner
```

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
