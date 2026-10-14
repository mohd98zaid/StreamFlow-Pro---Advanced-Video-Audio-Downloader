"""
StreamFlow Pro - Main Application Entrypoint
Launches the modern desktop interface (Tauri / React + Python) or the
Ad-Free YouTube / Music Player depending on command-line flags.
"""
import sys
import subprocess
import logging
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Configure logging centrally
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def check_dependencies():
    """Verify required runtime dependencies."""
    missing = []
    
    try:
        import yt_dlp
    except ImportError:
        missing.append("yt-dlp")

    try:
        import static_ffmpeg
    except ImportError:
        missing.append("static-ffmpeg")

    try:
        import webview
    except ImportError:
        missing.append("pywebview")

    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")

    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn")

    if missing:
        logging.warning(f"Missing recommended packages: {', '.join(missing)}")
        print(f"\n[!] Notice: Missing packages: {', '.join(missing)}")
        print(f"[*] Run: pip install -r requirements.txt\n")
        return False
    
    return True

def main():
    """Main entry point for StreamFlow Pro."""
    # Ensure static-ffmpeg is available on PATH
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except ImportError:
        logging.warning("static-ffmpeg not installed; high-quality audio/video merge may fail.")

    check_dependencies()

    # Route based on command-line argument if provided
    args = [a.lower() for a in sys.argv[1:]]
    if any(arg in args for arg in ["--player", "-p", "player", "--music", "music", "youtube"]):
        logging.info("Starting YouTube & Music Player...")
        from utils.player_process import main as launch_player
        launch_player()
    else:
        logging.info("Starting StreamFlow Pro Modern Downloader Interface...")
        import run_modern
        run_modern.main()

if __name__ == "__main__":
    main()
