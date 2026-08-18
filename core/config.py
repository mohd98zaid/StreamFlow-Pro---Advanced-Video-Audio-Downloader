import json
import logging
from pathlib import Path
import os

class ConfigManager:
    """Manage application configuration"""
    def __init__(self):
        # improvement: Store config in a dedicated folder
        self.app_data_dir = Path.home() / ".VideoDownloader"
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.app_data_dir / "config.json"
        
        self.default_config = {
            "download_path": str(Path.home() / "Downloads"),
            "theme": "dark",
            "window_size": "1150x800",
            "last_position": "+100+100",
            "auto_retry": True,
            "max_retries": 3,
            "embed_thumbnail": True,
            "embed_metadata": True,
            "embed_subtitles": False,
            "last_download_type": "Video",
            "last_quality": "1080p (Full HD)",
            "last_format_type": "mp4",
            # New features
            "concurrent_downloads": 3,
            "notifications_enabled": True,
            "taskbar_progress": True,
            "system_tray": False,
            "auto_update_check": True,
            "last_preset": "Default",
            "show_statistics": True,
            "db_migration_done": False
        }

        self.config = self.load_config()

    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    merged = self.default_config.copy()
                    merged.update(config)
                    return merged
            return self.default_config.copy()
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return self.default_config.copy()

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
