import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import os
import logging
from datetime import datetime

from core import Event, EventBus, DownloadStatus
from core.database import DatabaseManager


class HistoryTab:
    """History tab UI component built with CustomTkinter"""
    
    def __init__(self, parent, database: DatabaseManager, event_bus: EventBus):
        self.database = database
        self.event_bus = event_bus
        
        # Parent tab frame
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # UI components
        self.history_tree: Optional[ttk.Treeview] = None
        self.search_var = tk.StringVar()
        self.status_filter_var = tk.StringVar(value="All")
        
        # Pagination
        self.current_page = 0
        self.page_size = 100
        
        # Subscribe to events
        self.event_bus.subscribe(Event.DOWNLOAD_COMPLETED, lambda _: self.refresh())
        self.event_bus.subscribe(Event.DOWNLOAD_FAILED, lambda _: self.refresh())
        self.event_bus.subscribe(Event.HISTORY_UPDATED, lambda _: self.refresh())
        
        # Build UI
        self.create_ui()
        self.refresh()
    
    def create_ui(self) -> None:
        """Create history tab UI with CustomTkinter controls and table matrix"""
        main_container = ctk.CTkFrame(self.frame, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # 1. TOOLBAR & FILTER CARD
        control_card = ctk.CTkFrame(main_container, corner_radius=10)
        control_card.pack(fill=tk.X, pady=(0, 10))
        
        control_inner = ctk.CTkFrame(control_card, fg_color="transparent")
        control_inner.pack(fill=tk.X, padx=12, pady=10)
        
        # Search Box
        ctk.CTkLabel(control_inner, text="Search:", font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side=tk.LEFT, padx=(0, 6))
        search_entry = ctk.CTkEntry(
            control_inner,
            textvariable=self.search_var,
            placeholder_text="Filter title or URL...",
            width=220
        )
        search_entry.pack(side=tk.LEFT, padx=(0, 12))
        search_entry.bind('<Return>', lambda e: self.refresh())
        
        # Status Filter Option Menu
        ctk.CTkLabel(control_inner, text="Status:", font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side=tk.LEFT, padx=(0, 6))
        filter_option = ctk.CTkOptionMenu(
            control_inner,
            values=["All", "Completed", "Failed", "Cancelled"],
            variable=self.status_filter_var,
            width=110,
            command=lambda choice: self.refresh()
        )
        filter_option.pack(side=tk.LEFT, padx=(0, 12))
        
        ctk.CTkButton(
            control_inner,
            text="Refresh",
            width=80,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.refresh
        ).pack(side=tk.LEFT, padx=4)
        
        ctk.CTkButton(
            control_inner,
            text="Clear History",
            width=100,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.clear_history
        ).pack(side=tk.LEFT, padx=4)
        
        # Right Actions
        ctk.CTkButton(
            control_inner,
            text="Play Media",
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            command=self.play_file
        ).pack(side=tk.RIGHT, padx=4)
        
        ctk.CTkButton(
            control_inner,
            text="Open Folder",
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.open_in_explorer
        ).pack(side=tk.RIGHT, padx=4)
        
        # 2. DOWNLOAD HISTORY MATRIX CARD
        matrix_card = ctk.CTkFrame(main_container, corner_radius=10)
        matrix_card.pack(fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(
            matrix_card,
            text="Download History Archive",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 6))
        
        tree_cont = ctk.CTkFrame(matrix_card, fg_color="transparent")
        tree_cont.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        
        vsb = ttk.Scrollbar(tree_cont, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.history_tree = ttk.Treeview(
            tree_cont,
            columns=("Title", "Type", "Status", "Date"),
            yscrollcommand=vsb.set,
            selectmode="extended"
        )
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.history_tree.yview)
        
        # Configure columns
        self.history_tree.heading("#0", text="", anchor="w")
        self.history_tree.heading("Title", text="Media Title", anchor="w")
        self.history_tree.heading("Type", text="Type", anchor="center")
        self.history_tree.heading("Status", text="Status", anchor="center")
        self.history_tree.heading("Date", text="Completion Date", anchor="center")
        
        self.history_tree.column("#0", width=0, stretch=tk.NO)
        self.history_tree.column("Title", width=440, anchor="w")
        self.history_tree.column("Type", width=100, anchor="center")
        self.history_tree.column("Status", width=120, anchor="center")
        self.history_tree.column("Date", width=160, anchor="center")
        
        # Tags for status styling
        self.history_tree.tag_configure("COMPLETED", foreground="#10B981")
        self.history_tree.tag_configure("FAILED", foreground="#EF4444")
        self.history_tree.tag_configure("CANCELLED", foreground="#F59E0B")
        
        # Bind events
        self.history_tree.bind("<Button-3>", self.show_context_menu)
        self.history_tree.bind("<Double-1>", lambda e: self.play_file())
        
        # 3. PAGINATION FOOTER
        pagination_card = ctk.CTkFrame(main_container, corner_radius=10)
        pagination_card.pack(fill=tk.X, pady=(10, 0))
        
        pag_inner = ctk.CTkFrame(pagination_card, fg_color="transparent")
        pag_inner.pack(padx=12, pady=6)
        
        ctk.CTkButton(
            pag_inner,
            text="Previous Page",
            width=110,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.previous_page
        ).pack(side=tk.LEFT, padx=6)
        
        self.page_label = ctk.CTkLabel(
            pag_inner,
            text="Page 1",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        self.page_label.pack(side=tk.LEFT, padx=16)
        
        ctk.CTkButton(
            pag_inner,
            text="Next Page",
            width=110,
            fg_color=("gray85", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            command=self.next_page
        ).pack(side=tk.LEFT, padx=6)
    
    def refresh(self) -> None:
        """Refresh history display"""
        self.history_tree.delete(*self.history_tree.get_children())
        
        # Get search and filter criteria
        search_query = self.search_var.get().strip() or None
        status_filter = None if self.status_filter_var.get() == "All" else self.status_filter_var.get()
        
        # Get history from database with pagination
        offset = self.current_page * self.page_size
        items = self.database.get_history(
            limit=self.page_size,
            offset=offset,
            status_filter=status_filter,
            search_query=search_query
        )
        
        for item in items:
            title = item.title
            if len(title) > 60:
                title = title[:57] + "..."
            
            date_str = ""
            if item.completed_at:
                try:
                    dt = datetime.fromisoformat(item.completed_at)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    date_str = item.completed_at[:16]
            
            values = (
                title,
                item.download_type.title(),
                item.status.upper(),
                date_str
            )
            
            tag_name = item.status.upper()
            
            # Store item ID in tags along with status tag for coloring
            self.history_tree.insert("", "end", values=values, tags=(item.id, tag_name))
        
        # Update pagination label
        if hasattr(self, 'page_label') and self.page_label:
            self.page_label.configure(text=f"Page {self.current_page + 1}")

    
    def previous_page(self) -> None:
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh()
    
    def next_page(self) -> None:
        """Go to next page"""
        self.current_page += 1
        self.refresh()
        
        # If no items, go back
        if len(self.history_tree.get_children()) == 0:
            self.current_page -= 1
            self.refresh()
    
    def get_selected_item(self):
        """Get selected history item from database"""
        selection = self.history_tree.selection()
        if not selection:
            return None
        
        # Get item ID from tags
        item_id = self.history_tree.item(selection[0])['tags'][0]
        return self.database.get_download_by_id(item_id)
    
    def open_in_explorer(self) -> None:
        """Open selected file in explorer"""
        item = self.get_selected_item()
        if not item:
            return
        
        if item.status != DownloadStatus.COMPLETED.value:
            messagebox.showwarning("Warning", "Can only open completed downloads")
            return
        
        if not item.file_path or not os.path.exists(item.file_path):
            messagebox.showerror("Error", "File not found")
            return
        
        try:
            import subprocess
            subprocess.Popen(['explorer', '/select,', os.path.abspath(item.file_path)])
        except Exception as e:
            logging.error(f"Error opening explorer: {e}")
            messagebox.showerror("Error", f"Could not open file location: {e}")
    
    def play_file(self) -> None:
        """Play selected file"""
        item = self.get_selected_item()
        if not item:
            return
        
        if item.status != DownloadStatus.COMPLETED.value:
            messagebox.showwarning("Warning", "Can only play completed downloads")
            return
        
        if not item.file_path or not os.path.exists(item.file_path):
            messagebox.showerror("Error", "File not found")
            return
        
        try:
            os.startfile(item.file_path)
        except Exception as e:
            logging.error(f"Error playing file: {e}")
            messagebox.showerror("Error", f"Could not open file: {e}")
    
    def show_context_menu(self, event) -> None:
        """Show right-click context menu"""
        item_id = self.history_tree.identify_row(event.y)
        if item_id:
            self.history_tree.selection_set(item_id)
            menu = tk.Menu(self.frame, tearoff=0)
            menu.add_command(label="Play", command=self.play_file)
            menu.add_command(label="Open Folder", command=self.open_in_explorer)
            menu.add_separator()
            menu.add_command(label="Delete from History", command=self.delete_selected)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
    
    def delete_selected(self) -> None:
        """Delete selected items from history"""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        if not messagebox.askyesno("Confirm", f"Delete {len(selection)} item(s) from history?"):
            return
        
        for iid in selection:
            item_id = self.history_tree.item(iid)['tags'][0]
            self.database.delete_download(item_id)
        
        self.refresh()
        messagebox.showinfo("Success", f"Deleted {len(selection)} item(s)")
    
    def clear_history(self) -> None:
        """Clear all history"""
        if not messagebox.askyesno("Clear History", 
                                  "Are you sure you want to clear all history?\n\nThis action cannot be undone."):
            return
        
        if self.database.clear_history():
            self.refresh()
            messagebox.showinfo("Success", "History cleared")
        else:
            messagebox.showerror("Error", "Failed to clear history")

