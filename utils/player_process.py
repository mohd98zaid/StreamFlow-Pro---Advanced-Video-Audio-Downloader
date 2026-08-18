import sys
import os
import re
import threading
import ctypes
import time
import json
import logging
from pathlib import Path
import webview
import yt_dlp

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import ConfigManager
from core.database import DatabaseManager
from core.models import DownloadItem, DownloadStatus

active_window = None
current_download_lock = threading.Lock()
is_downloading = False

class PlayerApi:
    """JS API without self-references to avoid .NET introspection recursion"""
    def toggle_fullscreen(self):
        global active_window
        if active_window:
            active_window.toggle_fullscreen()
            return active_window.fullscreen
        return False

    def exit_fullscreen(self):
        global active_window
        if active_window and active_window.fullscreen:
            active_window.toggle_fullscreen()
            return False
        return False

    def is_fullscreen(self):
        global active_window
        return bool(active_window and active_window.fullscreen)

    def download_current_video(self, url_or_id):
        """Send current video download request to the main application queue"""
        global is_downloading
        try:
            target_url = url_or_id.strip() if url_or_id else ""
            if not target_url:
                if active_window:
                    active_window.evaluate_js("if(window.onDownloadComplete) window.onDownloadComplete(false, 'Play a video first!');")
                return {"status": "error", "message": "Play a video first"}
            
            # If YouTube URL, extract strictly the single video ID
            if "youtube.com" in target_url or "youtu.be" in target_url:
                v_match = re.search(r'(?:v=|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', target_url)
                if v_match:
                    target_url = f"https://www.youtube.com/watch?v={v_match.group(1)}"
                else:
                    if active_window:
                        active_window.evaluate_js("if(window.onDownloadComplete) window.onDownloadComplete(false, 'Play a video first!');")
                    return {"status": "error", "message": "Play a video first"}
            
            # Send to SQLite inbox_queue so the main application active queue picks it up immediately
            db = DatabaseManager()
            db.add_to_inbox(target_url, title="", download_type="video", quality="Best Available")
            logging.info(f"Queued single video download to main app: {target_url}")
            
            if active_window:
                active_window.evaluate_js("if(window.onDownloadComplete) window.onDownloadComplete(true, 'Added to Download Queue!');")
            
            return {"status": "queued", "message": "Added to Download Queue"}
        except Exception as e:
            logging.error(f"Error queueing player download: {e}")
            if active_window:
                clean_msg = str(e).replace("'", "").replace('"', '')[:30]
                active_window.evaluate_js(f"if(window.onDownloadComplete) window.onDownloadComplete(false, '{clean_msg}');")
            return {"status": "error", "message": str(e)}



def start_esc_listener():
    """Background listener for physical ESC key to restore window even when focus is inside video player"""
    def listener_loop():
        try:
            user32 = ctypes.windll.user32
            VK_ESCAPE = 0x1B
            while True:
                time.sleep(0.05)
                if active_window and active_window.fullscreen:
                    if user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
                        time.sleep(0.18)  # Debounce
                        if active_window and active_window.fullscreen:
                            active_window.toggle_fullscreen()
        except Exception:
            pass

    t = threading.Thread(target=listener_loop, daemon=True)
    t.start()

CINEMA_CSS = """
/* Hide external YouTube UI: headers, sidebar recommendations, comments in Cinema Mode */
#masthead-container, #masthead, #guide, #guide-wrapper, #secondary, #comments, 
#below, #chat, #ticker, ytd-merch-shelf-renderer, ytd-banner-promo-renderer, 
.ytp-ad-module, .video-ads, .ytp-ad-overlay-container, ytd-popup-container,
#voice-search-button, #chips, ytd-feed-filter-chip-bar-renderer {
    display: none !important;
}

/* Base full viewport reset */
html, body {
    overflow: hidden !important;
    background-color: #000000 !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
}

/* Master Player Container Expansion */
#movie_player, .html5-video-player {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    max-width: 100vw !important;
    max-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    z-index: 9999 !important;
    background: #000000 !important;
}

/* Ensure Video Container fills the space correctly */
.html5-video-container {
    width: 100% !important;
    height: 100% !important;
}

.html5-video-container video {
    width: 100% !important;
    height: 100% !important;
    top: 0 !important;
    left: 0 !important;
    object-fit: contain !important;
}

/* Ensure Controls Bar, Settings Menu, Subtitles, and Seekbar are ON TOP and fully visible */
.ytp-chrome-bottom, .ytp-chrome-top, .ytp-gradient-bottom, .ytp-gradient-top, 
.ytp-popup, .ytp-settings-menu, .ytp-panel, .ytp-menuitem, .ytp-caption-window-container {
    z-index: 2000000000 !important;
}
"""

CONTROLS_CSS = """
/* Top control pill */
#antigravity-top-controls {
    position: fixed;
    top: 14px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 2147483647;
    pointer-events: none;
    display: flex;
    align-items: center;
    gap: 10px;
    opacity: 1;
    transition: opacity 0.4s ease, transform 0.3s ease;
}

#antigravity-top-controls.hidden {
    opacity: 0 !important;
    pointer-events: none !important;
    transform: translateX(-50%) translateY(-6px);
}

.ag-control-btn {
    pointer-events: auto;
    background: rgba(15, 23, 42, 0.92);
    color: #F8FAFC;
    border: 1px solid rgba(255, 255, 255, 0.25);
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    cursor: pointer;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.6);
    transition: all 0.2s ease;
    user-select: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.ag-control-btn:hover {
    background: #2563EB;
    color: #FFFFFF;
    border-color: #3B82F6;
    transform: scale(1.05);
}

.ag-control-btn:active {
    transform: scale(0.98);
}

.ag-download-btn {
    background: rgba(16, 185, 129, 0.92) !important;
    border-color: rgba(52, 211, 153, 0.5) !important;
    color: #FFFFFF !important;
}

.ag-download-btn:hover {
    background: #059669 !important;
    border-color: #10B981 !important;
    transform: scale(1.05);
}
"""

CINEMA_JS = r"""
(function() {
    try {
        // Controls Base Styling
        const controlsStyle = document.createElement('style');
        controlsStyle.type = 'text/css';
        controlsStyle.appendChild(document.createTextNode(`{controls_css}`));
        (document.head || document.documentElement).appendChild(controlsStyle);

        // Cinema Mode Dynamic Stylesheet
        let cinemaStyle = document.getElementById('antigravity-cinema-style');
        if (!cinemaStyle) {
            cinemaStyle = document.createElement('style');
            cinemaStyle.id = 'antigravity-cinema-style';
            cinemaStyle.type = 'text/css';
            cinemaStyle.appendChild(document.createTextNode(`{cinema_css}`));
            (document.head || document.documentElement).appendChild(cinemaStyle);
        }

        // Top Controls Container
        let controls = document.getElementById('antigravity-top-controls');
        if (!controls) {
            controls = document.createElement('div');
            controls.id = 'antigravity-top-controls';
            
            // 1. Maximize Screen Button
            const fsBtn = document.createElement('button');
            fsBtn.className = 'ag-control-btn';
            fsBtn.id = 'agFsBtn';
            fsBtn.textContent = '⛶ Maximize Screen';

            // 2. Switch to YouTube Web View Button
            const modeBtn = document.createElement('button');
            modeBtn.className = 'ag-control-btn';
            modeBtn.id = 'agModeBtn';
            modeBtn.textContent = '🌐 YouTube View';
            modeBtn.title = 'Switch between Cinema Mode and YouTube Web Interface';
            
            // 3. Download Current Video Button
            const dlBtn = document.createElement('button');
            dlBtn.className = 'ag-control-btn ag-download-btn';
            dlBtn.id = 'agDlBtn';
            dlBtn.textContent = '⬇️ Download Video';
            dlBtn.title = 'Download current video directly to your Downloads folder';

            controls.appendChild(fsBtn);
            controls.appendChild(modeBtn);
            controls.appendChild(dlBtn);
            document.body.appendChild(controls);
        }

        let isFull = false;
        let isCinema = window.location.search.includes('v=');
        let isHovered = false;
        let isDownloading = false;
        let hideTimer;
        
        const fsBtn = document.getElementById('agFsBtn');
        const modeBtn = document.getElementById('agModeBtn');
        const dlBtn = document.getElementById('agDlBtn');

        if (!isCinema && cinemaStyle) {
            cinemaStyle.disabled = true;
            if (modeBtn) {
                modeBtn.textContent = '🎬 Cinema View';
                modeBtn.style.background = 'rgba(37, 99, 235, 0.92)';
            }
        }


        function updateFullscreenState(state) {
            isFull = state;
            if (isFull) {
                fsBtn.textContent = '🗗 Exit Fullscreen (Esc)';
                fsBtn.style.background = 'rgba(220, 38, 38, 0.92)';
            } else {
                fsBtn.textContent = '⛶ Maximize Screen';
                fsBtn.style.background = 'rgba(15, 23, 42, 0.92)';
            }
        }

        if (fsBtn) {
            fsBtn.addEventListener('click', () => {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.toggle_fullscreen().then(updateFullscreenState);
                }
            });
        }

        if (modeBtn) {
            modeBtn.addEventListener('click', () => {
                isCinema = !isCinema;
                if (isCinema) {
                    cinemaStyle.disabled = false;
                    modeBtn.textContent = '🌐 YouTube View';
                    modeBtn.style.background = 'rgba(15, 23, 42, 0.92)';
                } else {
                    cinemaStyle.disabled = true;
                    modeBtn.textContent = '🎬 Cinema View';
                    modeBtn.style.background = 'rgba(37, 99, 235, 0.92)';
                }
            });
        }

        function getCleanVideoUrl() {
            try {
                const url = new URL(window.location.href);
                // 1. Standard YouTube Watch URL: extract strictly the video ID
                const v = url.searchParams.get('v');
                if (v && v.length >= 10) {
                    return 'https://www.youtube.com/watch?v=' + v;
                }
                
                // 2. YouTube Shorts
                if (url.pathname.includes('/shorts/')) {
                    const shortId = url.pathname.split('/shorts/')[1].split('/')[0].split('?')[0];
                    if (shortId) return 'https://www.youtube.com/watch?v=' + shortId;
                }
                
                // 3. YouTube Embed or youtu.be
                if (url.hostname.includes('youtu.be')) {
                    const shortId = url.pathname.replace(/^\//, '').split('?')[0];
                    if (shortId) return 'https://www.youtube.com/watch?v=' + shortId;
                }
                
                // 4. Non-YouTube URLs (Instagram, TikTok, Vimeo, Twitter, direct MP4)
                if (!url.hostname.includes('youtube.com')) {
                    return window.location.href;
                }
            } catch(e) {}
            return null;
        }

        if (dlBtn) {
            dlBtn.addEventListener('click', () => {
                if (isDownloading) return;
                const cleanUrl = getCleanVideoUrl();
                if (!cleanUrl) {
                    dlBtn.textContent = '⚠️ Play a video first!';
                    dlBtn.style.background = 'rgba(220, 38, 38, 0.92)';
                    setTimeout(() => {
                        if (dlBtn && !isDownloading) {
                            dlBtn.textContent = '⬇️ Download Video';
                            dlBtn.style.background = 'rgba(16, 185, 129, 0.92)';
                        }
                    }, 3000);
                    return;
                }

                isDownloading = true;
                dlBtn.textContent = '⏳ Adding to Queue...';
                dlBtn.style.background = 'rgba(234, 88, 12, 0.92)';
                
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.download_current_video(cleanUrl);
                }
            });
        }

        window.onDownloadComplete = function(success, msg) {
            isDownloading = false;
            if (dlBtn) {
                if (success) {
                    dlBtn.textContent = '✅ ' + (msg || 'Added to Queue!');
                    dlBtn.style.background = 'rgba(16, 185, 129, 0.92)';
                } else {
                    dlBtn.textContent = '⚠️ ' + (msg || 'Failed');
                    dlBtn.style.background = 'rgba(220, 38, 38, 0.92)';
                }
                setTimeout(() => {
                    if (dlBtn && !isDownloading) {
                        dlBtn.textContent = '⬇️ Download Video';
                        dlBtn.style.background = 'rgba(16, 185, 129, 0.92)';
                    }
                }, 3500);
            }
        };


        // 2-Second Inactivity Auto-Fade
        controls.addEventListener('mouseenter', () => {
            isHovered = true;
            controls.classList.remove('hidden');
            clearTimeout(hideTimer);
        });

        controls.addEventListener('mouseleave', () => {
            isHovered = false;
            resetTimer();
        });

        function resetTimer() {
            controls.classList.remove('hidden');
            clearTimeout(hideTimer);
            if (!isHovered) {
                hideTimer = setTimeout(() => {
                    controls.classList.add('hidden');
                }, 2000);
            }
        }

        window.addEventListener('mousemove', resetTimer);
        window.addEventListener('mousedown', resetTimer);
        resetTimer();

        // Auto-Play & Ad-Blocker Loop
        setInterval(() => {
            try {
                // Auto-skip video ads
                const skipBtn = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button');
                if (skipBtn) {
                    skipBtn.click();
                }
                const video = document.querySelector('video');
                const ad = document.querySelector('.ad-showing, .ad-interrupting');
                if (ad && video && !isNaN(video.duration)) {
                    video.currentTime = video.duration;
                }

                // Auto-unmute & play if paused at start
                if (video && video.paused && video.currentTime < 1) {
                    video.play().catch(() => {});
                }

                // Remove overlay promotions
                const overlays = document.querySelectorAll('.ytp-ad-overlay-container, ytd-banner-promo-renderer, ytd-popup-container');
                overlays.forEach(el => el.remove());
            } catch(e) {}
        }, 400);

    } catch(err) {
        console.error('Antigravity Cinema Init Error:', err);
    }
})();
"""

def on_loaded(window):
    """Inject cinema styling, view switcher, download button, and ad-stripper once YouTube page finishes loading"""
    cinema_css_sanitized = CINEMA_CSS.replace("`", "\\`").replace("\n", " ")
    controls_css_sanitized = CONTROLS_CSS.replace("`", "\\`").replace("\n", " ")
    js_payload = CINEMA_JS.replace("{cinema_css}", cinema_css_sanitized).replace("{controls_css}", controls_css_sanitized)
    window.evaluate_js(js_payload)

def main():
    global active_window
    if len(sys.argv) < 2:
        print("Usage: player_process.py <video_id> [title]")
        return
    
    video_id = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "Ad-Free Video Preview"
    
    # Support direct internet URLs from any website (Instagram, Twitter/X, TikTok, Vimeo, etc.)
    if video_id.startswith("http://") or video_id.startswith("https://"):
        watch_url = video_id
    else:
        watch_url = f"https://www.youtube.com/watch?v={video_id}"

    
    # Start physical ESC key listener
    start_esc_listener()
    
    api = PlayerApi()
    
    window = webview.create_window(
        title=f"🎬 StreamFlow Pro: {title[:50]}",
        url=watch_url,
        width=1040,
        height=650,
        resizable=True,
        text_select=False,
        zoomable=True,
        js_api=api
    )
    active_window = window
    
    # Bind page load to inject cinema UI, view switcher, and download button
    window.events.loaded += lambda: on_loaded(window)
    
    try:
        webview.start(private_mode=False)
    finally:
        pass

if __name__ == '__main__':
    main()
