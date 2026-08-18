# Advanced Video/Audio Downloader

A powerful, feature-rich video and audio downloader with a modern GUI built with Python and yt-dlp.

## ✨ Features

### Core Features
- **Concurrent Downloads**: Download up to 3-5 videos simultaneously for faster batch processing
- **Multiple Format Support**: Download videos in various qualities (144p to 4K) or extract audio (MP3, M4A, WAV)
- **YouTube Search**: Built-in search functionality to find and download videos directly
- **Smart Queue Management**: Add multiple URLs, pause/resume, and track download progress in real-time
- **Download History**: Comprehensive history with search, filtering, and pagination powered by SQLite database
- **Format Presets**: Quick-select presets for common download scenarios (4K Video, High-Quality Music, etc.)

### User Interface
- **Modern Design**: Clean, intuitive interface with light and dark theme support
- **Drag & Drop**: Drop URLs directly into the application (coming soon)
- **Keyboard Shortcuts**: Speed up your workflow with comprehensive keyboard shortcuts
- **Activity Log**: Real-time logging of all download activities
- **System Notifications**: Get notified when downloads complete (Windows)
- **Progress Tracking**: See real-time progress, speed, and ETA for each download

### Advanced Features
- **Metadata Embedding**: Automatically embed thumbnails, metadata, and subtitles
- **Export/Import Queue**: Save and load download queues for later
- **Download Statistics**: Track total downloads, success rates, and popular channels
- **Playlist Support**: Download entire YouTube playlists
- **Custom Filename Templates**: Flexible filename formatting options
- **Error Recovery**: Automatic retry with exponential backoff for failed downloads

## 📦 Installation

### Requirements
- Python 3.8 or higher
- Windows 10/11 (for notifications)

### Setup

1. **Clone or download this repository**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

Required packages:
- `yt-dlp` - Core download functionality
- `static-ffmpeg` - Video/audio merging for high-quality downloads
- `win10toast` - Windows notifications (optional)

3. **Run the application**:
```bash
python main.py
```

The application will automatically check for missing dependencies and offer to install them.

## 🚀 Usage

### Basic Download
1. Launch the application
2. Go to the **Download** tab
3. Paste one or more URLs (one per line)
4. Select quality and format options
5. Click "Start Download & Add to Queue"

### Using Presets
1. Select a preset from the dropdown (e.g., "Music (MP3 High Quality)")
2. Click "Apply"
3. Paste URLs and download

### YouTube Search
1. Enter a search query in the **YouTube Search** section
2. Click "Search"
3. Select videos from results
4. Click "Add Selected" or "Download Selected"

### Managing Queue
1. Switch to the **Queue** tab
2. View active downloads with real-time progress
3. Use controls to pause/resume or remove items

### Viewing History
1. Switch to the **History** tab
2. Search or filter downloads
3. Double-click to play downloaded files
4. Right-click for more options (Open Folder, Delete, etc.)

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New download (focus URL input) |
| `Ctrl+O` | Open download folder |
| `Ctrl+H` | Show history tab |
| `Ctrl+S` | Start download |
| `Ctrl+Q` | Quit application |
| `F5` | Refresh |
| `Delete` | Remove selected from queue |

## 🛠️ Configuration

Settings are automatically saved in `~/.VideoDownloader/config.json`

Key settings:
- `concurrent_downloads`: Number of simultaneous downloads (default: 3)
- `download_path`: Default download location
- `theme`: UI theme ("light" or "dark")
- `notifications_enabled`: Enable/disable notifications
- `auto_retry`: Automatic retry on failure
- `max_retries`: Maximum retry attempts (default: 3)

## 📊 Project Structure

```
VideoDownloader/
├── core/                  # Core application logic
│   ├── events.py         # Event bus for component communication
│   ├── models.py         # Data models (DownloadItem, Queue, etc.)
│   ├── database.py       # SQLite database manager
│   ├── downloader.py     # Download engine with concurrent support
│   └── config.py         # Configuration management
├── gui/                   # User interface components
│   ├── main_window.py    # Main application window
│   ├── download_tab.py   # Download tab UI
│   ├── queue_tab.py      # Queue management UI
│   ├── history_tab.py    # History browsing UI
│   └── styles.py         # Theme and styling
├── utils/                 # Utility modules
│   ├── validators.py     # URL validation
│   ├── notifications.py  # System notifications
│   ├── shortcuts.py      # Keyboard shortcut management
│   └── presets.py        # Format presets
├── tests/                 # Unit tests
├── main.py               # Application entry point
└── requirements.txt      # Python dependencies
```

## 🧪 Testing

Run unit tests:
```bash
python -m pytest tests/
```

Or with unittest:
```bash
python -m unittest discover tests
```

## 🐛 Troubleshooting

### Downloads fail with "FFmpeg not found"
- The application uses `static-ffmpeg` which should install automatically
- If issues persist, restart the application after installation

### No notifications appear
- Ensure `win10toast` is installed: `pip install win10toast`
- Enable notifications in Settings

### High-quality videos download as audio only
- This happens when FFmpeg is unavailable
- Reinstall `static-ffmpeg`: `pip install--upgrade static-ffmpeg`

### Database errors
- Delete `~/.VideoDownloader/history.db` to reset history database
- Old JSON history will be automatically migrated on next launch

## 📝 Changelog

### Version 2.0 (Current)
- ✨ Complete architectural refactoring with modular design
- ✨ Concurrent download support (3-5 parallel)
- ✨ SQLite database for efficient history management
- ✨ Format presets for quick configuration
- ✨ Event-driven architecture for better performance
- ✨ Enhanced error handling and retry logic
- ✨ Keyboard shortcuts and system notifications
- ✨ Export/Import queue functionality
- ✨ Search and filter in history
- 🐛 Fixed queue tree update bug
- 🐛 Improved memory management

### Version 1.0
- Initial release with basic download functionality

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

This project is provided as-is for personal use.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Powerful video downloader
- [static-ffmpeg](https://github.com/zackees/static-ffmpeg) - FFmpeg binaries
- [win10toast](https://github.com/jithurjacob/Windows-10-Toast-Notifications) - Windows notifications

## 📧 Support

For issues and questions, please use the GitHub issue tracker.

---

**Note**: This application is for personal use only. Please respect copyright laws and terms of service of the websites you download from.
"# YT_bang" 
