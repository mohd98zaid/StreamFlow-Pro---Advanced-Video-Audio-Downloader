"""
StreamFlow Pro - Modern Desktop Application Launcher
Launches the local Python backend engine (FastAPI + WebSocket) and opens the
modern React desktop interface in native Windows WebView2 / Tauri.
"""
import sys
import os
import time
import threading
import subprocess
import logging
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure static_ffmpeg is on PATH
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

import uvicorn
from backend.server import app

def start_backend():
    """Start local API and WebSocket bridge on 127.0.0.1:47891."""
    uvicorn.run(app, host="127.0.0.1", port=47891, log_level="warning")

def main():
    print("=" * 60)
    print("    StreamFlow Pro - High Performance Media Workstation")
    print("=" * 60)
    print("\n[1/2] Starting local Python download engine & WebSocket bridge...")

    # Start FastAPI backend in background daemon thread
    backend_thread = threading.Thread(target=start_backend, daemon=True, name="BackendServer")
    backend_thread.start()

    # Wait for backend to be ready
    time.sleep(1.2)

    # Check if frontend is built
    dist_index = ROOT_DIR / "frontend" / "dist" / "index.html"
    if not dist_index.exists():
        print("[!] Building frontend production bundle...")
        subprocess.run(["npm.cmd", "run", "build"], cwd=str(ROOT_DIR / "frontend"), shell=True)

    print("[2/2] Launching modern desktop interface...")

    # Try launching native WebView2 window via pywebview
    try:
        import webview
        window = webview.create_window(
            title="StreamFlow Pro",
            url=str(dist_index.as_uri()),
            width=1180,
            height=780,
            min_size=(960, 640),
            background_color="#0B0D12",
            text_select=False,
            zoomable=False,
        )
        webview.start(debug=False)
    except Exception as e:
        print(f"[!] WebView launcher error: {e}")
        print("[*] Launching in default system browser instead...")
        import webbrowser
        webbrowser.open("http://localhost:5173" if not dist_index.exists() else str(dist_index.as_uri()))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down StreamFlow Pro...")

if __name__ == "__main__":
    main()
