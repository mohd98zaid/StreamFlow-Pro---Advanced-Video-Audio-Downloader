"""
Keyboard shortcut definitions and management.
"""
from typing import Dict, Callable
import logging


class ShortcutManager:
    """Manage application keyboard shortcuts"""
    
    def __init__(self):
        self.shortcuts: Dict[str, Callable] = {}
    
    def register(self, key_binding: str, callback: Callable, description: str = "") -> None:
        """
        Register a keyboard shortcut.
        
        Args:
            key_binding: Key binding string (e.g., '<Control-v>')
            callback: Function to call when shortcut is triggered
            description: Optional description of what the shortcut does
        """
        self.shortcuts[key_binding] = {
            'callback': callback,
            'description': description
        }
        logging.debug(f"Registered shortcut: {key_binding} - {description}")
    
    def bind_to_widget(self, widget) -> None:
        """
        Bind all registered shortcuts to a widget.
        
        Args:
            widget: Tkinter widget to bind shortcuts to
        """
        for key_binding, data in self.shortcuts.items():
            widget.bind(key_binding, lambda e, cb=data['callback']: cb())
    
    def get_shortcuts_help(self) -> str:
        """Get help text describing all shortcuts"""
        lines = ["Keyboard Shortcuts:", ""]
        for key_binding, data in self.shortcuts.items():
            if data['description']:
                # Format key binding for display
                display_key = key_binding.replace('<', '').replace('>', '').replace('Control', 'Ctrl')
                lines.append(f"  {display_key}: {data['description']}")
        return '\n'.join(lines)


# Default shortcut definitions
DEFAULT_SHORTCUTS = {
    '<Control-v>': 'Paste from clipboard',
    '<Control-s>': 'Start download',
    '<Control-q>': 'Quit application',
    '<Delete>': 'Remove selected item',
    '<Control-o>': 'Open download folder',
    '<Control-h>': 'Show download history',
    '<Control-n>': 'New download',
    '<F5>': 'Refresh',
    '<Control-w>': 'Close window',
    '<Control-comma>': 'Open settings',
    '<Escape>': 'Cancel/Close dialog',
}
