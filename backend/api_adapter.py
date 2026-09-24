"""
StreamFlow Pro - Backend API Adapter
Translates existing Python core classes (Downloader, EventBus, DatabaseManager, ConfigManager)
into clean, structured, frontend-friendly operations and data models.
"""
import os
import sys
import time
import logging
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional

import yt_dlp

# Add root directory to sys.path to ensure core and utils are importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import ConfigManager
from core.events import EventBus, Event
from core.database import DatabaseManager
from core.models import DownloadItem, DownloadStatus
from core.downloader import Downloader
from utils.presets import PresetManager
from utils.validators import validate_url, validate_multiple_urls, is_supported_site, extract_video_id
from utils.notifications import NotificationManager


class BackendApiAdapter:
    """High-level adapter wrapping all StreamFlow Pro core engine components."""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.event_bus = EventBus()
        self.database = DatabaseManager()
        self.preset_manager = PresetManager()
        self.notification_manager = NotificationManager(
            self.config_manager.get("notifications_enabled", True)
        )

        self.downloader = Downloader(
            self.config_manager,
            self.event_bus,
            self.database
        )

        # Hook notification manager to events
        self.event_bus.subscribe(Event.DOWNLOAD_COMPLETED, self._on_download_completed)
        self.event_bus.subscribe(Event.DOWNLOAD_FAILED, self._on_download_failed)

        # Start background queue processor
        self.downloader.start_queue_processor()
        logging.info("BackendApiAdapter initialized successfully.")

    def _on_download_completed(self, item: DownloadItem):
        if self.notification_manager.enabled:
            self.notification_manager.notify_download_complete(item.title, item.file_path)

    def _on_download_failed(self, item: DownloadItem):
        if self.notification_manager.enabled:
            self.notification_manager.notify_download_failed(item.title, item.error or "Download failed")

    # --------------------------------------------------------------------------
    # CONFIGURATION & PRESETS
    # --------------------------------------------------------------------------
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration dictionary."""
        return self.config_manager.config.copy()

    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration keys and persist to disk."""
        for key, val in new_config.items():
            self.config_manager.set(key, val)

        if "notifications_enabled" in new_config:
            self.notification_manager.set_enabled(new_config["notifications_enabled"])

        if "concurrent_downloads" in new_config:
            try:
                concurrency = int(new_config["concurrent_downloads"])
                self.downloader.max_concurrent = concurrency
            except Exception as e:
                logging.error(f"Error setting concurrency: {e}")

        return self.get_config()

    def get_presets(self) -> List[Dict[str, Any]]:
        """Get list of all format presets formatted for the frontend."""
        presets = []
        for name in self.preset_manager.get_preset_names():
            p = self.preset_manager.get_preset(name)
            presets.append({
                "name": p.name,
                "download_type": p.download_type,
                "quality": p.quality,
                "format_type": p.format_type,
                "embed_thumbnail": p.embed_thumbnail,
                "embed_metadata": p.embed_metadata,
                "embed_subtitles": p.embed_subtitles,
            })
        return presets

    # --------------------------------------------------------------------------
    # URL VALIDATION & METADATA EXTRACTION
    # --------------------------------------------------------------------------
    def validate_input(self, text: str) -> Dict[str, Any]:
        """Validate single or multiple URLs from text input."""
        valid_urls, errors = validate_multiple_urls(text)
        detected_sites = []
        for u in valid_urls:
            is_supp, site_name = is_supported_site(u)
            detected_sites.append({"url": u, "site": site_name, "supported": is_supp})

        return {
            "valid_urls": valid_urls,
            "detected_sites": detected_sites,
            "errors": [{"url": e[0], "message": e[1]} for e in errors],
            "is_valid": len(valid_urls) > 0 and len(errors) == 0,
            "count": len(valid_urls),
        }

    def fetch_metadata(self, url: str) -> Dict[str, Any]:
        """Fast metadata extraction using yt-dlp without downloading."""
        is_val, err = validate_url(url)
        if not is_val:
            return {"success": False, "error": err}

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "ignoreerrors": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return {"success": False, "error": "Unable to extract media information"}

                duration = info.get("duration")
                if duration and isinstance(duration, (int, float)):
                    duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))
                    if duration_str.startswith("00:"):
                        duration_str = duration_str[3:]
                else:
                    duration_str = info.get("duration_string", "N/A")

                # Detect available qualities
                available_qualities = []
                formats = info.get("formats", [])
                heights = set()
                for f in formats:
                    h = f.get("height")
                    if h and isinstance(h, int) and h > 0 and h not in heights:
                        heights.add(h)
                for h in sorted(list(heights), reverse=True):
                    label = f"{h}p"
                    if h >= 2160:
                        label = "2160p (4K)"
                    elif h >= 1440:
                        label = "1440p (2K)"
                    elif h >= 1080:
                        label = "1080p (Full HD)"
                    elif h >= 720:
                        label = "720p (HD)"
                    available_qualities.append(label)

                if "Best Available" not in available_qualities:
                    available_qualities.insert(0, "Best Available")

                return {
                    "success": True,
                    "url": url,
                    "title": info.get("title", "Unknown Title"),
                    "uploader": info.get("uploader") or info.get("channel") or "Unknown Channel",
                    "duration": duration,
                    "duration_str": duration_str,
                    "thumbnail": info.get("thumbnail"),
                    "view_count": info.get("view_count"),
                    "is_playlist": info.get("_type") == "playlist" or "entries" in info,
                    "playlist_count": len(info.get("entries", [])) if "entries" in info else 1,
                    "available_qualities": available_qualities,
                }
        except Exception as e:
            logging.error(f"Metadata extraction error for {url}: {e}")
            return {"success": False, "error": str(e)}

    # --------------------------------------------------------------------------
    # DOWNLOAD & QUEUE OPERATIONS
    # --------------------------------------------------------------------------
    def add_downloads(
        self,
        urls: List[str],
        download_type: str = "video",
        quality: str = "1080p (Full HD)",
        format_type: str = "mp4",
        options: Optional[Dict[str, Any]] = None,
        save_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add one or more URLs to the download queue."""
        if not urls:
            return {"success": False, "error": "No URLs provided"}

        opts = options.copy() if options else {}
        opts.setdefault("embed_thumbnail", self.config_manager.get("embed_thumbnail", True))
        opts.setdefault("embed_metadata", self.config_manager.get("embed_metadata", True))
        opts.setdefault("embed_subtitles", self.config_manager.get("embed_subtitles", False))
        opts.setdefault("format_type", format_type.lower())

        target_dir = save_path or self.config_manager.get("download_path", str(Path.home() / "Downloads"))
        filename_pattern = self.config_manager.get("filename_pattern", "%(title)s.%(ext)s")
        template = os.path.join(target_dir, filename_pattern)

        items_to_add: List[DownloadItem] = []

        for u in urls:
            u_clean = u.strip()
            if not u_clean:
                continue

            base_item = DownloadItem(
                url=u_clean,
                download_type=download_type.lower(),
                quality=quality,
                options=opts,
                output_template=template
            )

            # Check if this is a playlist
            if download_type.lower() == "playlist" or "list=" in u_clean.lower():
                self.event_bus.emit(Event.STATUS_MESSAGE, f"Extracting playlist: {u_clean}")
                expanded = self.downloader.extract_playlist_items(base_item)
                items_to_add.extend(expanded)
            else:
                items_to_add.append(base_item)

        added_items = []
        duplicate_count = 0

        for item in items_to_add:
            if self.downloader.download_queue.add(item):
                added_items.append(self._item_to_dict(item))
            else:
                duplicate_count += 1

        self.event_bus.emit(Event.QUEUE_UPDATED, None)
        self.downloader.start_queue_processor()

        return {
            "success": True,
            "added_count": len(added_items),
            "duplicate_count": duplicate_count,
            "items": added_items,
        }

    def get_queue(self) -> Dict[str, Any]:
        """Get snapshot of current download queue."""
        with self.downloader.download_queue.lock:
            items = [self._item_to_dict(item) for item in self.downloader.download_queue.items]

        # Calculate metrics summary
        active = sum(1 for i in items if i["status"] in ["Downloading", "Processing"])
        queued = sum(1 for i in items if i["status"] == "Queued")
        paused = sum(1 for i in items if i["status"] == "Paused")
        completed = sum(1 for i in items if i["status"] == "Completed")
        failed = sum(1 for i in items if i["status"] == "Failed")

        return {
            "items": items,
            "summary": {
                "total": len(items),
                "active": active,
                "queued": queued,
                "paused": paused,
                "completed": completed,
                "failed": failed,
            }
        }

    def pause_item(self, item_id: str) -> bool:
        """Pause a specific download item."""
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.id == item_id:
                    item.paused = True
                    item.status = DownloadStatus.PAUSED.value
                    item.speed = "Paused"
                    self.event_bus.emit(Event.DOWNLOAD_PROGRESS, item)
                    self.event_bus.emit(Event.QUEUE_UPDATED, None)
                    return True
        return False

    def resume_item(self, item_id: str) -> bool:
        """Resume a paused download item."""
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.id == item_id:
                    item.paused = False
                    item.status = DownloadStatus.QUEUED.value
                    item.speed = "Queued"
                    self.event_bus.emit(Event.DOWNLOAD_PROGRESS, item)
                    self.event_bus.emit(Event.QUEUE_UPDATED, None)
                    self.downloader.start_queue_processor()
                    return True
        return False

    def cancel_item(self, item_id: str) -> bool:
        """Cancel a download item."""
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.id == item_id:
                    item.cancelled = True
                    item.status = DownloadStatus.CANCELLED.value
                    self.event_bus.emit(Event.QUEUE_UPDATED, None)
                    return True
        return False

    def retry_item(self, item_id: str) -> bool:
        """Retry a failed or cancelled item."""
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.id == item_id:
                    item.retry_count = 0
                    item.error = None
                    item.status = DownloadStatus.QUEUED.value
                    item.paused = False
                    item.cancelled = False
                    self.event_bus.emit(Event.QUEUE_UPDATED, None)
                    self.downloader.start_queue_processor()
                    return True
        return False

    def pause_all(self) -> int:
        """Pause all queued or downloading items."""
        count = 0
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.status in [DownloadStatus.QUEUED.value, DownloadStatus.DOWNLOADING.value]:
                    item.paused = True
                    item.status = DownloadStatus.PAUSED.value
                    item.speed = "Paused"
                    count += 1
        self.event_bus.emit(Event.QUEUE_UPDATED, None)
        return count

    def resume_all(self) -> int:
        """Resume all paused items."""
        count = 0
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.status == DownloadStatus.PAUSED.value:
                    item.paused = False
                    item.status = DownloadStatus.QUEUED.value
                    count += 1
        self.event_bus.emit(Event.QUEUE_UPDATED, None)
        self.downloader.start_queue_processor()
        return count

    def clear_completed(self) -> int:
        """Remove completed and cancelled items from queue."""
        count = self.downloader.download_queue.clear_completed()
        self.event_bus.emit(Event.QUEUE_UPDATED, None)
        return count

    def remove_item(self, item_id: str) -> bool:
        """Remove an item completely from queue."""
        with self.downloader.download_queue.lock:
            target = None
            for item in self.downloader.download_queue.items:
                if item.id == item_id:
                    target = item
                    break
            if target:
                target.cancelled = True
                self.downloader.download_queue.items.remove(target)
                self.event_bus.emit(Event.QUEUE_UPDATED, None)
                return True
        return False

    # --------------------------------------------------------------------------
    # HISTORY & STATS
    # --------------------------------------------------------------------------
    def get_history(
        self,
        search_query: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Fetch download history from SQLite database with pagination and search."""
        items = self.database.get_history(
            limit=limit,
            offset=offset,
            status_filter=status_filter if status_filter and status_filter.lower() != "all" else None,
            search_query=search_query if search_query else None
        )
        return {
            "items": [self._item_to_dict(it) for it in items],
            "count": len(items),
            "limit": limit,
            "offset": offset,
        }

    def delete_history_item(self, item_id: str) -> bool:
        """Delete specific record from history database."""
        success = self.database.delete_download(item_id)
        if success:
            self.event_bus.emit(Event.HISTORY_UPDATED, None)
        return success

    def clear_history(self) -> bool:
        """Clear all historical download entries."""
        success = self.database.clear_history()
        if success:
            self.event_bus.emit(Event.HISTORY_UPDATED, None)
        return success

    def get_statistics(self) -> Dict[str, Any]:
        """Retrieve aggregated download statistics."""
        stats = self.database.get_statistics()
        return {
            "total_downloads": stats.total_downloads,
            "successful_downloads": stats.successful_downloads,
            "failed_downloads": stats.failed_downloads,
            "total_size_bytes": stats.total_size_bytes,
            "total_size_formatted": stats.get_total_size_formatted(),
            "success_rate": stats.get_success_rate(),
            "channels": stats.channels,
            "categories": stats.categories,
        }

    # --------------------------------------------------------------------------
    # YOUTUBE SEARCH
    # --------------------------------------------------------------------------
    def search_youtube(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Perform fast YouTube search using yt-dlp."""
        if not query or not query.strip():
            return []

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query.strip()}", download=False)
                if not info:
                    return []

                raw_entries = info.get("entries", [])
                results = []

                for entry in raw_entries:
                    if not entry:
                        continue
                    v_id = entry.get("id", "")
                    url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={v_id}"
                    
                    # Duration formatting
                    dur = entry.get("duration")
                    dur_str = time.strftime("%H:%M:%S", time.gmtime(dur)) if isinstance(dur, (int, float)) else "N/A"
                    if dur_str.startswith("00:"):
                        dur_str = dur_str[3:]

                    # Views formatting
                    views = entry.get("view_count")
                    views_str = f"{views:,}" if isinstance(views, int) else "N/A"

                    results.append({
                        "id": v_id,
                        "title": entry.get("title", "Unknown Title"),
                        "channel": entry.get("uploader") or entry.get("channel") or "Unknown Channel",
                        "url": url,
                        "duration": dur,
                        "duration_str": dur_str,
                        "views": views,
                        "views_str": views_str,
                        "thumbnail": f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg" if v_id else None,
                    })

                return results
        except Exception as e:
            logging.error(f"YouTube search error for query '{query}': {e}")
            return []

    # --------------------------------------------------------------------------
    # MEDIA & FILE SYSTEM ACTIONS
    # --------------------------------------------------------------------------
    def open_file(self, file_path: str) -> Dict[str, Any]:
        """Open a downloaded file with Windows default media player."""
        if not file_path or not os.path.exists(file_path):
            return {"success": False, "error": f"File does not exist: {file_path}"}
        try:
            os.startfile(file_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_folder(self, folder_or_file_path: Optional[str] = None) -> Dict[str, Any]:
        """Reveal file in Explorer or open destination directory."""
        path = folder_or_file_path or self.config_manager.get("download_path")
        if not path:
            path = str(Path.home() / "Downloads")

        if os.path.isfile(path):
            # Select file in Explorer
            import subprocess
            subprocess.Popen(f'explorer /select,"{path}"')
            return {"success": True}
        elif os.path.isdir(path):
            try:
                os.startfile(path)
                return {"success": True}
            except Exception:
                import subprocess
                subprocess.Popen(["explorer", path])
                return {"success": True}
        else:
            return {"success": False, "error": f"Path not found: {path}"}

    def launch_player(self, video_id: str, title: str = "Video Preview") -> Dict[str, Any]:
        """Launch the ad-free player or Yuma Studio via player_process."""
        try:
            player_script = os.path.join(ROOT_DIR, "utils", "player_process.py")
            if os.path.exists(player_script):
                import subprocess
                subprocess.Popen([sys.executable, player_script, video_id, title])
                return {"success": True}
            else:
                return {"success": False, "error": "Player process script not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --------------------------------------------------------------------------
    # SERIALIZATION HELPERS
    # --------------------------------------------------------------------------
    def _item_to_dict(self, item: DownloadItem) -> Dict[str, Any]:
        """Convert DownloadItem instance to frontend-friendly JSON structure."""
        return {
            "id": item.id,
            "url": item.url,
            "title": item.title,
            "download_type": item.download_type,
            "quality": item.quality,
            "status": item.status,
            "progress": round(item.progress, 1),
            "speed": item.speed or "N/A",
            "eta": item.eta or "N/A",
            "file_path": item.file_path,
            "file_size": item.file_size,
            "created_at": item.created_at,
            "completed_at": item.completed_at,
            "channel": item.channel,
            "duration": item.duration,
            "thumbnail_url": item.thumbnail_url or (
                f"https://img.youtube.com/vi/{extract_video_id(item.url)}/hqdefault.jpg"
                if extract_video_id(item.url) else None
            ),
            "error": item.error,
            "is_paused": getattr(item, "paused", False),
            "is_cancelled": getattr(item, "cancelled", False),
        }
