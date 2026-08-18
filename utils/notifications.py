"""
Windows toast notifications for download completion.
"""
import logging
from typing import Optional

try:
    from win10toast import ToastNotifier
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    logging.warning("win10toast not available - notifications disabled")


class NotificationManager:
    """Manage Windows toast notifications"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled and NOTIFICATIONS_AVAILABLE
        self.toaster = ToastNotifier() if NOTIFICATIONS_AVAILABLE else None
    
    def notify_download_complete(self, title: str, file_path: Optional[str] = None) -> None:
        """
        Show notification for completed download.
        
        Args:
            title: Download title
            file_path: Optional path to downloaded file
        """
        if not self.enabled or not self.toaster:
            return
        
        try:
            message = f"'{title}' has finished downloading"
            if file_path:
                message += f"\nSaved to: {file_path}"
            
            self.toaster.show_toast(
                "Download Complete",
                message,
                duration=5,
                threaded=True
            )
        except Exception as e:
            logging.error(f"Notification error: {e}")
    
    def notify_download_failed(self, title: str, error: str) -> None:
        """
        Show notification for failed download.
        
        Args:
            title: Download title
            error: Error message
        """
        if not self.enabled or not self.toaster:
            return
        
        try:
            message = f"'{title}' failed to download\nError: {error[:50]}"
            
            self.toaster.show_toast(
                "Download Failed",
                message,
                duration=5,
                threaded=True
            )
        except Exception as e:
            logging.error(f"Notification error: {e}")
    
    def notify_queue_complete(self, count: int) -> None:
        """
        Show notification when queue is complete.
        
        Args:
            count: Number of downloads completed
        """
        if not self.enabled or not self.toaster:
            return
        
        try:
            message = f"{count} download(s) completed successfully"
            
            self.toaster.show_toast(
                "Queue Complete",
                message,
                duration=3,
                threaded=True
            )
        except Exception as e:
            logging.error(f"Notification error: {e}")
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable notifications"""
        self.enabled = enabled and NOTIFICATIONS_AVAILABLE
