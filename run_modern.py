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
import urllib.request
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

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 47891
APP_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

def start_backend():
    """Start local API and WebSocket bridge on 127.0.0.1:47891."""
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")

def wait_for_backend(timeout: float = 6.0) -> bool:
    """Poll backend health check until it responds or times out."""
    start_time = time.time()
    url = f"{APP_URL}/api/status"
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=0.8) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False

def main():
    print("=" * 60)
    print("    StreamFlow Pro - High Performance Media Workstation")
    print("=" * 60)

    # 1. Check if frontend production bundle is built
    dist_index = ROOT_DIR / "frontend" / "dist" / "index.html"
    if not dist_index.exists():
        print("[!] Frontend production bundle not found. Building now...")
        subprocess.run(["npm.cmd", "run", "build"], cwd=str(ROOT_DIR / "frontend"), shell=True)

    # 2. Start FastAPI backend in background daemon thread
    print("\n[1/2] Starting local Python download engine & WebSocket bridge...")
    backend_thread = threading.Thread(target=start_backend, daemon=True, name="BackendServer")
    backend_thread.start()

    # Wait for backend to be online and responding
    if not wait_for_backend():
        print("[!] Warning: Backend health check timed out, attempting launch anyway...")

    # 3. Launch modern desktop interface
    print("[2/2] Launching modern desktop interface...")
    try:
        import webview
        window = webview.create_window(
            title="StreamFlow Pro",
            url=APP_URL,
            width=1220,
            height=800,
            min_size=(960, 640),
            background_color="#0B0D12",
            text_select=False,
            zoomable=False,
        )
        webview.start(debug=False, private_mode=False)
    except Exception as e:
        print(f"[!] WebView launcher note: {e}")
        print(f"[*] Opening StreamFlow Pro in default system browser: {APP_URL}")
        import webbrowser
        webbrowser.open(APP_URL)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down StreamFlow Pro...")

if __name__ == "__main__":
    main()
