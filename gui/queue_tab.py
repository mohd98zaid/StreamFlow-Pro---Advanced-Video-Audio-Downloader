import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import logging

from core import Event, EventBus, DownloadStatus
from core.downloader import Downloader


class QueueTab:
    """Queue tab UI component built with CustomTkinter"""
    
    def __init__(self, parent, downloader: Downloader, event_bus: EventBus):
        self.downloader = downloader
        self.event_bus = event_bus
        
        # Parent tab frame
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # UI components
        self.queue_tree: Optional[ttk.Treeview] = None
        self.stat_queued_val: Optional[ctk.CTkLabel] = None
        self.stat_active_val: Optional[ctk.CTkLabel] = None
        self.stat_paused_val: Optional[ctk.CTkLabel] = None
        self.context_menu: Optional[tk.Menu] = None
        
        # Subscribe to events
        self.event_bus.subscribe(Event.DOWNLOAD_PROGRESS, lambda _: self.refresh())
        self.event_bus.subscribe(Event.QUEUE_UPDATED, lambda _: self.refresh())
        
        # Build UI
        self.create_ui()
    
    def create_ui(self) -> None:
        """Create queue tab UI with CustomTkinter metric cards and management toolbar"""
        main_container = ctk.CTkFrame(self.frame, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # 1. TOP METRICS DASHBOARD CARDS
        metrics_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        metrics_frame.pack(fill=tk.X, pady=(0, 10))
        metrics_frame.columnconfigure((0, 1, 2), weight=1)
        
        # Card 1: Total Queue
        card1 = ctk.CTkFrame(metrics_frame, corner_radius=10)
        card1.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(card1, text="Total In Queue", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("gray40", "gray65")).pack(anchor="w", padx=14, pady=(10, 0))
        self.stat_queued_val = ctk.CTkLabel(card1, text="0 Items", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"))
        self.stat_queued_val.pack(anchor="w", padx=14, pady=(2, 10))
        
        # Card 2: Active Downloading Engine
        card2 = ctk.CTkFrame(metrics_frame, corner_radius=10)
        card2.grid(row=0, column=1, sticky="ew", padx=3)
        ctk.CTkLabel(card2, text="Active Engine", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("gray40", "gray65")).pack(anchor="w", padx=14, pady=(10, 0))
        self.stat_active_val = ctk.CTkLabel(card2, text="0 Downloading", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color=("#2563EB", "#3B82F6"))
        self.stat_active_val.pack(anchor="w", padx=14, pady=(2, 10))
        
        # Card 3: Paused / Waiting
        card3 = ctk.CTkFrame(metrics_frame, corner_radius=10)
        card3.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(card3, text="Paused / Waiting", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("gray40", "gray65")).pack(anchor="w", padx=14, pady=(10, 0))
        self.stat_paused_val = ctk.CTkLabel(card3, text="0 Paused", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color=("#D97706", "#F59E0B"))
        self.stat_paused_val.pack(anchor="w", padx=14, pady=(2, 10))
        
        # 2. CONTROL TOOLBAR CARD
        toolbar_card = ctk.CTkFrame(main_container, corner_radius=10)
        toolbar_card.pack(fill=tk.X, pady=(0, 10))
        
        toolbar_inner = ctk.CTkFrame(toolbar_card, fg_color="transparent")
        toolbar_inner.pack(fill=tk.X, padx=12, pady=10)
        
        # Start Engine
        ctk.CTkButton(
            toolbar_inner,
            text="Start Engine",
            width=100,
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            command=self.start_queue
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # Single-Item Controls
        ctk.CTkButton(
            toolbar_inner,
            text="⏸️ Pause Selected",
            width=115,
            fg_color=("#D97706", "#F59E0B"),
            hover_color=("#B45309", "#D97706"),
            text_color="#FFFFFF",
            command=self.pause_selected
        ).pack(side=tk.LEFT, padx=3)
        
        ctk.CTkButton(
            toolbar_inner,
            text="▶️ Resume Selected",
            width=120,
            fg_color=("#059669", "#10B981"),
            hover_color=("#047857", "#059669"),
            text_color="#FFFFFF",
            command=self.resume_selected
        ).pack(side=tk.LEFT, padx=3)
        
        ctk.CTkButton(
            toolbar_inner,
            text="⏹️ Stop Selected",
            width=110,
            fg_color=("#DC2626", "#EF4444"),
            hover_color=("#B91C1C", "#DC2626"),
            text_color="#FFFFFF",
            command=self.stop_selected
        ).pack(side=tk.LEFT, padx=3)
        
        # Bulk Controls
        ctk.CTkButton(
            toolbar_inner,
            text="Pause All",
            width=80,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.pause_all
        ).pack(side=tk.LEFT, padx=3)
        
        ctk.CTkButton(
            toolbar_inner,
            text="Resume All",
            width=85,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.resume_all
        ).pack(side=tk.LEFT, padx=3)
        
        ctk.CTkButton(
            toolbar_inner,
            text="Clear Finished",
            width=100,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.clear_finished
        ).pack(side=tk.LEFT, padx=3)
        
        ctk.CTkButton(
            toolbar_inner,
            text="🗑️ Remove Selected",
            width=125,
            fg_color=("gray75", "#475569"),
            hover_color=("gray65", "#334155"),
            command=self.remove_selected
        ).pack(side=tk.RIGHT, padx=2)
        
        # 3. LIVE QUEUE MATRIX CARD
        matrix_card = ctk.CTkFrame(main_container, corner_radius=10)
        matrix_card.pack(fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(
            matrix_card,
            text="Live Queue Download Matrix (Right-click or Double-click to control individual downloads)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 6))
        
        tree_cont = ctk.CTkFrame(matrix_card, fg_color="transparent")
        tree_cont.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        
        vsb = ttk.Scrollbar(tree_cont, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.queue_tree = ttk.Treeview(
            tree_cont,
            columns=("Title", "Status", "Progress", "Speed", "ETA"),
            yscrollcommand=vsb.set,
            selectmode="extended"
        )
        self.queue_tree.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.queue_tree.yview)
        
        # Configure columns
        self.queue_tree.heading("#0", text="Type", anchor="center")
        self.queue_tree.heading("Title", text="Media Title", anchor="w")
        self.queue_tree.heading("Status", text="Status", anchor="center")
        self.queue_tree.heading("Progress", text="Progress", anchor="center")
        self.queue_tree.heading("Speed", text="Speed", anchor="center")
        self.queue_tree.heading("ETA", text="ETA", anchor="center")
        
        self.queue_tree.column("#0", width=60, stretch=False, anchor="center")
        self.queue_tree.column("Title", width=400, anchor="w")
        self.queue_tree.column("Status", width=120, anchor="center")
        self.queue_tree.column("Progress", width=100, anchor="center")
        self.queue_tree.column("Speed", width=110, anchor="center")
        self.queue_tree.column("ETA", width=100, anchor="center")
        
        # Tags for status styling
        self.queue_tree.tag_configure("DOWNLOADING", foreground="#3B82F6")
        self.queue_tree.tag_configure("COMPLETED", foreground="#10B981")
        self.queue_tree.tag_configure("FAILED", foreground="#EF4444")
        self.queue_tree.tag_configure("PAUSED", foreground="#F59E0B")
        self.queue_tree.tag_configure("CANCELLED", foreground="#94A3B8")
        self.queue_tree.tag_configure("QUEUED", foreground="#CBD5E1")
        
        # Create Right-Click Context Menu
        self.create_context_menu()
        self.queue_tree.bind("<Button-3>", self.show_context_menu)
        self.queue_tree.bind("<Double-1>", self.on_double_click)
    
    def create_context_menu(self) -> None:
        """Create right-click context menu for individual items"""
        self.context_menu = tk.Menu(self.frame, tearoff=0)
        self.context_menu.add_command(label="⏸️ Pause Selected", command=self.pause_selected)
        self.context_menu.add_command(label="▶️ Resume Selected", command=self.resume_selected)
        self.context_menu.add_command(label="⏹️ Stop / Cancel Selected", command=self.stop_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ Remove from Queue", command=self.remove_selected)
        self.context_menu.add_command(label="📋 Copy Video URL", command=self.copy_url)

    def show_context_menu(self, event) -> None:
        """Display right-click context menu on selected row"""
        row_id = self.queue_tree.identify_row(event.y)
        if row_id:
            if row_id not in self.queue_tree.selection():
                self.queue_tree.selection_set(row_id)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, event) -> None:
        """Double click to toggle pause/resume on the clicked item"""
        row_id = self.queue_tree.identify_row(event.y)
        if not row_id:
            return
        
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.id == row_id:
                    if item.status == DownloadStatus.PAUSED.value:
                        item.paused = False
                        item.status = DownloadStatus.QUEUED.value
                        self.event_bus.emit(Event.LOG_MESSAGE, f"▶️ Resumed: {item.title}")
                    else:
                        item.paused = True
                        item.status = DownloadStatus.PAUSED.value
                        self.event_bus.emit(Event.LOG_MESSAGE, f"⏸️ Paused: {item.title}")
                    break
        
        self.refresh()
        self.event_bus.emit(Event.QUEUE_UPDATED, None)

    def pause_selected(self) -> None:
        """Pause selected item(s)"""
        selection = self.queue_tree.selection()
        if not selection:
            return
        
        with self.downloader.download_queue.lock:
            for iid in selection:
                for item in self.downloader.download_queue.items:
                    if item.id == iid:
                        item.paused = True
                        item.status = DownloadStatus.PAUSED.value
                        self.event_bus.emit(Event.LOG_MESSAGE, f"⏸️ Paused: {item.title}")
                        break
        
        self.refresh()
        self.event_bus.emit(Event.QUEUE_UPDATED, None)

    def resume_selected(self) -> None:
        """Resume selected item(s)"""
        selection = self.queue_tree.selection()
        if not selection:
            return
        
        with self.downloader.download_queue.lock:
            for iid in selection:
                for item in self.downloader.download_queue.items:
                    if item.id == iid:
                        item.paused = False
                        item.cancelled = False
                        item.status = DownloadStatus.QUEUED.value
                        self.event_bus.emit(Event.LOG_MESSAGE, f"▶️ Resumed: {item.title}")
                        break
        
        self.downloader.start_queue_processor()
        self.refresh()
        self.event_bus.emit(Event.QUEUE_UPDATED, None)

    def stop_selected(self) -> None:
        """Stop / Cancel selected item(s)"""
        selection = self.queue_tree.selection()
        if not selection:
            return
        
        with self.downloader.download_queue.lock:
            for iid in selection:
                for item in self.downloader.download_queue.items:
                    if item.id == iid:
                        item.cancelled = True
                        item.status = DownloadStatus.CANCELLED.value
                        self.event_bus.emit(Event.LOG_MESSAGE, f"⏹️ Stopped: {item.title}")
                        break
        
        self.refresh()
        self.event_bus.emit(Event.QUEUE_UPDATED, None)

    def copy_url(self) -> None:
        """Copy URL of selected item to clipboard"""
        selection = self.queue_tree.selection()
        if not selection:
            return
        
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.id == selection[0]:
                    self.frame.clipboard_clear()
                    self.frame.clipboard_append(item.url)
                    self.event_bus.emit(Event.LOG_MESSAGE, f"📋 Copied URL: {item.url}")
                    break

    def start_queue(self) -> None:
        """Start queue processing"""
        self.downloader.start_queue_processor()
        self.event_bus.emit(Event.LOG_MESSAGE, "Queue started")
        self.refresh()
    
    def pause_all(self) -> None:
        """Pause all queued items"""
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                item.paused = True
                item.status = DownloadStatus.PAUSED.value
        
        self.refresh()
        self.event_bus.emit(Event.LOG_MESSAGE, "Paused all queue items")
    
    def resume_all(self) -> None:
        """Resume all paused items"""
        with self.downloader.download_queue.lock:
            for item in self.downloader.download_queue.items:
                if item.paused:
                    item.paused = False
                    item.status = DownloadStatus.QUEUED.value
        
        self.downloader.start_queue_processor()
        self.refresh()
        self.event_bus.emit(Event.LOG_MESSAGE, "Resumed all paused items")
    
    def clear_finished(self) -> None:
        """Clear finished downloads from queue"""
        count = self.downloader.download_queue.clear_completed()
        self.refresh()
        self.event_bus.emit(Event.LOG_MESSAGE, f"Cleared {count} completed downloads from queue")

    def remove_selected(self) -> None:
        """Remove selected items from queue (stopping if active)"""
        selection = self.queue_tree.selection()
        if not selection:
            return
        
        with self.downloader.download_queue.lock:
            for iid in selection:
                for item in self.downloader.download_queue.items[:]:
                    if item.id == iid:
                        item.cancelled = True
                        self.downloader.download_queue.remove(item)
                        self.event_bus.emit(Event.LOG_MESSAGE, f"🗑️ Removed: {item.title or item.url}")
                        break
        
        self.refresh()
        self.event_bus.emit(Event.QUEUE_UPDATED, None)
    
    def refresh(self) -> None:
        """Refresh queue tree display and metrics"""
        if not self.queue_tree:
            return
            
        with self.downloader.download_queue.lock:
            items = list(self.downloader.download_queue.items)
        
        # Update metrics
        total_count = len(items)
        downloading_count = sum(1 for i in items if i.status == DownloadStatus.DOWNLOADING.value)
        paused_count = sum(1 for i in items if i.status == DownloadStatus.PAUSED.value)
        
        if self.stat_queued_val:
            self.stat_queued_val.configure(text=f"{total_count} Total")
        if self.stat_active_val:
            self.stat_active_val.configure(text=f"{downloading_count} Active")
        if self.stat_paused_val:
            self.stat_paused_val.configure(text=f"{paused_count} Paused")

        # Get existing tree item IDs
        existing_iids = set(self.queue_tree.get_children())
        current_iids = set()
        
        for item in items:
            title = item.title
            if len(title) > 55:
                title = title[:52] + "..."
            
            values = (
                title,
                item.status.upper(),
                f"{item.progress:.1f}%",
                item.speed if item.speed else "0 KB/s",
                item.eta if item.eta else "--:--"
            )
            
            icon_text = "Audio" if item.download_type == 'audio' else "Video"
            tag_name = item.status.upper()
            
            if item.id in existing_iids:
                self.queue_tree.item(item.id, text=icon_text, values=values, tags=(tag_name,))
            else:
                self.queue_tree.insert("", "end", iid=item.id, text=icon_text, values=values, tags=(tag_name,))
            
            current_iids.add(item.id)
        
        # Remove items that are no longer in queue
        for iid in existing_iids - current_iids:
            self.queue_tree.delete(iid)
