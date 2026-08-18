"""
Enhanced downloader with concurrent download support and event-driven architecture.
"""
import threading
import time
import logging
import re
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, Dict, Any
import yt_dlp

from .models import DownloadItem, DownloadQueue, DownloadStatus
from .events import EventBus, Event
from .config import ConfigManager
from .database import DatabaseManager


class Downloader:
    """Enhanced downloader with concurrent downloads and event bus integration"""
    
    def __init__(self, config_manager: ConfigManager, event_bus: EventBus, 
                 database: DatabaseManager):
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.database = database
        self.download_queue = DownloadQueue()
        
        # Concurrent download settings
        self.max_concurrent = config_manager.get("concurrent_downloads", 3)
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent, 
                                          thread_name_prefix="Downloader")
        self.active_downloads: Dict[str, DownloadItem] = {}
        self.active_downloads_lock = threading.Lock()
        
        # Control flags
        self.stop_download = False
        self.running = True
        self.queue_processor_thread: Optional[threading.Thread] = None
        
        # Load history from database
        self.load_history()
        
        # Migrate from old JSON if needed
        if not self.config_manager.get("db_migration_done", False):
            self._migrate_from_json()
    
    def _migrate_from_json(self) -> None:
        """Migrate from old JSON history file"""
        try:
            old_history_file = Path.home() / ".VideoDownloader" / "history.json"
            if old_history_file.exists():
                count = self.database.migrate_from_json(old_history_file)
                self.log(f"Migrated {count} items from JSON to database")
                self.config_manager.set("db_migration_done", True)
        except Exception as e:
            logging.error(f"Migration error: {e}")
    
    def log(self, message: str) -> None:
        """Log message via event bus"""
        logging.info(message)
        self.event_bus.emit(Event.LOG_MESSAGE, message)
    
    def get_ydl_opts(self, item: DownloadItem) -> Dict[str, Any]:
        """Get yt-dlp options for download item"""
        ydl_opts = {
            'outtmpl': item.output_template,
            'progress_hooks': [lambda d: self.update_progress(d, item)],
            'postprocessor_hooks': [lambda d: self.postprocess_hook(d, item)],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'retries': 10,
            'fragment_retries': 10,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            },
        }

        
        # Rate limiting
        if item.options.get('limit_rate') and item.options.get('rate_limit'):
            rate_value = self.parse_rate_limit(item.options['rate_limit'])
            if rate_value:
                ydl_opts['ratelimit'] = rate_value
        
        # Audio downloads
        if item.download_type.lower() == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': item.options.get('format_type', 'mp3'),
                'preferredquality': '192',
            }]
            if item.options.get('embed_metadata'):
                ydl_opts['postprocessors'].append({'key': 'FFmpegMetadata'})
            if item.options.get('embed_thumbnail'):
                ydl_opts['writethumbnail'] = True
                ydl_opts['postprocessors'].append({'key': 'EmbedThumbnailPP'})
        
        # Video downloads
        else:
            quality_format_map = {
                'Best Available': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best',
                '2160p (4K)': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160][ext=mp4]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
                '2160p': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160][ext=mp4]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
                '1440p (2K)': 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440][ext=mp4]/bestvideo[height<=1440]+bestaudio/best[height<=1440]/best',
                '1440p': 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440][ext=mp4]/bestvideo[height<=1440]+bestaudio/best[height<=1440]/best',
                '1080p (Full HD)': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                '720p (HD)': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
                '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
                '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/bestvideo[height<=480]+bestaudio/best[height<=480]/best',
                '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/bestvideo[height<=360]+bestaudio/best[height<=360]/best',
                'Worst': 'worstvideo[ext=mp4]+bestaudio[ext=m4a]/worst[ext=mp4]/worstvideo+bestaudio/worst'
            }
            
            selected_quality = item.quality
            if selected_quality not in quality_format_map:
                match = re.search(r'(\d+p)', selected_quality)
                if match:
                    selected_quality = match.group(1)
            
            default_format = 'best[ext=mp4]/best'
            ydl_opts['format'] = quality_format_map.get(selected_quality, default_format)
            
            logging.info(f"Quality: {item.quality} -> Format: {ydl_opts['format']}")
            
            if item.options.get('embed_subtitles'):
                ydl_opts['writesubtitles'] = True
                ydl_opts['subtitleslangs'] = ['en']
        
        # Playlist handling
        if item.download_type.lower() == 'playlist':
            ydl_opts['noplaylist'] = False
            ydl_opts['extract_flat'] = False
        else:
            ydl_opts['noplaylist'] = True
        
        return ydl_opts

    def extract_playlist_items(self, item: DownloadItem) -> list:
        """Extract individual video items from a playlist URL with index prefixing (01_Title)"""
        import os
        url = item.url
        save_folder = os.path.dirname(item.output_template) if item.output_template else self.config_manager.get("download_path")
        if not save_folder:
            save_folder = self.config_manager.get("download_path")
            
        filename_pattern = os.path.basename(item.output_template) if item.output_template else "%(title)s.%(ext)s"
        # Ensure pattern includes %(title)s and %(ext)s
        if "%(title)s" not in filename_pattern:
            filename_pattern = "%(title)s.%(ext)s"
            
        self.log(f"🔍 Extracting playlist metadata: {url}...")
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            if not info:
                self.log(f"⚠️ Failed to extract playlist metadata: {url}")
                return [item]
                
            raw_entries = info.get('entries', [])
            entries = [e for e in raw_entries if e is not None]
            
            if not entries:
                self.log(f"⚠️ No videos found in playlist: {url}")
                return [item]
                
            # Create subfolder named after the playlist title
            playlist_title = info.get('title') or info.get('playlist_title') or 'Playlist'
            safe_folder_name = re.sub(r'[\\/*?:"<>|]', '_', playlist_title).strip()
            if not safe_folder_name:
                safe_folder_name = 'Playlist'
                
            playlist_save_folder = os.path.join(save_folder, safe_folder_name)
            self.log(f"📁 Created playlist folder: '{safe_folder_name}'")
            
            total_count = len(entries)
            pad_width = max(2, len(str(total_count)))
            self.log(f"✅ Extracted {total_count} video(s) from playlist. Expanding queue items...")
            
            expanded_items = []
            for idx, entry in enumerate(entries, start=1):
                prefix = f"{idx:0{pad_width}d}_"
                
                v_id = entry.get('id', '')
                v_url = entry.get('url') or entry.get('webpage_url')
                if not v_url and v_id:
                    v_url = f"https://www.youtube.com/watch?v={v_id}"
                if not v_url:
                    v_url = url
                    
                v_title = entry.get('title') or f"Video {idx}"
                prefixed_title = f"{prefix}{v_title}"
                
                output_template = os.path.join(playlist_save_folder, f"{prefix}{filename_pattern}")
                
                new_item = DownloadItem(
                    url=v_url,
                    download_type='audio' if item.download_type.lower() == 'audio' else 'video',
                    quality=item.quality,
                    options=dict(item.options),
                    output_template=output_template
                )
                new_item.title = prefixed_title
                expanded_items.append(new_item)
                
            return expanded_items
            
        except Exception as e:
            self.log(f"❌ Error expanding playlist: {e}")
            logging.error(f"Playlist extraction error: {e}", exc_info=True)
            return [item]
    
    def parse_rate_limit(self, rate_str: str) -> Optional[int]:
        """Parse rate limit string"""
        if not rate_str:
            return None
        rate_str = rate_str.strip().upper()
        multiplier = 1
        if rate_str.endswith('K'):
            multiplier = 1000
            rate_str = rate_str[:-1]
        elif rate_str.endswith('M'):
            multiplier = 1000000
            rate_str = rate_str[:-1]
        elif rate_str.endswith('G'):
            multiplier = 1000000000
            rate_str = rate_str[:-1]
        try:
            val = float(rate_str) * multiplier
            return int(val) if val > 0 else None
        except ValueError:
            return None
    
    def update_progress(self, d: Dict[str, Any], item: DownloadItem) -> None:
        """Update download progress"""
        try:
            if d['status'] == 'downloading':
                if '_percent_str' in d:
                    clean_percent = re.sub(r'\x1b\[[0-9;]*m', '', d['_percent_str']).strip()
                    percent_match = re.search(r'(\d+(?:\.\d+)?)', clean_percent)
                    if percent_match:
                        item.progress = float(percent_match.group(1))
                elif 'downloaded_bytes' in d and 'total_bytes' in d and d['total_bytes'] > 0:
                    item.progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                elif 'downloaded_bytes' in d and 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
                    item.progress = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                
                raw_speed = d.get('_speed_str', 'N/A')
                raw_eta = d.get('_eta_str', 'N/A')
                if isinstance(raw_speed, str):
                    item.speed = re.sub(r'\x1b\[[0-9;]*m', '', raw_speed).strip()
                if isinstance(raw_eta, str):
                    item.eta = re.sub(r'\x1b\[[0-9;]*m', '', raw_eta).strip()
                
                item.status = DownloadStatus.DOWNLOADING.value
                self.event_bus.emit(Event.DOWNLOAD_PROGRESS, item)
            
            elif d['status'] == 'finished':
                item.progress = 100
                item.status = DownloadStatus.PROCESSING.value
                if 'filename' in d:
                    item.file_path = d['filename']
                self.event_bus.emit(Event.DOWNLOAD_PROGRESS, item)
        except Exception as e:
            logging.error(f"Progress update error: {e}")
    
    def postprocess_hook(self, d: Dict[str, Any], item: DownloadItem) -> None:
        """Post-processing hook"""
        try:
            if d.get('status') == 'finished':
                final_path = d.get('filepath') or d.get('filename')
                if final_path:
                    item.file_path = final_path
                    # Get file size
                    try:
                        item.file_size = Path(final_path).stat().st_size
                    except:
                        pass
                elif 'info_dict' in d:
                    info = d['info_dict']
                    if 'filepath' in info:
                        item.file_path = info['filepath']
        except Exception as e:
            logging.error(f"Postprocess hook error: {e}")
    
    def download_item(self, item: DownloadItem) -> None:
        """Download a single item"""
        if item.cancelled:
            return
        
        # Add to active downloads
        with self.active_downloads_lock:
            self.active_downloads[item.id] = item
        
        try:
            item.status = DownloadStatus.DOWNLOADING.value
            self.log(f"Starting: {item.url}")
            self.event_bus.emit(Event.DOWNLOAD_STARTED, item)
            
            ydl_opts = self.get_ydl_opts(item)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if item.cancelled:
                    self._handle_cancellation(item)
                    return
                
                try:
                    info = ydl.extract_info(item.url, download=False)
                    item.title = info.get('title', 'Unknown')
                    item.channel = info.get('uploader') or info.get('channel')
                    item.duration = info.get('duration_string')
                    item.thumbnail_url = info.get('thumbnail')
                    self.event_bus.emit(Event.DOWNLOAD_PROGRESS, item)
                except Exception as e:
                    logging.warning(f"Info extraction failed: {e}")
                    item.title = "Unknown Title"
                
                if item.cancelled:
                    self._handle_cancellation(item)
                    return
                
                ydl.download([item.url])
            
            if not item.cancelled:
                item.status = DownloadStatus.COMPLETED.value
                item.progress = 100
                self.log(f"[OK] Completed: {item.title}")
                self.download_queue.move_to_history(item)
                self.database.add_download(item)
                self.event_bus.emit(Event.DOWNLOAD_COMPLETED, item)
        
        except yt_dlp.DownloadError as e:
            self._handle_error(item, str(e))
        except Exception as e:
            self._handle_error(item, str(e))
        finally:
            # Remove from active downloads
            with self.active_downloads_lock:
                self.active_downloads.pop(item.id, None)
            
            if not item.cancelled:
                self.event_bus.emit(Event.QUEUE_UPDATED, None)
    
    def _handle_cancellation(self, item: DownloadItem) -> None:
        """Handle download cancellation"""
        item.status = DownloadStatus.CANCELLED.value
        self.log(f"Cancelled: {item.url}")
        self.download_queue.move_to_history(item)
        self.database.add_download(item)
        self.event_bus.emit(Event.DOWNLOAD_CANCELLED, item)
    
    def _handle_error(self, item: DownloadItem, error_msg: str) -> None:
        """Handle download error with retry logic"""
        if item.cancelled:
            self._handle_cancellation(item)
            return
        
        item.error = error_msg
        if item.retry_count < item.max_retries:
            item.retry_count += 1
            item.status = f"Retry {item.retry_count}/{item.max_retries}"
            self.log(f"[RETRY] Error, retrying {item.retry_count}/{item.max_retries}: {item.title}")
            time.sleep(min(2 ** item.retry_count, 30))
            self.download_item(item)
        else:
            item.status = DownloadStatus.FAILED.value
            self.log(f"[FAILED] {item.title} - {error_msg}")
            self.download_queue.move_to_history(item)
            self.database.add_download(item)
            self.event_bus.emit(Event.DOWNLOAD_FAILED, item)
    
    def queue_processor(self) -> None:
        """Process download queue with concurrent downloads"""
        while self.running:
            try:
                if not self.stop_download:
                    # Check how many downloads are active
                    with self.active_downloads_lock:
                        active_count = len(self.active_downloads)
                    
                    # Start new downloads if under limit
                    while active_count < self.max_concurrent:
                        item = self.download_queue.get_next()
                        if item:
                            # Submit to thread pool
                            self.executor.submit(self.download_item, item)
                            active_count += 1
                        else:
                            break
                    
                    time.sleep(0.5)
                else:
                    time.sleep(1)
            except Exception as e:
                logging.error(f"Queue processor error: {e}")
                time.sleep(1)
    
    def start_queue_processor(self) -> None:
        """Start the queue processor"""
        if self.queue_processor_thread is None or not self.queue_processor_thread.is_alive():
            self.stop_download = False
            self.queue_processor_thread = threading.Thread(
                target=self.queue_processor, 
                daemon=True, 
                name="QueueProcessor"
            )
            self.queue_processor_thread.start()
            self.log("Queue processor started")
    
    def load_history(self) -> None:
        """Load history from database"""
        try:
            items = self.database.get_history(limit=1000)
            with self.download_queue.lock:
                self.download_queue.history = items
            self.log(f"Loaded {len(items)} history items from database")
        except Exception as e:
            logging.error(f"Error loading history: {e}")
    
    def shutdown(self) -> None:
        """Shutdown downloader gracefully"""
        self.running = False
        self.stop_download = True
        self.executor.shutdown(wait=True)
        self.database.close()
        self.log("Downloader shutdown complete")
