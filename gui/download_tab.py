import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional
import threading
import time
import logging
import yt_dlp

from core import Event, EventBus, DownloadItem, ConfigManager
from core.downloader import Downloader
from utils import PresetManager, validate_url
from .video_preview_modal import open_ad_free_player




class DownloadTab:
    """Download tab UI component built with CustomTkinter"""
    
    def __init__(self, parent, downloader: Downloader, config: ConfigManager,
                 event_bus: EventBus, preset_manager: PresetManager):
        self.downloader = downloader
        self.config = config
        self.event_bus = event_bus
        self.preset_manager = preset_manager
        
        # Parent tab frame
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # UI variables
        self.url_text: Optional[ctk.CTkTextbox] = None
        self.log_text: Optional[ctk.CTkTextbox] = None
        self.download_type = tk.StringVar(value=self.config.get("last_download_type", "Video"))
        self.quality = tk.StringVar(value=self.config.get("last_quality", "1080p (Full HD)"))
        self.format_type = tk.StringVar(value=self.config.get("last_format_type", "mp4"))
        self.embed_thumbnail = tk.BooleanVar(value=self.config.get("embed_thumbnail", True))
        self.embed_metadata = tk.BooleanVar(value=self.config.get("embed_metadata", True))
        self.embed_subtitles = tk.BooleanVar(value=self.config.get("embed_subtitles", False))
        self.path_entry: Optional[ctk.CTkEntry] = None
        self.filename_template = tk.StringVar(value="%(title)s.%(ext)s")
        self.results_tree: Optional[ttk.Treeview] = None
        self.results_frame: Optional[ctk.CTkFrame] = None
        self.search_entry: Optional[ctk.CTkEntry] = None
        self.preset_var = tk.StringVar(value=self.config.get("last_preset", "Default"))
        
        # Trace preference changes to auto-save
        for var in (self.download_type, self.quality, self.format_type, 
                    self.embed_thumbnail, self.embed_metadata, self.embed_subtitles, self.preset_var):
            var.trace_add("write", self.save_user_preferences)
        
        # Subscription to events
        self.event_bus.subscribe(Event.LOG_MESSAGE, self.log_safe)
        
        # Build UI
        self.create_ui()

    
    def create_ui(self) -> None:
        """Create download tab UI with CustomTkinter card containers"""
        main_container = ctk.CTkFrame(self.frame, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(0, weight=1)
        
        # LEFT PANEL - Discovery & Activity Console
        left_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        # YouTube Search Card
        search_card = ctk.CTkFrame(left_panel, corner_radius=10)
        search_card.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(
            search_card,
            text="YouTube Search & Discovery",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        ).pack(anchor="w", padx=14, pady=(12, 6))
        
        search_input = ctk.CTkFrame(search_card, fg_color="transparent")
        search_input.pack(fill=tk.X, padx=14, pady=(0, 12))
        
        self.search_entry = ctk.CTkEntry(
            search_input,
            placeholder_text="Enter video title, artist, or keywords to search..."
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.search_entry.bind('<Return>', lambda e: self.search_youtube())
        
        ctk.CTkButton(
            search_input,
            text="Search",
            width=90,
            fg_color=("#2563EB", "#3B82F6"),
            command=self.search_youtube
        ).pack(side=tk.RIGHT)
        
        # Search Results Frame (Hidden until search returns)
        self.results_frame = ctk.CTkFrame(left_panel, corner_radius=10)
        self.results_frame.pack(fill=tk.X, pady=(0, 10))
        self.results_frame.pack_forget()
        
        tree_cont = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        tree_cont.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        
        columns = ("Title", "Channel", "Duration", "Views", "URL")
        self.results_tree = ttk.Treeview(tree_cont, columns=columns, show="headings", height=8)
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=80)
        self.results_tree.column("Title", width=220)
        self.results_tree.column("URL", width=0, stretch=tk.NO)
        
        vsb = ttk.Scrollbar(tree_cont, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.results_tree.bind("<Double-1>", lambda e: self.preview_selected_video())
        
        btn_frame = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        ctk.CTkButton(
            btn_frame,
            text="🎬 Preview Video (Ad-Free)",
            fg_color=("#059669", "#10B981"),
            command=self.preview_selected_video
        ).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(
            btn_frame,
            text="Add Selected to Queue",
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.add_selected_to_queue
        ).pack(side=tk.LEFT, padx=4)
        
        ctk.CTkButton(
            btn_frame,
            text="Download Selected Now",
            fg_color=("#2563EB", "#3B82F6"),
            command=self.download_selected_now
        ).pack(side=tk.LEFT, padx=4)

        
        # Activity Console Card (Bottom of left panel)
        log_card = ctk.CTkFrame(left_panel, corner_radius=10)
        log_card.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(
            log_card,
            text="Activity Console Log",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 4))
        
        self.log_text = ctk.CTkTextbox(
            log_card,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("#0F172A", "#0B1120"),
            text_color="#F8FAFC",
            height=130
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # RIGHT PANEL - Input & Options Card
        right_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        
        # Quick Presets Card
        preset_card = ctk.CTkFrame(right_panel, corner_radius=10)
        preset_card.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(
            preset_card,
            text="Quick Quality Presets",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 4))
        
        preset_sub = ctk.CTkFrame(preset_card, fg_color="transparent")
        preset_sub.pack(fill=tk.X, padx=14, pady=(0, 10))
        
        self.preset_option = ctk.CTkOptionMenu(
            preset_sub,
            values=self.preset_manager.get_preset_names(),
            variable=self.preset_var,
            command=self.apply_preset
        )
        self.preset_option.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        
        ctk.CTkButton(
            preset_sub,
            text="Apply",
            width=80,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.apply_preset
        ).pack(side=tk.RIGHT)
        
        # URL Input Card
        url_card = ctk.CTkFrame(right_panel, corner_radius=10)
        url_card.pack(fill=tk.X, pady=(0, 10))
        
        url_header = ctk.CTkFrame(url_card, fg_color="transparent")
        url_header.pack(fill=tk.X, padx=14, pady=(10, 4))
        
        ctk.CTkLabel(
            url_header,
            text="Video URL Input (One link per line)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(side=tk.LEFT)
        
        ctk.CTkButton(
            url_header,
            text="Clear",
            width=65,
            height=26,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.clear_urls
        ).pack(side=tk.RIGHT, padx=2)
        
        ctk.CTkButton(
            url_header,
            text="Paste Clipboard",
            width=115,
            height=26,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.paste_clipboard
        ).pack(side=tk.RIGHT, padx=2)
        
        self.url_text = ctk.CTkTextbox(
            url_card,
            height=95,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.url_text.pack(fill=tk.X, padx=14, pady=(0, 12))
        
        # Options Card
        options_card = ctk.CTkFrame(right_panel, corner_radius=10)
        options_card.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(
            options_card,
            text="Format & Media Options",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 6))
        
        opts_grid = ctk.CTkFrame(options_card, fg_color="transparent")
        opts_grid.pack(fill=tk.X, padx=14, pady=(0, 10))
        opts_grid.columnconfigure(1, weight=1)
        
        # Download Type
        ctk.CTkLabel(opts_grid, text="Type:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.type_option = ctk.CTkOptionMenu(
            opts_grid,
            values=["Video", "Audio", "Playlist"],
            variable=self.download_type,
            command=self.update_quality_options
        )
        self.type_option.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        
        # Quality Target
        ctk.CTkLabel(opts_grid, text="Quality:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.quality_option = ctk.CTkOptionMenu(
            opts_grid,
            values=["Best Available", "2160p (4K)", "1440p (2K)", "1080p (Full HD)", "720p (HD)", "480p", "360p"],
            variable=self.quality
        )
        self.quality_option.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        
        # Audio Format
        ctk.CTkLabel(opts_grid, text="Audio Format:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.format_option = ctk.CTkOptionMenu(
            opts_grid,
            values=["mp3", "m4a", "wav"],
            variable=self.format_type
        )
        self.format_option.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        
        # Checkbox Row
        checks_frame = ctk.CTkFrame(options_card, fg_color="transparent")
        checks_frame.pack(fill=tk.X, padx=14, pady=(0, 8))
        
        ctk.CTkCheckBox(checks_frame, text="Thumbnail", variable=self.embed_thumbnail).pack(side=tk.LEFT, padx=(0, 12))
        ctk.CTkCheckBox(checks_frame, text="Metadata", variable=self.embed_metadata).pack(side=tk.LEFT, padx=(0, 12))
        ctk.CTkCheckBox(checks_frame, text="Subtitles", variable=self.embed_subtitles).pack(side=tk.LEFT)
        
        # Path Folder Card
        path_box = ctk.CTkFrame(options_card, fg_color="transparent")
        path_box.pack(fill=tk.X, padx=14, pady=(0, 12))
        path_box.columnconfigure(1, weight=1)
        
        ctk.CTkLabel(path_box, text="Save To:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.path_entry = ctk.CTkEntry(path_box)
        self.path_entry.insert(0, self.config.get("download_path"))
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        
        ctk.CTkButton(
            path_box,
            text="Browse...",
            width=80,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.browse_path
        ).grid(row=0, column=2, padx=4, pady=2)
        
        # Primary Action CTA Button
        ctk.CTkButton(
            right_panel,
            text="Start Download & Add to Queue",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=44,
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            command=self.download_now
        ).pack(fill=tk.X, pady=(4, 0))

        
    def paste_clipboard(self) -> None:
        """Paste clipboard content into URL text area"""
        try:
            clipboard_text = self.frame.clipboard_get()
            if clipboard_text:
                current_text = self.url_text.get('1.0', tk.END).strip()
                if current_text:
                    self.url_text.insert(tk.END, f"\n{clipboard_text}")
                else:
                    self.url_text.delete('1.0', tk.END)
                    self.url_text.insert('1.0', clipboard_text)
                self.log("📋 Pasted URL(s) from clipboard")
        except Exception as e:
            self.log("⚠️ Could not read text from clipboard")

    def apply_theme(self) -> None:
        """Apply theme update to tab elements"""
        pass

    
    def bind_context_menu(self, widget) -> None:
        """Bind right-click context menu to widget"""
        widget.bind("<Button-3>", lambda event: self.show_context_menu(event))
    
    def show_context_menu(self, event) -> None:
        """Show context menu for paste"""
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="Paste", command=lambda: event.widget.event_generate("<<Paste>>"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def update_quality_options(self, choice=None) -> None:
        """Update quality options based on download type"""
        dtype = self.download_type.get()
        if dtype == "Audio":
            self.quality_option.configure(state="disabled")
            self.format_option.configure(state="normal")
        else:
            self.quality_option.configure(state="normal")
            self.format_option.configure(state="disabled")
    
    def apply_preset(self, choice=None) -> None:
        """Apply selected preset"""
        preset_name = self.preset_var.get()
        options = self.preset_manager.apply_preset_to_options(preset_name)
        
        self.download_type.set(options['download_type'].title())
        self.quality.set(options.get('quality', '1080p (Full HD)'))
        self.format_type.set(options.get('format_type', 'mp4'))
        self.embed_thumbnail.set(options.get('embed_thumbnail', True))
        self.embed_metadata.set(options.get('embed_metadata', True))
        self.embed_subtitles.set(options.get('embed_subtitles', False))
        
        self.update_quality_options()
        self.save_user_preferences()

    def save_user_preferences(self, *args) -> None:
        """Auto-save current UI option preferences to config file"""
        try:
            self.config.set("last_download_type", self.download_type.get())
            self.config.set("last_quality", self.quality.get())
            self.config.set("last_format_type", self.format_type.get())
            self.config.set("embed_thumbnail", self.embed_thumbnail.get())
            self.config.set("embed_metadata", self.embed_metadata.get())
            self.config.set("embed_subtitles", self.embed_subtitles.get())
            self.config.set("last_preset", self.preset_var.get())
            if self.path_entry:
                new_path = self.path_entry.get().strip()
                if new_path:
                    self.config.set("download_path", new_path)
        except Exception as e:
            logging.error(f"Error saving preferences: {e}")

    
    def search_youtube(self) -> None:
        """Search YouTube"""
        query = self.search_entry.get().strip()
        if not query:
            self.log("⚠️ Please enter a search query")
            return
        
        self.log(f"🔍 Searching YouTube for: '{query}'...")
        
        def run_search():
            try:
                ydl_opts = {
                    'quiet': True, 
                    'extract_flat': True, 
                    'no_warnings': True,
                    'ignoreerrors': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch15:{query}", download=False)
                
                if not info:
                    self.frame.after(0, lambda: self.log("❌ No response from YouTube"))
                    return
                
                entries = [e for e in info.get('entries', []) if e is not None]
                self.frame.after(0, lambda: self.log(f"✅ Got {len(entries)} result(s)"))
                self.frame.after(0, lambda: self.display_results(entries))
                
            except Exception as e:
                error_msg = str(e)
                logging.error(f"Search error: {error_msg}", exc_info=True)
                self.frame.after(0, lambda: self.log(f"❌ Search error: {error_msg}"))
        
        threading.Thread(target=run_search, daemon=True).start()
    
    def display_results(self, entries) -> None:
        """Display search results"""
        try:
            self.results_tree.delete(*self.results_tree.get_children())
            
            if not entries:
                self.results_frame.pack_forget()
                self.log("No results to display")
                return
            
            self.results_frame.pack(fill=tk.X, pady=(0, 10))
            self.log(f"📋 Displaying {len(entries)} results...")
            
            count = 0
            for entry in entries:
                try:
                    title = entry.get('title', 'Unknown')
                    video_id = entry.get('id', '')
                    
                    url = entry.get('webpage_url')
                    if not url and video_id:
                        url = f"https://www.youtube.com/watch?v={video_id}"
                    if not url:
                        url = "N/A"
                    
                    channel = entry.get('uploader') or entry.get('channel') or 'Unknown'
                    
                    duration = entry.get('duration')
                    if duration and isinstance(duration, (int, float)):
                        dur_str = time.strftime('%H:%M:%S', time.gmtime(duration))
                    else:
                        dur_str = 'N/A'
                    
                    views = entry.get('view_count')
                    views_str = f"{views:,}" if isinstance(views, int) else 'N/A'
                    
                    self.results_tree.insert("", "end", values=(title, channel, dur_str, views_str, url))
                    count += 1
                    
                except Exception as e:
                    logging.error(f"Error displaying entry: {e}")
                    continue
            
            self.log(f"✅ Added {count} results to list")
            self.results_tree.update_idletasks()
            
        except Exception as e:
            self.log(f"❌ Display error: {str(e)}")
            logging.error(f"Display results error: {e}", exc_info=True)
    
    def add_selected_to_queue(self) -> None:
        """Add selected search results to queue"""
        selected = self.results_tree.selection()
        if not selected:
            return
        
        for iid in selected:
            vals = self.results_tree.item(iid)['values']
            url = vals[4]
            title = vals[0]
            item = self.create_download_item(url, title)
            self.downloader.download_queue.add(item)
            self.log(f"Added: {title}")
        
        self.event_bus.emit(Event.QUEUE_UPDATED, None)
        self.log(f"✅ Added {len(selected)} item(s) to queue")
    
    def download_selected_now(self) -> None:
        """Download selected search results immediately"""
        selected = self.results_tree.selection()
        if not selected:
            self.log("⚠️ Please select videos from the search results")
            return
        
        self.log(f"Starting download for {len(selected)} selected item(s)...")
        self.add_selected_to_queue()
        self.downloader.start_queue_processor()
    
    def preview_selected_video(self) -> None:
        """Preview selected search video directly in single ad-free player window"""
        selected = self.results_tree.selection()
        if not selected:
            self.log("⚠️ Please select a video from search results to preview")
            return
        
        iid = selected[0]
        vals = self.results_tree.item(iid)['values']
        title = vals[0]
        url = vals[4]
        
        video_id = ""
        if "v=" in str(url):
            video_id = str(url).split("v=")[1].split("&")[0]
        elif "youtu.be/" in str(url):
            video_id = str(url).split("youtu.be/")[1].split("?")[0]
        
        if not video_id:
            self.log(f"⚠️ Could not extract video ID for: {title}")
            return
        
        self.log(f"🎬 Opening ad-free preview: {title}")
        open_ad_free_player(video_id=video_id, title=title)


    
    def download_now(self) -> None:
        """Download URLs immediately with automatic playlist expansion"""
        urls = self.get_urls()
        if not urls:
            self.log("❌ Please enter at least one URL")
            return
        
        def process_urls_bg():
            items_to_queue = []
            for url in urls:
                item = self.create_download_item(url)
                if item.download_type == 'playlist' or 'list=' in url.lower():
                    self.frame.after(0, lambda u=url: self.log(f"🔍 Extracting playlist items for: {u}..."))
                    playlist_items = self.downloader.extract_playlist_items(item)
                    items_to_queue.extend(playlist_items)
                else:
                    items_to_queue.append(item)
            
            for qitem in items_to_queue:
                self.downloader.download_queue.add(qitem)
            
            def finalize_ui():
                self.event_bus.emit(Event.QUEUE_UPDATED, None)
                self.downloader.start_queue_processor()
                self.log(f"🚀 Added {len(items_to_queue)} item(s) to queue and started engine.")
                
            self.frame.after(0, finalize_ui)

        threading.Thread(target=process_urls_bg, daemon=True).start()
    
    def get_urls(self) -> list:
        """Get URLs from input text box"""
        text = self.url_text.get('1.0', tk.END).strip()
        return [url.strip() for url in text.split('\n') if url.strip()]
    
    def create_download_item(self, url: str, title: str = None) -> DownloadItem:
        """Create download item from current settings"""
        import os
        
        options = {
            'embed_thumbnail': self.embed_thumbnail.get(),
            'embed_metadata': self.embed_metadata.get(),
            'embed_subtitles': self.embed_subtitles.get(),
            'format_type': self.format_type.get().lower(),
        }
        
        template = os.path.join(self.path_entry.get(), self.filename_template.get())
        
        item = DownloadItem(
            url=url,
            download_type=self.download_type.get().lower(),
            quality=self.quality.get(),
            options=options,
            output_template=template
        )
        
        if title:
            item.title = title
        
        return item
    
    def clear_urls(self) -> None:
        """Clear URL input"""
        self.url_text.delete('1.0', tk.END)
    
    def browse_path(self) -> None:
        """Browse for download path"""
        folder = filedialog.askdirectory(initialdir=self.path_entry.get())
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)
            self.config.set("download_path", folder)
    
    def open_folder(self) -> None:
        """Open download folder"""
        import os
        path = self.path_entry.get()
        if os.path.exists(path):
            try:
                os.startfile(path)
            except:
                import subprocess
                subprocess.Popen(['explorer', path])
    
    def focus_url_input(self) -> None:
        """Focus URL input field"""
        if self.url_text:
            self.url_text.focus_set()
    
    def log(self, message: str) -> None:
        """Log message to CTkTextbox"""
        timestamp = time.strftime("%H:%M:%S")
        if self.log_text:
            self.log_text.configure(state='normal')
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state='disabled')
    
    def log_safe(self, message: str) -> None:
        """Thread-safe log"""
        self.frame.after(0, lambda: self.log(message))

