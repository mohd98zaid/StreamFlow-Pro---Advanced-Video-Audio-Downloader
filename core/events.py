"""
Event Bus implementation for decoupled communication between components.
"""
from enum import Enum
from typing import Callable, Dict, List, Any
import threading
import logging


class Event(Enum):
    """Download and application events"""
    DOWNLOAD_STARTED = "download_started"
    DOWNLOAD_PROGRESS = "download_progress"
    DOWNLOAD_COMPLETED = "download_completed"
    DOWNLOAD_FAILED = "download_failed"
    DOWNLOAD_PAUSED = "download_paused"
    DOWNLOAD_RESUMED = "download_resumed"
    DOWNLOAD_CANCELLED = "download_cancelled"
    QUEUE_UPDATED = "queue_updated"
    HISTORY_UPDATED = "history_updated"
    STATUS_MESSAGE = "status_message"
    LOG_MESSAGE = "log_message"


class EventBus:
    """Thread-safe event bus for publish-subscribe pattern"""
    
    def __init__(self):
        self._listeners: Dict[Event, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def subscribe(self, event: Event, callback: Callable[[Any], None]) -> None:
        """
        Subscribe to an event with a callback function.
        
        Args:
            event: The event to subscribe to
            callback: Function to call when event is emitted
        """
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            if callback not in self._listeners[event]:
                self._listeners[event].append(callback)
                logging.debug(f"Subscribed to {event.value}")
    
    def unsubscribe(self, event: Event, callback: Callable[[Any], None]) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event: The event to unsubscribe from
            callback: The callback to remove
        """
        with self._lock:
            if event in self._listeners and callback in self._listeners[event]:
                self._listeners[event].remove(callback)
                logging.debug(f"Unsubscribed from {event.value}")
    
    def emit(self, event: Event, data: Any = None) -> None:
        """
        Emit an event to all subscribers.
        
        Args:
            event: The event to emit
            data: Optional data to pass to callbacks
        """
        with self._lock:
            listeners = self._listeners.get(event, []).copy()
        
        for callback in listeners:
            try:
                callback(data)
            except Exception as e:
                logging.error(f"Error in event handler for {event.value}: {e}")
    
    def clear(self, event: Event = None) -> None:
        """
        Clear all listeners for an event, or all events if None.
        
        Args:
            event: Specific event to clear, or None for all
        """
        with self._lock:
            if event:
                self._listeners[event] = []
            else:
                self._listeners.clear()
