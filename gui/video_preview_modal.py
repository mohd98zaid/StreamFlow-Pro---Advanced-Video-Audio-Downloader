import customtkinter as ctk
import tkinter as tk
from typing import Optional, Callable
import logging
import webbrowser
import subprocess
import sys
import os

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False


def open_ad_free_player(video_id: str, title: str = "Video Preview"):
    """
    Launch the native Chromium WebView2 ad-free player in a dedicated process
    """
    if not video_id:
        return
    
    player_script = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "utils",
        "player_process.py"
    )
    
    if HAS_WEBVIEW and os.path.exists(player_script):
        try:
            subprocess.Popen([
                sys.executable,
                player_script,
                video_id,
                title
            ])
            return
        except Exception as e:
            logging.error(f"Failed to launch webview player process: {e}")

    # If pywebview is missing, warn the user
    logging.warning("pywebview is not available. Please install 'pywebview' (pip install pywebview) to enable in-app ad-free playback.")
    # Fallback to privacy-enhanced browser embed
    embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=1&modestbranding=1&rel=0"
    webbrowser.open(embed_url)


class VideoPreviewModal(ctk.CTkToplevel):
    """
    In-App Ad-Free Video Preview Controller Window
    """

    def __init__(
        self,
        parent,
        video_id: str,
        title: str = "Video Preview",
        channel: str = "",
        url: str = "",
        on_add_to_queue: Optional[Callable[[], None]] = None,
        on_download_now: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)

        self.video_id = video_id
        self.title_text = title
        self.channel_text = channel
        self.url = url or f"https://www.youtube.com/watch?v={video_id}"
        self.on_add_to_queue = on_add_to_queue
        self.on_download_now = on_download_now

        self.title(f"🎬 Ad-Free Player: {title[:45]}")
        self.geometry("640x380")
        self.minsize(560, 320)
        self.resizable(False, False)

        # Make modal stay on top initially
        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))

        self.create_ui()
        
        # Auto-launch native ad-free player
        self.after(200, self._launch_player)

    def create_ui(self) -> None:
        # Header Info Card
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1E293B", "#0F172A"))
        header_frame.pack(fill=tk.X, padx=14, pady=(14, 8))

        ctk.CTkLabel(
            header_frame,
            text=f"🎬 {self.title_text}",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#F8FAFC",
            anchor="w",
            wraplength=590,
        ).pack(fill=tk.X, padx=14, pady=(12, 4))

        sub_text = f"Channel: {self.channel_text}" if self.channel_text else f"URL: {self.url}"
        ctk.CTkLabel(
            header_frame,
            text=sub_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94A3B8",
            anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(0, 12))

        # Main Player Status Frame
        status_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#0F172A", "#0B1120"))
        status_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        ctk.CTkLabel(
            status_frame,
            text="✨ Ad-Free Privacy Stream Ready",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#38BDF8",
        ).pack(pady=(22, 6))

        ctk.CTkLabel(
            status_frame,
            text="Playing video using YouTube's privacy-enhanced embed without ads.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94A3B8",
        ).pack(pady=(0, 14))

        play_btn = ctk.CTkButton(
            status_frame,
            text="▶️ Play / Reopen Ad-Free Player",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=("#059669", "#10B981"),
            hover_color=("#047857", "#059669"),
            height=38,
            command=self._launch_player,
        )
        play_btn.pack(pady=4)

        # Action Buttons Footer Bar
        footer_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        footer_frame.pack(fill=tk.X, padx=14, pady=(8, 14))

        if self.on_add_to_queue:
            ctk.CTkButton(
                footer_frame,
                text="➕ Add to Queue",
                fg_color=("gray85", "#334155"),
                text_color=("gray10", "#F8FAFC"),
                command=self._handle_add_to_queue,
            ).pack(side=tk.LEFT, padx=4)

        if self.on_download_now:
            ctk.CTkButton(
                footer_frame,
                text="⚡ Download Now",
                fg_color=("#2563EB", "#3B82F6"),
                command=self._handle_download_now,
            ).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(
            footer_frame,
            text="Close",
            width=80,
            fg_color=("#DC2626", "#EF4444"),
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=4)

    def _launch_player(self) -> None:
        """Launch the ad-free player"""
        open_ad_free_player(self.video_id, self.title_text)

    def _handle_add_to_queue(self) -> None:
        if self.on_add_to_queue:
            self.on_add_to_queue()
        self.destroy()

    def _handle_download_now(self) -> None:
        if self.on_download_now:
            self.on_download_now()
        self.destroy()
