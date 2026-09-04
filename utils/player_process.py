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

    def download_current_video(self, url_or_id, title=""):
        """Send current video download request to the main application queue"""
        global is_downloading
        try:
            target_url = str(url_or_id).strip() if url_or_id else ""
            video_title = str(title).strip() if title else ""
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
            db.add_to_inbox(target_url, title=video_title, download_type="video", quality="Best Available")
            logging.info(f"Queued single video download to main app: {target_url} ({video_title})")
            
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

# Global permanent ad-blocker styles applied in both Cinema and Web View
ADBLOCK_CSS = """
/* ==========================================================================
   StreamFlow Pro - Global Zero-Flicker AdBlock CSS Shield
   ========================================================================== */

/* Video Player Ad Overlays & Modules */
.ytp-ad-module, 
.video-ads, 
.ytp-ad-overlay-container, 
.ytp-ad-message-container,
.ytp-ad-action-interstitial,
.ytp-ad-preview-container,
.ytp-ad-feedback-dialog-container,
.ytp-ad-overlay-slot,
.ytp-ad-text-overlay,
.ytp-ad-image-overlay,
#player-ads {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    width: 0 !important;
    height: 0 !important;
}

/* Feed, Search, and Sidebar Sponsored Cards */
ytd-promoted-sparkles-web-renderer,
ytd-promoted-video-renderer,
ytd-display-ad-renderer,
ytd-statement-banner-renderer,
ytd-banner-promo-renderer,
ytd-in-feed-ad-layout-renderer,
ytd-ad-slot-renderer,
ytd-action-companion-ad-renderer,
#masthead-ad,
ytd-merch-shelf-renderer,
ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-ads"],
/* Brave procedural cosmetic filters for empty grid slots */
ytd-rich-item-renderer:has(ytd-ad-slot-renderer),
ytd-item-section-renderer:has(ytd-ad-slot-renderer),
ytd-rich-section-renderer:has(ytd-statement-banner-renderer) {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    height: 0 !important;
}

/* YouTube Anti-Adblock & Premium Nag Modals */
ytd-enforcement-message-view-model,
tp-yt-paper-dialog:has(ytd-enforcement-message-view-model),
tp-yt-paper-dialog:has(#feedback),
tp-yt-paper-dialog:has(yt-upsell-dialog-renderer),
yt-upsell-dialog-renderer,
ytd-mealbar-promo-renderer {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
"""

CINEMA_CSS = """
/* Hide external YouTube UI: headers, sidebar recommendations, comments in Cinema Mode */
#masthead-container, #masthead, #guide, #guide-wrapper, #secondary, #comments, 
#below, #chat, #ticker, #voice-search-button, #chips, ytd-feed-filter-chip-bar-renderer {
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
        // =========================================================================
        // BRAVE-STYLE JSON-PRUNING & PLAYER RESPONSE INTERCEPTION
        // Intercepts and prunes adPlacements / playerAds before the player loads ads
        // =========================================================================
        function cleanPlayerResponse(obj) {
            if (!obj || typeof obj !== 'object') return;
            
            // Delete root ad properties
            if ('adPlacements' in obj) delete obj.adPlacements;
            if ('playerAds' in obj) delete obj.playerAds;
            if ('adSlots' in obj) delete obj.adSlots;
            if ('adBreakHeartbeatParams' in obj) delete obj.adBreakHeartbeatParams;
            
            // Delete nested playerResponse ads
            if (obj.playerResponse && typeof obj.playerResponse === 'object') {
                if ('adPlacements' in obj.playerResponse) delete obj.playerResponse.adPlacements;
                if ('playerAds' in obj.playerResponse) delete obj.playerResponse.playerAds;
                if ('adSlots' in obj.playerResponse) delete obj.playerResponse.adSlots;
            }

            // Neutralize telemetry and ad playback beacons
            if (obj.playbackTracking && typeof obj.playbackTracking === 'object') {
                delete obj.playbackTracking.videostatsPlaybackUrl;
                delete obj.playbackTracking.videostatsDelayplayUrl;
                delete obj.playbackTracking.videostatsWatchtimeUrl;
                delete obj.playbackTracking.ptrackingUrl;
                delete obj.playbackTracking.qoeUrl;
            }
        }

        // 1. Intercept and prune window.ytInitialPlayerResponse
        try {
            if (window.ytInitialPlayerResponse) {
                cleanPlayerResponse(window.ytInitialPlayerResponse);
            }
            let _initialResponse = window.ytInitialPlayerResponse;
            Object.defineProperty(window, 'ytInitialPlayerResponse', {
                get() { return _initialResponse; },
                set(val) {
                    if (val && typeof val === 'object') {
                        cleanPlayerResponse(val);
                    }
                    _initialResponse = val;
                },
                configurable: true
            });
        } catch(e) {}

        // 2. Intercept window.fetch for /youtubei/v1/player (SPA video navigations)
        try {
            if (!window._fetchPatched) {
                window._fetchPatched = true;
                const originalFetch = window.fetch;
                window.fetch = async function(...args) {
                    const response = await originalFetch.apply(this, args);
                    const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
                    if (url && (url.includes('/youtubei/v1/player') || url.includes('/youtubei/v1/browse'))) {
                        try {
                            const clone = response.clone();
                            const json = await clone.json();
                            if (json && typeof json === 'object') {
                                cleanPlayerResponse(json);
                                return new Response(JSON.stringify(json), {
                                    status: response.status,
                                    statusText: response.statusText,
                                    headers: response.headers
                                });
                            }
                        } catch(err) {}
                    }
                    return response;
                };
            }
        } catch(e) {}

        // 3. Intercept XMLHttpRequest for /youtubei/v1/player
        try {
            if (!window._xhrPatched) {
                window._xhrPatched = true;
                const originalXHROpen = XMLHttpRequest.prototype.open;
                const originalXHRSend = XMLHttpRequest.prototype.send;
                
                XMLHttpRequest.prototype.open = function(method, url, ...rest) {
                    this._url = url;
                    return originalXHROpen.apply(this, [method, url, ...rest]);
                };
                
                XMLHttpRequest.prototype.send = function(...args) {
                    if (this._url && this._url.includes('/youtubei/v1/player')) {
                        this.addEventListener('readystatechange', function() {
                            if (this.readyState === 4 && this.status === 200) {
                                try {
                                    const parsed = JSON.parse(this.responseText);
                                    cleanPlayerResponse(parsed);
                                    Object.defineProperty(this, 'responseText', {
                                        value: JSON.stringify(parsed),
                                        writable: false,
                                        configurable: true
                                    });
                                    Object.defineProperty(this, 'response', {
                                        value: JSON.stringify(parsed),
                                        writable: false,
                                        configurable: true
                                    });
                                } catch(err) {}
                            }
                        });
                    }
                    return originalXHRSend.apply(this, args);
                };
            }
        } catch(e) {}

        // 4. Inject Permanent Global Ad-Blocker Stylesheet
        let adblockStyle = document.getElementById('antigravity-adblock-style');
        if (!adblockStyle) {
            adblockStyle = document.createElement('style');
            adblockStyle.id = 'antigravity-adblock-style';
            adblockStyle.type = 'text/css';
            adblockStyle.appendChild(document.createTextNode(`{adblock_css}`));
            (document.head || document.documentElement).appendChild(adblockStyle);
        }

        // 2. Inject Top Controls Styling
        let controlsStyle = document.getElementById('antigravity-controls-style');
        if (!controlsStyle) {
            controlsStyle = document.createElement('style');
            controlsStyle.id = 'antigravity-controls-style';
            controlsStyle.type = 'text/css';
            controlsStyle.appendChild(document.createTextNode(`{controls_css}`));
            (document.head || document.documentElement).appendChild(controlsStyle);
        }

        // 3. Inject Cinema Mode Stylesheet (Toggable)
        let cinemaStyle = document.getElementById('antigravity-cinema-style');
        if (!cinemaStyle) {
            cinemaStyle = document.createElement('style');
            cinemaStyle.id = 'antigravity-cinema-style';
            cinemaStyle.type = 'text/css';
            cinemaStyle.appendChild(document.createTextNode(`{cinema_css}`));
            (document.head || document.documentElement).appendChild(cinemaStyle);
        }

        // 4. Inject Top Controls Container
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
            if (fsBtn) {
                if (state) {
                    fsBtn.textContent = '🗗 Exit Fullscreen (Esc)';
                    fsBtn.style.background = 'rgba(220, 38, 38, 0.92)';
                } else {
                    fsBtn.textContent = '⛶ Maximize Screen';
                    fsBtn.style.background = 'rgba(15, 23, 42, 0.92)';
                }
            }
        }

        if (fsBtn) {
            fsBtn.onclick = () => {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.toggle_fullscreen().then(updateFullscreenState);
                }
            };
        }

        if (modeBtn) {
            modeBtn.onclick = () => {
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
            };
        }

        function getCleanVideoUrl() {
            try {
                // 1. Check active YouTube player API directly
                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                if (player && typeof player.getVideoData === 'function') {
                    const data = player.getVideoData();
                    if (data && data.video_id) {
                        return {
                            url: 'https://www.youtube.com/watch?v=' + data.video_id,
                            title: data.title || ''
                        };
                    }
                }

                // 2. Parse current URL
                const url = new URL(window.location.href);
                const v = url.searchParams.get('v');
                let pageTitle = '';
                const titleEl = document.querySelector('h1.ytd-video-primary-info-renderer, h1.ytd-watch-metadata, title');
                if (titleEl) pageTitle = titleEl.textContent.replace(' - YouTube', '').trim();

                if (v && v.length >= 10) {
                    return {
                        url: 'https://www.youtube.com/watch?v=' + v,
                        title: pageTitle
                    };
                }
                
                if (url.pathname.includes('/shorts/')) {
                    const shortId = url.pathname.split('/shorts/')[1].split('/')[0].split('?')[0];
                    if (shortId) return {
                        url: 'https://www.youtube.com/watch?v=' + shortId,
                        title: pageTitle
                    };
                }
                
                if (url.hostname.includes('youtu.be')) {
                    const shortId = url.pathname.replace(/^\//, '').split('?')[0];
                    if (shortId) return {
                        url: 'https://www.youtube.com/watch?v=' + shortId,
                        title: pageTitle
                    };
                }
                
                if (!url.hostname.includes('youtube.com')) {
                    return {
                        url: window.location.href,
                        title: document.title || ''
                    };
                }
            } catch(e) {}
            return null;
        }

        if (dlBtn) {
            dlBtn.onclick = () => {
                if (isDownloading) return;
                const videoInfo = getCleanVideoUrl();
                if (!videoInfo || !videoInfo.url) {
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
                
                const triggerDownload = () => {
                    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.download_current_video === 'function') {
                        window.pywebview.api.download_current_video(videoInfo.url, videoInfo.title);
                    } else if (window.pywebviewApi && typeof window.pywebviewApi.download_current_video === 'function') {
                        window.pywebviewApi.download_current_video(videoInfo.url, videoInfo.title);
                    } else {
                        // Fallback retry in case bridge is still hooking
                        setTimeout(() => {
                            if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.download_current_video === 'function') {
                                window.pywebview.api.download_current_video(videoInfo.url, videoInfo.title);
                            } else {
                                isDownloading = false;
                                dlBtn.textContent = '⚠️ Bridge Connecting...';
                                dlBtn.style.background = 'rgba(220, 38, 38, 0.92)';
                                setTimeout(() => {
                                    if (dlBtn && !isDownloading) {
                                        dlBtn.textContent = '⬇️ Download Video';
                                        dlBtn.style.background = 'rgba(16, 185, 129, 0.92)';
                                    }
                                }, 2500);
                            }
                        }, 300);
                    }
                };

                triggerDownload();
            };
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

        // 2-Second Inactivity Auto-Fade for Top Controls
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

        // =========================================================================
        // HIGH-QUALITY SEAMLESS AD-BLOCKER & ANTI-DETECTION ENGINE
        // =========================================================================
        let isAdActive = false;
        let originalPlaybackRate = 1.0;
        let originalMuted = false;

        function processAdBlocker() {
            try {
                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                const video = document.querySelector('video');

                // Intercept and sanitize internal player args
                if (player && typeof player.getConfig === 'function') {
                    try {
                        const cfg = player.getConfig();
                        if (cfg && cfg.args) {
                            cleanPlayerResponse(cfg.args);
                        }
                    } catch(err) {}
                }

                // 1. Detect if an ad is actively playing
                const hasAdClass = player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'));
                const hasAdOverlay = !!document.querySelector('.ytp-ad-player-overlay, .ytp-ad-player-overlay-layout');
                const isAdPlaying = hasAdClass || hasAdOverlay;

                if (isAdPlaying && video) {
                    if (!isAdActive) {
                        isAdActive = true;
                        if (video.playbackRate >= 0.25 && video.playbackRate <= 3.0) {
                            originalPlaybackRate = video.playbackRate;
                        }
                        originalMuted = video.muted;
                    }

                    // A. Mute instantly so high-speed ad audio is completely silent
                    video.muted = true;

                    // B. Accelerate ad to 16x speed (HTML5 spec max)
                    // At 16x, ads complete smoothly in < 0.9s without triggering buffer crashes or anti-adblock bans
                    if (video.playbackRate !== 16.0) {
                        video.playbackRate = 16.0;
                    }

                    // C. Auto-click any skip button the instant it appears
                    const skipSelectors = [
                        '.ytp-ad-skip-button',
                        '.ytp-ad-skip-button-modern',
                        '.ytp-skip-ad-button',
                        '.ytp-ad-skip-button-slot button',
                        '.ytp-ad-skip-button-container button',
                        'button[class*="ytp-ad-skip"]'
                    ];
                    for (const sel of skipSelectors) {
                        const skipBtn = document.querySelector(sel);
                        if (skipBtn && typeof skipBtn.click === 'function') {
                            skipBtn.click();
                            break;
                        }
                    }

                    // D. Safe skip: If the video is confirmed to be an ad stream and duration is short (< 120s),
                    // smoothly nudge near the end without crashing the player state
                    if (!isNaN(video.duration) && video.duration > 0 && video.duration < 120) {
                        if (video.currentTime < video.duration - 0.2) {
                            video.currentTime = video.duration - 0.05;
                        }
                    }
                } else {
                    // Normal video playing
                    if (isAdActive) {
                        isAdActive = false;
                        // Clean restoration of user's genuine playback rate and volume
                        if (video) {
                            video.playbackRate = originalPlaybackRate || 1.0;
                            video.muted = originalMuted;
                        }
                    }
                }

                // 2. Auto-dismiss YouTube Anti-Adblock Warning Modals & "Continue Watching" dialogs
                const dismissSelectors = [
                    'ytd-enforcement-message-view-model #dismiss-button button',
                    'tp-yt-paper-dialog:has(ytd-enforcement-message-view-model) #dismiss-button button',
                    'tp-yt-paper-dialog #dismiss-button button',
                    'yt-confirm-dialog-renderer #confirm-button button',
                    '.ytp-ad-overlay-close-button'
                ];
                for (const dSel of dismissSelectors) {
                    const dBtn = document.querySelector(dSel);
                    if (dBtn && typeof dBtn.click === 'function') {
                        dBtn.click();
                    }
                }

                // Remove anti-adblock modal containers if they appear
                const antiAdModals = document.querySelectorAll('ytd-enforcement-message-view-model, tp-yt-paper-dialog:has(ytd-enforcement-message-view-model)');
                antiAdModals.forEach(m => m.remove());

                // 3. Remove non-video promotional overlays
                const promoOverlays = document.querySelectorAll('.ytp-ad-overlay-container, ytd-banner-promo-renderer, ytd-popup-container:has(yt-upsell-dialog-renderer)');
                promoOverlays.forEach(el => el.remove());

            } catch(e) {}
        }

        // Hook MutationObserver for instantaneous 0-millisecond reaction
        const targetNode = document.documentElement || document.body;
        const observer = new MutationObserver(() => {
            processAdBlocker();
        });
        observer.observe(targetNode, {
            attributes: true,
            attributeFilter: ['class', 'style'],
            childList: true,
            subtree: true
        });

        // Backup high-frequency interval to catch stream changes reliably
        setInterval(processAdBlocker, 80);

        // Keep active across Single Page Application (SPA) YouTube video navigations
        window.addEventListener('yt-navigate-finish', () => {
            isAdActive = false;
            processAdBlocker();
        });

    } catch(err) {
        console.error('Antigravity Cinema Init Error:', err);
    }
})();
"""

def on_loaded(window):
    """Inject permanent adblock CSS shield, cinema styling, view switcher, and stealth ad-blocker engine"""
    adblock_css_sanitized = ADBLOCK_CSS.replace("`", "\\`").replace("\n", " ")
    cinema_css_sanitized = CINEMA_CSS.replace("`", "\\`").replace("\n", " ")
    controls_css_sanitized = CONTROLS_CSS.replace("`", "\\`").replace("\n", " ")
    js_payload = CINEMA_JS.replace("{adblock_css}", adblock_css_sanitized).replace("{cinema_css}", cinema_css_sanitized).replace("{controls_css}", controls_css_sanitized)
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
