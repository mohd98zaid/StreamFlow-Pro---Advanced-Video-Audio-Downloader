import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from typing import Optional, Dict, Any
import os
import logging
from datetime import datetime

from core import (
    Event, EventBus, DownloadItem, ConfigManager, 
    DatabaseManager, DownloadStatus
)
from core.downloader import Downloader
from gui.styles import StyleManager
from gui.download_tab import DownloadTab
from gui.queue_tab import QueueTab
from gui.history_tab import HistoryTab
from utils import ShortcutManager, NotificationManager, PresetManager


class AdvancedDownloaderApp:
    """Main application window built with CustomTkinter"""
    
    def __init__(self, root: ctk.CTk):
        self.root = root
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.event_bus = EventBus()
        self.database = DatabaseManager()
        self.style_manager = StyleManager(self.config_manager.get("theme", "dark"))
        self.shortcut_manager = ShortcutManager()
        self.notification_manager = NotificationManager(
            self.config_manager.get("notifications_enabled", True)
        )
        self.preset_manager = PresetManager()
        
        # Initialize downloader with dependency injection
        self.downloader = Downloader(
            self.config_manager,
            self.event_bus,
            self.database
        )
        
        # UI components
        self.tabview: Optional[ctk.CTkTabview] = None
        self.download_tab: Optional[DownloadTab] = None
        self.queue_tab: Optional[QueueTab] = None
        self.history_tab: Optional[HistoryTab] = None
        self.status_label: Optional[ctk.CTkLabel] = None
        
        # Setup
        self.setup_window()
        self.subscribe_to_events()
        self.create_menu()
        self.create_widgets()
        self.setup_shortcuts()
        self.apply_window_settings()
        
        # Start downloader
        self.downloader.start_queue_processor()
        
        logging.info("Application initialized successfully with CustomTkinter")
    
    def setup_window(self) -> None:
        """Setup main window"""
        self.root.title("StreamFlow Pro - High Performance Downloader")
        window_size = self.config_manager.get("window_size", "1150x800")
        self.root.geometry(window_size)
        self.root.minsize(980, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def subscribe_to_events(self) -> None:
        """Subscribe to event bus events"""
        self.event_bus.subscribe(Event.DOWNLOAD_STARTED, self.on_download_started)
        self.event_bus.subscribe(Event.DOWNLOAD_PROGRESS, self.on_download_progress)
        self.event_bus.subscribe(Event.DOWNLOAD_COMPLETED, self.on_download_completed)
        self.event_bus.subscribe(Event.DOWNLOAD_FAILED, self.on_download_failed)
        self.event_bus.subscribe(Event.QUEUE_UPDATED, self.on_queue_updated)
        self.event_bus.subscribe(Event.LOG_MESSAGE, self.on_log_message)
        self.event_bus.subscribe(Event.STATUS_MESSAGE, self.on_status_message)
    
    def create_menu(self) -> None:
        """Create application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Download", command=self.focus_download_tab, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Folder", command=self.open_download_folder, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Export Queue", command=self.export_queue)
        file_menu.add_command(label="Import Queue", command=self.import_queue)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing, accelerator="Ctrl+Q")
        
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Download Center", command=lambda: self.tabview.set("Download Center"))
        view_menu.add_command(label="Active Queue", command=lambda: self.tabview.set("Active Queue"))
        view_menu.add_command(label="History Log", command=lambda: self.tabview.set("History Log"), accelerator="Ctrl+H")
        view_menu.add_separator()
        view_menu.add_command(label="Light Theme", command=lambda: self.change_theme("light"))
        view_menu.add_command(label="Dark Theme", command=lambda: self.change_theme("dark"))
        view_menu.add_separator()
        view_menu.add_command(label="Refresh", command=self.refresh_all, accelerator="F5")
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Clear Completed", command=self.clear_completed)
        tools_menu.add_command(label="Clear History", command=lambda: self.history_tab.clear_history() if self.history_tab else None)
        tools_menu.add_separator()
        tools_menu.add_command(label="Settings", command=self.open_settings)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts_help)
        help_menu.add_command(label="About", command=self.show_about)
    
    def create_widgets(self) -> None:
        """Create main application widgets with CustomTkinter layout"""
        # Modern Header Banner (CTkFrame)
        self.header_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color=("#F1F5F9", "#151D2A"), height=60)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)
        
        # Left Title Box
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side=tk.LEFT, fill=tk.Y, padx=18, pady=10)
        
        title_label = ctk.CTkLabel(
            title_box,
            text="StreamFlow Pro",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=("#2563EB", "#60A5FA")
        )
        title_label.pack(anchor="w")
        
        sub_label = ctk.CTkLabel(
            title_box,
            text="Next-Gen Multi-Threaded Media Downloader",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray50", "gray65")
        )
        sub_label.pack(anchor="w")
        
        # Right Header Actions
        header_actions = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        header_actions.pack(side=tk.RIGHT, fill=tk.Y, padx=18, pady=10)
        
        # Theme Switcher
        is_dark = self.style_manager.theme == "dark"
        self.theme_switch = ctk.CTkSwitch(
            header_actions,
            text="Dark Mode",
            command=self.on_switch_theme,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        if is_dark:
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
        self.theme_switch.pack(side=tk.RIGHT, padx=10)
        
        # Settings Button
        self.settings_btn = ctk.CTkButton(
            header_actions,
            text="Settings",
            width=90,
            height=32,
            fg_color=("gray85", "#334155"),
            hover_color=("gray75", "#475569"),
            text_color=("gray10", "#F8FAFC"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.open_settings
        )
        self.settings_btn.pack(side=tk.RIGHT, padx=6)
        
        # Open Downloads Button
        self.folder_btn = ctk.CTkButton(
            header_actions,
            text="Downloads Folder",
            width=130,
            height=32,
            fg_color=("gray85", "#334155"),
            hover_color=("gray75", "#475569"),
            text_color=("gray10", "#F8FAFC"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.open_download_folder
        )
        self.folder_btn.pack(side=tk.RIGHT, padx=6)

        # Load YouTube 2017 icon
        yt_icon_img = None
        try:
            from PIL import Image
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "youtube_icon.png")
            if os.path.exists(icon_path):
                pil_img = Image.open(icon_path)
                yt_icon_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(22, 15))
        except Exception as e:
            logging.warning(f"Could not load YouTube icon: {e}")

        # Open YouTube Button with 2017 Brand Logo
        self.youtube_btn = ctk.CTkButton(
            header_actions,
            text=" YouTube",
            image=yt_icon_img,
            compound="left",
            width=120,
            height=32,
            fg_color=("#FF0000", "#FF0000"),
            hover_color=("#CC0000", "#CC0000"),
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.open_youtube_browser
        )
        self.youtube_btn.pack(side=tk.RIGHT, padx=6)



        # Main Segmented TabView (CTkTabview) with high-contrast font styling
        self.tabview = ctk.CTkTabview(
            self.root,
            corner_radius=12,
            command=self.on_tab_changed,
            segmented_button_fg_color=("#E2E8F0", "#1E293B"),
            segmented_button_selected_color=("#2563EB", "#3B82F6"),
            segmented_button_selected_hover_color=("#1D4ED8", "#2563EB"),
            segmented_button_unselected_color=("#E2E8F0", "#1E293B"),
            segmented_button_unselected_hover_color=("#CBD5E1", "#334155"),
            text_color=("#0F172A", "#F8FAFC")
        )
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 8))
        
        # Create Tab Frames
        tab1_frame = self.tabview.add("Download Center")
        tab2_frame = self.tabview.add("Active Queue")
        tab3_frame = self.tabview.add("History Log")
        
        self.download_tab = DownloadTab(
            tab1_frame,
            self.downloader,
            self.config_manager,
            self.event_bus,
            self.preset_manager
        )
        
        self.queue_tab = QueueTab(
            tab2_frame,
            self.downloader,
            self.event_bus
        )
        
        self.history_tab = HistoryTab(
            tab3_frame,
            self.database,
            self.event_bus
        )
        
        # Apply high-contrast button font styling
        self.update_tab_button_colors()
        
        # Status Bar Footer
        status_frame = ctk.CTkFrame(self.root, corner_radius=0, height=30, fg_color=("gray90", "#1E293B"))
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Engine Ready",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#334155", "#94A3B8"),
            anchor="w"
        )
        self.status_label.pack(side=tk.LEFT, padx=16, pady=4)

    def on_tab_changed(self, selected_tab: str = None) -> None:
        """Handle tab selection change and update button text colors"""
        self.update_tab_button_colors()

    def update_tab_button_colors(self) -> None:
        """Ensure active tab has white text and unselected tabs have high-contrast dark/light text"""
        try:
            current = self.tabview.get()
            sb = getattr(self.tabview, '_segmented_button', None)
            if sb and hasattr(sb, '_buttons_dict'):
                for name, btn in sb._buttons_dict.items():
                    if name == current:
                        btn.configure(text_color="#FFFFFF")
                    else:
                        btn.configure(text_color=("#0F172A", "#F8FAFC"))
        except Exception:
            pass

    def on_switch_theme(self) -> None:
        """Handle theme switch toggle"""
        mode = "dark" if self.theme_switch.get() == 1 else "light"
        self.change_theme(mode)

    def change_theme(self, theme: str) -> None:
        """Change application theme live"""
        self.config_manager.set("theme", theme)
        self.style_manager.apply_theme(theme)
        
        if hasattr(self, 'theme_switch'):
            if theme == "dark":
                self.theme_switch.select()
            else:
                self.theme_switch.deselect()

        self.update_tab_button_colors()

        if self.download_tab and hasattr(self.download_tab, 'apply_theme'):
            self.download_tab.apply_theme()
        if self.queue_tab:
            self.queue_tab.refresh()
        if self.history_tab:
            self.history_tab.refresh()

    def setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts"""
        self.shortcut_manager.register(
            '<Control-n>',
            self.focus_download_tab,
            "New download"
        )
        self.shortcut_manager.register(
            '<Control-o>',
            self.open_download_folder,
            "Open download folder"
        )
        self.shortcut_manager.register(
            '<Control-q>',
            self.on_closing,
            "Quit application"
        )
        self.shortcut_manager.register(
            '<Control-h>',
            lambda: self.tabview.set("History Log"),
            "Show history"
        )
        self.shortcut_manager.register(
            '<F5>',
            self.refresh_all,
            "Refresh"
        )
        self.shortcut_manager.register(
            '<Delete>',
            lambda: self.queue_tab.remove_selected() if self.queue_tab else None,
            "Remove selected from queue"
        )
        
        # Bind shortcuts to root window
        self.shortcut_manager.bind_to_widget(self.root)
    
    def apply_window_settings(self) -> None:
        """Apply saved window position and size"""
        try:
            pos = self.config_manager.get("last_position", "+100+100")
            size = self.config_manager.get("window_size", "1150x800")
            self.root.geometry(f"{size}{pos}")
        except:
            pass
    
    # Event handlers
    def on_download_started(self, item: DownloadItem) -> None:
        """Handle download started event"""
        if hasattr(self, 'status_label') and self.status_label:
            self.root.after(0, lambda: self.status_label.configure(text=f"Downloading: {item.title}"))
    
    def on_download_progress(self, item: DownloadItem) -> None:
        """Handle download progress event"""
        pass
    
    def on_download_completed(self, item: DownloadItem) -> None:
        """Handle download completed event"""
        if hasattr(self, 'status_label') and self.status_label:
            self.root.after(0, lambda: self.status_label.configure(text=f"Completed: {item.title}"))
        
        # Show notification
        if self.notification_manager.enabled:
            self.notification_manager.notify_download_complete(item.title, item.file_path)
        
        # Refresh history
        if self.history_tab:
            self.root.after(100, self.history_tab.refresh)
    
    def on_download_failed(self, item: DownloadItem) -> None:
        """Handle download failed event"""
        if hasattr(self, 'status_label') and self.status_label:
            self.root.after(0, lambda: self.status_label.configure(text=f"Failed: {item.title}"))
        
        # Show notification
        if self.notification_manager.enabled:
            self.notification_manager.notify_download_failed(item.title, item.error or "Unknown error")
    
    def on_queue_updated(self, data: Any) -> None:
        """Handle queue updated event"""
        pass
    
    def on_log_message(self, message: str) -> None:
        """Handle log message event"""
        pass
    
    def on_status_message(self, message: str) -> None:
        """Handle status message event"""
        if hasattr(self, 'status_label') and self.status_label:
            self.root.after(0, lambda: self.status_label.configure(text=message))
    
    # Actions
    def focus_download_tab(self) -> None:
        """Switch to download tab"""
        self.tabview.set("Download Center")
        if self.download_tab:
            self.download_tab.focus_url_input()
    
    def open_download_folder(self) -> None:
        """Open download folder in file explorer"""
        path = self.config_manager.get("download_path")
        if os.path.exists(path):
            try:
                os.startfile(path)
            except:
                import subprocess
                subprocess.Popen(['explorer', path])
        else:
            messagebox.showerror("Error", f"Download folder does not exist: {path}")
    
    def export_queue(self) -> None:
        """Export current queue to JSON file"""
        import json
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                with self.downloader.download_queue.lock:
                    items = [item.to_dict() for item in self.downloader.download_queue.items]
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(items, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Success", f"Exported {len(items)} items to queue")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export queue: {e}")
    
    def import_queue(self) -> None:
        """Import queue from JSON file"""
        import json
        
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    items_data = json.load(f)
                
                count = 0
                for item_data in items_data:
                    item = DownloadItem.from_dict(item_data)
                    self.downloader.download_queue.add(item)
                    count += 1
                
                self.event_bus.emit(Event.QUEUE_UPDATED, None)
                messagebox.showinfo("Success", f"Imported {count} items to queue")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import queue: {e}")
    
    def open_youtube_browser(self) -> None:
        """Directly open YouTube in the dedicated ad-free player browser"""
        try:
            from gui.video_preview_modal import open_ad_free_player
            open_ad_free_player("https://www.youtube.com", "YouTube Browser")
            self.on_log_message("🌐 Opened Ad-Free YouTube Browser")
        except Exception as e:
            logging.error(f"Failed to open YouTube browser: {e}")

    def clear_completed(self) -> None:

        """Clear completed downloads from queue"""
        count = self.downloader.download_queue.clear_completed()
        if count > 0:
            self.event_bus.emit(Event.QUEUE_UPDATED, None)
            messagebox.showinfo("Success", f"Removed {count} completed items")
        else:
            messagebox.showinfo("Info", "No completed items to remove")
    
    def refresh_all(self) -> None:
        """Refresh all tabs"""
        if self.queue_tab:
            self.queue_tab.refresh()
        if self.history_tab:
            self.history_tab.refresh()
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.configure(text="Refreshed all components")
    
    def open_settings(self) -> None:
        """Open settings modal dialog using CustomTkinter"""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("StreamFlow Settings")
        settings_window.geometry("520x420")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Header Box
        header = ctk.CTkFrame(settings_window, corner_radius=0, fg_color=("gray90", "#151D2A"))
        header.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(
            header,
            text="Application Settings",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 2))
        
        ctk.CTkLabel(
            header,
            text="Configure downloader behavior and queue preferences",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray65")
        ).pack(anchor="w", padx=20, pady=(0, 15))
        
        body = ctk.CTkFrame(settings_window, fg_color="transparent")
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Concurrent Downloads Card
        f1 = ctk.CTkFrame(body, corner_radius=10)
        f1.pack(fill=tk.X, pady=(0, 12), padx=5)
        
        f1_label = ctk.CTkLabel(f1, text="Concurrent Downloads Limit:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
        f1_label.pack(side=tk.LEFT, padx=14, pady=12)
        
        concurrent_var = tk.StringVar(value=str(self.config_manager.get("concurrent_downloads", 3)))
        concurrent_opt = ctk.CTkOptionMenu(
            f1,
            values=["1", "2", "3", "4", "5", "6", "8", "10"],
            variable=concurrent_var,
            width=80
        )
        concurrent_opt.pack(side=tk.RIGHT, padx=14, pady=12)
        
        # Save Folder Card
        f2 = ctk.CTkFrame(body, corner_radius=10)
        f2.pack(fill=tk.X, pady=(0, 12), padx=5)
        
        f2_label = ctk.CTkLabel(f2, text="Default Download Save Folder:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
        f2_label.pack(anchor="w", padx=14, pady=(12, 4))
        
        f2_sub = ctk.CTkFrame(f2, fg_color="transparent")
        f2_sub.pack(fill=tk.X, padx=14, pady=(0, 12))
        
        path_var = tk.StringVar(value=self.config_manager.get("download_path", ""))
        path_entry = ctk.CTkEntry(f2_sub, textvariable=path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        
        def browse_folder():
            folder = filedialog.askdirectory(initialdir=path_var.get())
            if folder:
                path_var.set(folder)
                
        ctk.CTkButton(f2_sub, text="Browse...", width=90, command=browse_folder).pack(side=tk.RIGHT)
        
        # Notifications Card
        f3 = ctk.CTkFrame(body, corner_radius=10)
        f3.pack(fill=tk.X, pady=(0, 12), padx=5)
        
        notif_var = tk.BooleanVar(value=self.config_manager.get("notifications_enabled", True))
        notif_switch = ctk.CTkSwitch(
            f3,
            text="Enable Desktop Notifications on Download Finish/Fail",
            variable=notif_var,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        notif_switch.pack(anchor="w", padx=14, pady=12)
        
        # Save / Cancel Buttons
        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        
        def save_settings():
            try:
                val = int(concurrent_var.get())
                self.config_manager.set("concurrent_downloads", val)
            except:
                pass
            self.config_manager.set("download_path", path_var.get())
            self.config_manager.set("notifications_enabled", notif_var.get())
            self.notification_manager.set_enabled(notif_var.get())
            
            if self.download_tab and hasattr(self.download_tab, 'path_entry') and self.download_tab.path_entry:
                self.download_tab.path_entry.delete(0, tk.END)
                self.download_tab.path_entry.insert(0, path_var.get())
            messagebox.showinfo("Success", "Settings saved successfully!")
            settings_window.destroy()
        
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color=("gray80", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            width=100,
            command=settings_window.destroy
        ).pack(side=tk.RIGHT, padx=6)
        
        ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            width=130,
            command=save_settings
        ).pack(side=tk.RIGHT, padx=6)
    
    def show_shortcuts_help(self) -> None:
        """Show keyboard shortcuts help"""
        help_text = self.shortcut_manager.get_shortcuts_help()
        messagebox.showinfo("Keyboard Shortcuts", help_text)
    
    def show_about(self) -> None:
        """Show about dialog"""
        about_text = """StreamFlow Video & Audio Downloader Pro
Version 3.0 (CustomTkinter Modern Edition)

Features:
• CustomTkinter High-DPI Desktop Interface
• Multi-threaded engine powered by yt-dlp & ffmpeg
• Quick presets (4K Ultra HD, Full HD, 320k Audio)
• Direct YouTube search with metadata preview
• Real-time queue dashboard & status matrix

Built with Python, CustomTkinter, yt-dlp."""
        messagebox.showinfo("About StreamFlow Pro", about_text)
    
    def on_closing(self) -> None:
        """Handle window closing"""
        if messagebox.askokcancel("Quit", "Are you sure you want to exit StreamFlow?"):
            try:
                self.config_manager.set("window_size", f"{self.root.winfo_width()}x{self.root.winfo_height()}")
                self.config_manager.set("last_position", f"+{self.root.winfo_x()}+{self.root.winfo_y()}")
            except:
                pass
            
            self.downloader.shutdown()
            self.root.destroy()

