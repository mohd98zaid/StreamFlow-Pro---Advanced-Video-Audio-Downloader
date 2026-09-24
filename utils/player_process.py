import sys
import os
import re
import threading
import ctypes
import time
import json
import urllib.request
import urllib.parse
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
try:
    from utils.studio_assets import STUDIO_ASSETS
except ImportError:
    try:
        from studio_assets import STUDIO_ASSETS
    except ImportError:
        STUDIO_ASSETS = {}

active_window = None
current_download_lock = threading.Lock()
is_downloading = False
_recs_cache = {}

def clean_track_info(title, artist=""):
    """Prunes raw YouTube junk from title/artist and extracts genuine track info"""
    raw_title = str(title or "").strip()
    raw_artist = str(artist or "").strip()
    t = raw_title
    
    # Strip emojis and symbols
    t = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]', '', t)
    
    t = re.sub(r'^(?:full\s*song|video\s*song|official\s*(?:video|audio|music)|lyrical(?:\s*video)?|audio\s*song)[\s_:–\-—]+', '', t, flags=re.I)
    t = re.sub(r'[\(\[\{]+\s*(?:official\s*(?:music\s*)?(?:video|audio|song|lyric|visualizer|hd|4k|uhd)?|full\s*(?:song|video|audio)|video\s*song|audio\s*song|lyrics?|lyric\s*video|visualizer|remastered|extended|hq|audio|4k|1080p|hd|uhd|hdr|60fps|8k|prod\.[^\)\]\}]+|jhankaar[^\)\]\}]*)\s*[\)\]\}]+', '', t, flags=re.I)
    t = re.sub(r'[\(\[\{]\s*[\)\]\}]', '', t)
    t = re.sub(r'\s*M\/V$', '', t, flags=re.I)
    t = re.sub(r'\s*MV$', '', t, flags=re.I)

    if '|' in t:
        parts = [p.strip() for p in t.split('|') if p.strip()]
        if len(parts) > 1:
            t = parts[0]
            if (not raw_artist or raw_artist in ["YouTube Music", "Studio Audio"] or raw_artist.startswith('@')):
                potential = parts[1]
                if not re.search(r'official|video|audio|lyrics|t-series|sony|music|record', potential, re.I):
                    raw_artist = potential

    t = re.sub(r'\s*-\s*(?:official\s*)?(?:lyric\s*video|music\s*video|audio\s*video|lyric|video|audio|full\s*song).*$', '', t, flags=re.I)
    t = re.sub(r'\s+(?:full\s*song(?:\s*with\s*lyrics)?|video\s*song(?:\s*with\s*lyrics)?|full\s*video(?:\s*song)?|audio\s*song|song\s*with\s*lyrics|8k\/4k\s*mus.*)$', '', t, flags=re.I)
    t = re.sub(r' (?:full\s*song|video\s*song|official\s*music) ', '', t, flags=re.I)
    t = re.sub(r'__+', ' ', t)
    t = re.sub(r'--+', '-', t)
    t = re.sub(r'[_]+', ' ', t)
    t = re.sub(r'^[\s"\'\-]+|[\s"\'\-]+$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()

    a = raw_artist
    a = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]', '', a)
    a = re.sub(r'^@+', '', a)
    a = re.sub(r'\s*-\s*Topic$', '', a, flags=re.I)
    a = re.sub(r'VEVO$', '', a, flags=re.I)
    a = re.sub(r'\s*(?:official\s*(?:channel|artist\s*channel|music|audio)?)$', '', a, flags=re.I)
    a = re.sub(r'\s+', ' ', a).strip()

    if (not a or a in ["YouTube Music", "Studio Audio", "Various Artists", "Various"]) and (' - ' in t or ' : ' in t):
        sep = ' - ' if ' - ' in t else ' : '
        parts = [p.strip() for p in t.split(sep, 1)]
        if len(parts) == 2 and len(parts[0]) > 1 and len(parts[1]) > 1:
            if re.search(r'feat|ft\.|trivedi|singh|kumar|khan|sharma|shreya|arijit|armaan|sonu|king|divine|pritam|badshah|honey|rahman', parts[1], re.I):
                t = parts[0]
                a = parts[1]
            elif re.search(r'feat|ft\.|trivedi|singh|kumar|khan|sharma|shreya|arijit|armaan|sonu|king|divine|pritam|badshah|honey|rahman', parts[0], re.I):
                a = parts[0]
                t = parts[1]
            else:
                t = parts[0]
                a = parts[1]

    if t.isupper() and len(t) > 6:
        t = t.title()

    if not a or a in ["YouTube Music", "Studio Audio"]:
        a = "Original Artist"

    return t or raw_title, a


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

    def download_current_video(self, url_or_id, title="", download_type="video"):
        """Send current video or audio download request to the main application queue"""
        global is_downloading
        try:
            target_url = str(url_or_id).strip() if url_or_id else ""
            video_title = str(title).strip() if title else ""
            dl_type = "audio" if str(download_type).lower() == "audio" else "video"
            if not target_url:
                if active_window:
                    active_window.evaluate_js("if(window.onDownloadComplete) window.onDownloadComplete(false, 'Play a track first!');")
                return {"status": "error", "message": "Play a track first"}
            
            # If YouTube URL, extract strictly the single video ID
            if "youtube.com" in target_url or "youtu.be" in target_url:
                v_match = re.search(r'(?:v=|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', target_url)
                if v_match:
                    target_url = f"https://www.youtube.com/watch?v={v_match.group(1)}"
                else:
                    if active_window:
                        active_window.evaluate_js("if(window.onDownloadComplete) window.onDownloadComplete(false, 'Play a track first!');")
                    return {"status": "error", "message": "Play a track first"}
            
            # Send to SQLite inbox_queue so the main application active queue picks it up immediately
            db = DatabaseManager()
            db.add_to_inbox(target_url, title=video_title, download_type=dl_type, quality="Best Available")
            logging.info(f"Queued single {dl_type} download to main app: {target_url} ({video_title})")
            
            success_msg = "Added MP3 to Queue!" if dl_type == "audio" else "Added to Download Queue!"
            if active_window:
                active_window.evaluate_js(f"if(window.onDownloadComplete) window.onDownloadComplete(true, '{success_msg}');")
            
            return {"status": "queued", "message": success_msg}
        except Exception as e:
            logging.error(f"Error queueing player download: {e}")
            if active_window:
                clean_msg = str(e).replace("'", "").replace('"', '')[:30]
                active_window.evaluate_js(f"if(window.onDownloadComplete) window.onDownloadComplete(false, '{clean_msg}');")
            return {"status": "error", "message": str(e)}




    def request_song_recommendations(self, video_id=None, query=None):
        """Asynchronously trigger song recommendations and push to window.onSongRecommendations"""
        def _bg():
            try:
                self.get_song_recommendations(video_id, query)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()
        return True

    def get_song_recommendations(self, video_id=None, query=None):
        """Fetch high quality music recommendations based on current video ID and title/artist"""
        global _recs_cache
        key = (str(video_id).strip() if video_id else "") or (str(query).strip() if query else "") or "default"
        now = time.time()
        if key in _recs_cache and (now - _recs_cache[key]["time"] < 300):
            data = _recs_cache[key]["data"]
            if active_window:
                try:
                    safe_json = json.dumps(data).replace('\\', '\\\\').replace("'", "\\'")
                    active_window.evaluate_js(f"if(window.onSongRecommendations) window.onSongRecommendations(JSON.parse('{safe_json}'));")
                except Exception:
                    pass
            return {"status": "success", "tracks": data, "source": "cache"}

        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }

        try:
            if video_id and len(str(video_id).strip()) >= 10:
                target_url = f"https://www.youtube.com/watch?v={str(video_id).strip()}"
            elif query:
                target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(str(query).strip())}"
            else:
                target_url = "https://www.youtube.com/feed/trending?bp=4gINGgt5dG1hX2NoYXJ0cw%3D%3D"

            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=4.5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                m = re.search(r'var ytInitialData\s*=\s*({.+?});</script>', html)
                if not m:
                    m = re.search(r'ytInitialData\s*=\s*({.+?});', html)
                if m:
                    data = json.loads(m.group(1))
                    contents = data.get("contents", {})

                    # 1. Watch page related results (lockupViewModel & compactVideoRenderer)
                    sec = contents.get("twoColumnWatchNextResults", {}).get("secondaryResults", {})
                    res_list = sec.get("secondaryResults", {}).get("results", [])
                    for r in res_list:
                        if "itemSectionRenderer" in r:
                            for it in r["itemSectionRenderer"].get("contents", []):
                                vm = it.get("lockupViewModel")
                                if vm and vm.get("contentId"):
                                    vid = vm.get("contentId")
                                    lmd = vm.get("metadata", {}).get("lockupMetadataViewModel", {})
                                    title = lmd.get("title", {}).get("content", "")
                                    cmd = lmd.get("metadata", {}).get("contentMetadataViewModel", {})
                                    rows = cmd.get("metadataRows", []) or lmd.get("metadataRows", [])
                                    author = ""
                                    if rows and rows[0].get("metadataParts"):
                                        author = " • ".join([p.get("text", {}).get("content", "") for p in rows[0].get("metadataParts", []) if p.get("text", {}).get("content")])
                                    dur = ""
                                    # Extract duration from thumbnail overlays
                                    for ov in vm.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", []):
                                        for b in ov.get("thumbnailBottomOverlayViewModel", {}).get("badges", []):
                                            t_str = b.get("thumbnailBadgeViewModel", {}).get("text")
                                            if t_str:
                                                dur = t_str
                                                break
                                    if not dur and len(rows) > 1 and rows[1].get("metadataParts"):
                                        dur = " • ".join([p.get("text", {}).get("content", "") for p in rows[1].get("metadataParts", []) if p.get("text", {}).get("content")])
                                    if vid and title and vid != video_id:
                                        clean_t, clean_a = clean_track_info(title, author)
                                        results.append({
                                            "id": vid,
                                            "title": clean_t,
                                            "artist": clean_a,
                                            "duration": dur or "3:30",
                                            "thumb": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                                            "url": f"https://www.youtube.com/watch?v={vid}"
                                        })
                                c = it.get("compactVideoRenderer")
                                if c and c.get("videoId"):
                                    vid = c.get("videoId")
                                    title = c.get("title", {}).get("simpleText") or (c.get("title", {}).get("runs", [{}])[0].get("text") if "runs" in c.get("title", {}) else "")
                                    author = c.get("shortBylineText", {}).get("runs", [{}])[0].get("text", "") if "runs" in c.get("shortBylineText", {}) else ""
                                    dur = c.get("lengthText", {}).get("simpleText", "")
                                    if vid and title and vid != video_id:
                                        clean_t, clean_a = clean_track_info(title, author)
                                        results.append({
                                            "id": vid,
                                            "title": clean_t,
                                            "artist": clean_a,
                                            "duration": dur or "3:30",
                                            "thumb": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                                            "url": f"https://www.youtube.com/watch?v={vid}"
                                        })

                    # 2. Search results page
                    prim = contents.get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {})
                    sec_items = prim.get("sectionListRenderer", {}).get("contents", [])
                    for s in sec_items:
                        for it in s.get("itemSectionRenderer", {}).get("contents", []):
                            vr = it.get("videoRenderer")
                            if vr and vr.get("videoId"):
                                vid = vr.get("videoId")
                                title = vr.get("title", {}).get("runs", [{}])[0].get("text", "") if "runs" in vr.get("title", {}) else vr.get("title", {}).get("simpleText", "")
                                author = vr.get("ownerText", {}).get("runs", [{}])[0].get("text", "") if "runs" in vr.get("ownerText", {}) else ""
                                dur = vr.get("lengthText", {}).get("simpleText", "")
                                if vid and title and vid != video_id:
                                    clean_t, clean_a = clean_track_info(title, author)
                                    results.append({
                                        "id": vid,
                                        "title": clean_t,
                                        "artist": clean_a,
                                        "duration": dur or "3:30",
                                        "thumb": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                                        "url": f"https://www.youtube.com/watch?v={vid}"
                                    })
        except Exception as e:
            logging.error(f"Error fetching song recommendations: {e}")

        _recs_cache[key] = {"time": time.time(), "data": results[:20]}
        if active_window:
            try:
                safe_json = json.dumps(results[:20]).replace('\\', '\\\\').replace("'", "\\'")
                active_window.evaluate_js(f"if(window.onSongRecommendations) window.onSongRecommendations(JSON.parse('{safe_json}'));")
            except Exception:
                pass
        return {"status": "success", "tracks": results[:20], "source": "network"}


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
    gap: 8px;
    opacity: 1;
    transition: opacity 0.4s ease, transform 0.3s ease;
    max-width: 96vw;
    flex-wrap: wrap;
    justify-content: center;
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
    padding: 6px 14px;
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
    white-space: nowrap;
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

.ag-music-btn:hover {
    background: #E11D48 !important;
    border-color: #FB7185 !important;
}

.ag-download-btn {
    background: rgba(16, 185, 129, 0.92) !important;
    border-color: rgba(52, 211, 153, 0.5) !important;
    color: #FFFFFF !important;
}

.ag-download-btn:hover {
    background: #059669 !important;
}

.ag-studio-btn {
    background: linear-gradient(135deg, #0284C7, #06B6D4) !important;
    border-color: rgba(6, 182, 212, 0.6) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 16px rgba(6, 182, 212, 0.4);
}

.ag-studio-btn:hover {
    background: linear-gradient(135deg, #0EA5E9, #22D3EE) !important;
    box-shadow: 0 0 20px rgba(34, 211, 238, 0.7) !important;
}
"""

STUDIO_MUSIC_CSS = """/* ==========================================================================
   StreamFlow Studio - YumaPlayer Architecture (UI/UX Pro Max Edition)
   ========================================================================== */

@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root, #antigravity-studio-music {
    --ambient-bg: #080a12;
    --ambient-color-1: rgba(190, 90, 20, 0.45);
    --ambient-color-2: rgba(30, 64, 175, 0.45);
    --yuma-accent: #38bdf8;
    --text-main: #ffffff;
    --text-sub: rgba(255, 255, 255, 0.65);
}

#antigravity-studio-music {
    position: fixed !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    z-index: 2147483640 !important;
    background: var(--ambient-bg) !important;
    color: #ffffff !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    display: none;
    flex-direction: column !important;
    overflow: hidden !important;
    user-select: none !important;
    -webkit-user-select: none !important;
    box-sizing: border-box !important;
    -webkit-font-smoothing: antialiased !important;
}

#antigravity-studio-music.active {
    display: flex !important;
}

#antigravity-studio-music * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

#antigravity-studio-music button {
    border: none;
    outline: none;
    background: none;
    font-family: inherit;
    cursor: pointer;
}

/* Ambient Lighting Gradient */
.ag-sm-ambient-mesh {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
}
.ag-sm-ambient-mesh::before {
    content: '';
    position: absolute;
    width: 50vw;
    height: 55vh;
    top: -10%;
    left: -5%;
    background: radial-gradient(circle, var(--ambient-color-1) 0%, transparent 70%);
    filter: blur(100px);
    opacity: 0.9;
    transition: all 1.2s ease;
}
.ag-sm-ambient-mesh::after {
    content: '';
    position: absolute;
    width: 45vw;
    height: 50vh;
    bottom: -5%;
    right: 5%;
    background: radial-gradient(circle, var(--ambient-color-2) 0%, transparent 70%);
    filter: blur(110px);
    opacity: 0.8;
    transition: all 1.2s ease;
}

/* Custom Scrollbars */
#antigravity-studio-music ::-webkit-scrollbar {
    width: 5px;
}
#antigravity-studio-music ::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
}
#antigravity-studio-music ::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.22);
}
#antigravity-studio-music ::-webkit-scrollbar-track {
    background: transparent;
}

/* TOP NAVIGATION BAR */
.ag-sm-header {
    height: 54px;
    background: rgba(9, 12, 20, 0.6);
    backdrop-filter: blur(32px) saturate(160%);
    -webkit-backdrop-filter: blur(32px) saturate(160%);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    z-index: 50;
    position: relative;
    flex-shrink: 0;
}

.ag-sm-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.ag-sm-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
}
.ag-sm-brand-icon {
    display: flex;
    align-items: flex-end;
    gap: 2.5px;
    height: 18px;
}
.ag-sm-brand-icon span {
    width: 2.5px;
    background: linear-gradient(to top, #38bdf8, #818cf8);
    border-radius: 2px;
    animation: agEqDance 1.2s ease-in-out infinite alternate;
}
.ag-sm-brand-icon span:nth-child(1) { height: 8px; animation-delay: 0.1s; }
.ag-sm-brand-icon span:nth-child(2) { height: 16px; animation-delay: 0.3s; }
.ag-sm-brand-icon span:nth-child(3) { height: 13px; animation-delay: 0.2s; }
.ag-sm-brand-icon span:nth-child(4) { height: 18px; animation-delay: 0.4s; }
.ag-sm-brand-icon span:nth-child(5) { height: 7px; animation-delay: 0.15s; }

@keyframes agEqDance {
    0% { height: 4px; }
    100% { height: 18px; }
}

.ag-sm-brand-text {
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.3px;
}

.ag-sm-header-center {
    flex: 1;
    display: flex;
    justify-content: center;
}

.ag-sm-search-capsule {
    width: 380px;
    height: 34px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 9999px;
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 10px;
    backdrop-filter: blur(16px);
    transition: all 0.2s ease;
}
.ag-sm-search-capsule:focus-within {
    border-color: rgba(255, 255, 255, 0.28);
    background: rgba(255, 255, 255, 0.09);
    box-shadow: 0 0 16px rgba(255, 255, 255, 0.08);
    width: 420px;
}
.ag-sm-search-capsule svg {
    color: #94a3b8;
    flex-shrink: 0;
}
.ag-sm-search-capsule input {
    background: transparent;
    border: none;
    outline: none;
    color: #ffffff;
    font-size: 12.5px;
    width: 100%;
    font-family: inherit;
}
.ag-sm-search-capsule input::placeholder {
    color: #64748b;
}

.ag-sm-header-right {
    display: flex;
    align-items: center;
    gap: 10px;
}

.ag-sm-hdr-btn {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border-radius: 9999px;
    padding: 6px 14px;
    font-size: 11.5px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    backdrop-filter: blur(12px);
    transition: all 0.2s ease;
}
.ag-sm-hdr-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.2);
}
.ag-sm-hdr-video {
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.35);
    color: #7dd3fc;
}
.ag-sm-hdr-video:hover {
    background: rgba(56, 189, 248, 0.24);
    color: #ffffff;
}
.ag-sm-hdr-icon-btn {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #94a3b8;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    backdrop-filter: blur(12px);
    transition: all 0.2s ease;
}
.ag-sm-hdr-icon-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
}

/* MAIN CONTENT STAGE */
.ag-sm-content-stage {
    flex: 1;
    display: flex;
    overflow: hidden;
    position: relative;
    z-index: 10;
}

/* =========================================================================
   LEFT COLUMN: PROPORTIONAL YUMA FULL PLAYER
   ========================================================================= */
.ag-sm-left-player {
    width: 420px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 14px 30px 12px 30px;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(8, 10, 18, 0.45);
    backdrop-filter: blur(36px);
    -webkit-backdrop-filter: blur(36px);
    overflow: hidden;
}

.ag-sm-art-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 0;
    margin: 2px 0 8px 0;
}
.ag-sm-art-img {
    width: clamp(160px, 30vh, 220px);
    height: clamp(160px, 30vh, 220px);
    aspect-ratio: 1 / 1;
    object-fit: cover;
    border-radius: 26px;
    box-shadow: 0 20px 48px rgba(0, 0, 0, 0.8), 0 0 45px var(--ambient-color-1);
    border: 1px solid rgba(255, 255, 255, 0.12);
    transition: transform 0.3s ease;
}
.ag-sm-art-wrap:hover .ag-sm-art-img {
    transform: scale(1.02);
}

.ag-sm-info-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
    flex-shrink: 0;
}
.ag-sm-info-text {
    flex: 1;
    min-width: 0;
    padding-right: 14px;
}
.ag-sm-hero-title {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    letter-spacing: -0.3px;
}
.ag-sm-hero-artist {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--text-sub);
    margin-top: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.ag-sm-heart-btn {
    color: rgba(255, 255, 255, 0.7);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.2s ease, color 0.2s ease;
    flex-shrink: 0;
}
.ag-sm-heart-btn:hover, .ag-sm-heart-btn.liked {
    color: #ec4899;
    transform: scale(1.15);
}

/* Seekbar */
.ag-sm-seek-wrap {
    margin-bottom: 6px;
    flex-shrink: 0;
}
.ag-sm-slider {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 4.5px;
    border-radius: 9999px;
    background: linear-gradient(to right, #ffffff 28%, rgba(255, 255, 255, 0.18) 28%);
    outline: none;
    cursor: pointer;
    transition: height 0.15s ease;
}
.ag-sm-slider:hover {
    height: 6px;
}
.ag-sm-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.8);
    cursor: pointer;
}

.ag-sm-meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-sub);
    font-variant-numeric: tabular-nums;
    margin-bottom: 10px;
    flex-shrink: 0;
}
.ag-sm-badge-capsule {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 3px 12px;
    border-radius: 9999px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(12px);
    font-size: 10.5px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.85);
    letter-spacing: 0.4px;
}

/* Floating Transport Capsule */
.ag-sm-transport-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
    flex-shrink: 0;
}
.ag-sm-flank-btn {
    color: rgba(255, 255, 255, 0.65);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.2s ease, transform 0.2s ease;
    width: 36px;
    height: 36px;
}
.ag-sm-flank-btn:hover {
    color: #ffffff;
    transform: scale(1.12);
}

.ag-sm-transport-capsule {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 22px;
    background: rgba(255, 255, 255, 0.16);
    backdrop-filter: blur(32px);
    -webkit-backdrop-filter: blur(32px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 9999px;
    padding: 5px 24px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}
.ag-sm-trans-btn {
    color: #ffffff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.18s ease;
}
.ag-sm-trans-btn:hover {
    transform: scale(1.15);
}

/* PURE SOLID WHITE CIRCULAR PLAY BUTTON (YUMA SIGNATURE) */
#antigravity-studio-music .ag-sm-play-circle {
    width: 52px !important;
    height: 52px !important;
    border-radius: 50% !important;
    background: #ffffff !important;
    color: #080a12 !important;
    border: none !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45), 0 0 16px rgba(255, 255, 255, 0.4) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}
#antigravity-studio-music .ag-sm-play-circle svg {
    fill: #080a12 !important;
    color: #080a12 !important;
}
#antigravity-studio-music .ag-sm-play-circle:hover {
    transform: scale(1.08) !important;
    box-shadow: 0 8px 28px rgba(255, 255, 255, 0.65) !important;
}
#antigravity-studio-music .ag-sm-play-circle:active {
    transform: scale(0.95) !important;
}

.ag-sm-bottom-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 26px;
    flex-shrink: 0;
    padding: 0 4px;
}
.ag-sm-sheet-btn {
    color: rgba(255, 255, 255, 0.65);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.2s ease, transform 0.2s ease;
}
.ag-sm-sheet-btn:hover {
    color: #ffffff;
    transform: scale(1.12);
}
.ag-sm-drag-handle {
    width: 44px;
    height: 4px;
    background: rgba(255, 255, 255, 0.28);
    border-radius: 9999px;
}

/* =========================================================================
   RIGHT COLUMN: YUMA QUICK PICKS & QUEUE
   ========================================================================= */
.ag-sm-right-stage {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 16px 26px 20px 26px;
    gap: 14px;
}

/* Mood Filter Chips */
.ag-sm-chips-row {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow-x: auto;
    flex-shrink: 0;
    padding-bottom: 2px;
}
#antigravity-studio-music .ag-sm-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 6px 18px;
    border-radius: 9999px;
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.10);
    color: rgba(255, 255, 255, 0.75);
    font-size: 12px;
    font-weight: 600;
    line-height: 1.2;
    cursor: pointer;
    backdrop-filter: blur(12px);
    white-space: nowrap;
    transition: all 0.2s ease;
}
#antigravity-studio-music .ag-sm-chip:hover {
    background: rgba(255, 255, 255, 0.14);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.18);
}
#antigravity-studio-music .ag-sm-chip.active {
    background: #ffffff !important;
    color: #080a12 !important;
    border-color: #ffffff !important;
    font-weight: 700;
    box-shadow: 0 2px 14px rgba(255, 255, 255, 0.3) !important;
}

.ag-sm-sec-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2px;
}
.ag-sm-sec-title {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.3px;
}
.ag-sm-sec-sub {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-sub);
}

/* Tactile Queue Cards */
.ag-sm-queue-list {
    display: flex;
    flex-direction: column;
    gap: 7px;
}

.ag-sm-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 14px;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.06);
    backdrop-filter: blur(16px);
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.ag-sm-card:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.16);
    transform: translateX(4px);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}
.ag-sm-card.active-playing {
    background: rgba(56, 189, 248, 0.08);
    border-color: rgba(56, 189, 248, 0.35);
    box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.15), 0 4px 20px rgba(56, 189, 248, 0.18), 0 4px 16px rgba(0, 0, 0, 0.35);
    animation: agActiveCardPulse 2.8s ease-in-out infinite;
    position: relative;
}
.ag-sm-card.active-playing::before {
    content: '';
    position: absolute;
    left: 0;
    top: 20%;
    bottom: 20%;
    width: 3px;
    background: var(--yuma-accent);
    border-radius: 0 3px 3px 0;
    box-shadow: 0 0 8px rgba(56, 189, 248, 0.8);
}

@keyframes agActiveCardPulse {
    0%, 100% { box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.15), 0 4px 20px rgba(56, 189, 248, 0.18), 0 4px 16px rgba(0, 0, 0, 0.35); }
    50% { box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.28), 0 6px 28px rgba(56, 189, 248, 0.32), 0 4px 16px rgba(0, 0, 0, 0.35); }
}

@media (prefers-reduced-motion: reduce) {
    .ag-sm-card.active-playing { animation: none !important; }
    .ag-sm-brand-icon span { animation: none !important; }
    .ag-sm-ambient-mesh::before, .ag-sm-ambient-mesh::after { transition: none !important; }
}

.ag-sm-card-thumb {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    overflow: hidden;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}
.ag-sm-card-thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.ag-sm-card-info {
    flex: 1;
    min-width: 0;
}
.ag-sm-card-title {
    font-size: 13.5px;
    font-weight: 600;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    letter-spacing: 0.1px;
    line-height: 1.4;
}
.ag-sm-card-artist {
    font-size: 11.5px;
    color: var(--text-sub);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.4;
}

.ag-sm-card-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
}
.ag-sm-card-dur {
    font-size: 11.5px;
    font-weight: 500;
    color: var(--text-sub);
    font-variant-numeric: tabular-nums;
}

/* Tactile Pill Download Button */
.ag-sm-card-dl-btn {
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #ffffff;
    border-radius: 9999px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: all 0.18s ease;
}
.ag-sm-card-dl-btn svg {
    color: rgba(255, 255, 255, 0.7);
    transition: transform 0.15s ease, color 0.15s ease;
}
.ag-sm-card-dl-btn:hover {
    background: #ffffff;
    color: #080a12;
    border-color: #ffffff;
    transform: scale(1.04);
}
.ag-sm-card-dl-btn:hover svg {
    color: #080a12;
    transform: translateY(1px);
}

/* EQUALIZER DRAWER SHEET */
.ag-sm-eq-drawer {
    display: none;
    background: rgba(12, 16, 28, 0.92);
    backdrop-filter: blur(36px) saturate(160%);
    -webkit-backdrop-filter: blur(36px) saturate(160%);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 20px;
    padding: 14px 18px;
    flex-direction: column;
    gap: 10px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6);
    margin-bottom: 10px;
}
.ag-sm-eq-drawer.open {
    display: flex !important;
}
.ag-sm-eq-row {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
}
.ag-sm-eq-group {
    display: flex;
    align-items: center;
    gap: 5px;
}
.ag-sm-eq-label {
    font-size: 9.5px;
    font-weight: 700;
    color: #94a3b8;
    letter-spacing: 0.5px;
}
.ag-sm-eq-chip {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 600;
    cursor: pointer;
    backdrop-filter: blur(10px);
    transition: all 0.18s ease;
}
.ag-sm-eq-chip:hover {
    background: rgba(255, 255, 255, 0.10);
    border-color: rgba(255, 255, 255, 0.16);
    color: #ffffff;
}
.ag-sm-eq-chip.active {
    background: #ffffff;
    border-color: #ffffff;
    color: #080a12;
    box-shadow: 0 2px 10px rgba(255, 255, 255, 0.3);
}
.ag-sm-eq-sliders {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 0;
}
.ag-sm-band {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
}
.ag-sm-band-name {
    font-size: 9.5px;
    color: #94a3b8;
    font-weight: 600;
}
.ag-sm-band-slider {
    -webkit-appearance: none;
    width: 100%;
    height: 3px;
    border-radius: 1.5px;
    background: rgba(255, 255, 255, 0.12);
    outline: none;
    cursor: pointer;
}
.ag-sm-band-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 0 8px rgba(255, 255, 255, 0.8);
    cursor: pointer;
}
.ag-sm-band-val {
    font-size: 9px;
    color: #64748b;
    font-variant-numeric: tabular-nums;
}

/* =========================================================================
   SKELETON LOADING STATE (shown while recommendations are fetching)
   ========================================================================= */
.ag-sm-skeleton-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 14px;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.04);
}
.ag-sm-skel-thumb {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
    animation: agSkeletonShimmer 1.6s ease-in-out infinite;
}
.ag-sm-skel-lines {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 7px;
}
.ag-sm-skel-line {
    height: 10px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.07);
    animation: agSkeletonShimmer 1.6s ease-in-out infinite;
}
.ag-sm-skel-line:nth-child(1) { width: 72%; animation-delay: 0s; }
.ag-sm-skel-line:nth-child(2) { width: 50%; animation-delay: 0.15s; }

@keyframes agSkeletonShimmer {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}

/* Right pane scoped scrollbar */
.ag-sm-right-stage::-webkit-scrollbar { width: 4px; }
.ag-sm-right-stage::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
}
.ag-sm-right-stage::-webkit-scrollbar-thumb:hover {
    background: rgba(56, 189, 248, 0.35);
}
.ag-sm-right-stage::-webkit-scrollbar-track { background: transparent; }

/* Smooth ambient color transitions */
.ag-sm-ambient-mesh::before {
    transition: background 1.5s ease, opacity 1.5s ease !important;
}
.ag-sm-ambient-mesh::after {
    transition: background 1.5s ease, opacity 1.5s ease !important;
}

/* Live EQ Bars for active card */
.ag-sm-live-eq {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 16px;
}
.ag-sm-live-eq span {
    width: 3px;
    background: var(--yuma-accent);
    border-radius: 2px;
    animation: agEqDance 0.8s ease-in-out infinite alternate;
}
.ag-sm-live-eq span:nth-child(1) { height: 8px; animation-delay: 0s; }
.ag-sm-live-eq span:nth-child(2) { height: 14px; animation-delay: 0.15s; }
.ag-sm-live-eq span:nth-child(3) { height: 10px; animation-delay: 0.07s; }
.ag-sm-live-eq span:nth-child(4) { height: 16px; animation-delay: 0.22s; }
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

        function safeGetStorage(key) {
            try {
                return (typeof window !== 'undefined' && window.sessionStorage) ? window.sessionStorage.getItem(key) : null;
            } catch(e) {
                return null;
            }
        }
        function safeSetStorage(key, val) {
            try {
                if (typeof window !== 'undefined' && window.sessionStorage) window.sessionStorage.setItem(key, val);
            } catch(e) {}
        }

        // 1. Inject Permanent Global Ad-Blocker Stylesheet
        let adblockStyle = document.getElementById('antigravity-adblock-style');
        if (!adblockStyle) {
            adblockStyle = document.createElement('style');
            adblockStyle.id = 'antigravity-adblock-style';
            adblockStyle.type = 'text/css';
            adblockStyle.textContent = {adblock_css_json};
            (document.head || document.documentElement).appendChild(adblockStyle);
        }

        // 2. Inject Top Controls Styling
        let controlsStyle = document.getElementById('antigravity-controls-style');
        if (!controlsStyle) {
            controlsStyle = document.createElement('style');
            controlsStyle.id = 'antigravity-controls-style';
            controlsStyle.type = 'text/css';
            controlsStyle.textContent = {controls_css_json};
            (document.head || document.documentElement).appendChild(controlsStyle);
        }

        // 3. Inject Cinema Mode Stylesheet (Toggable)
        let cinemaStyle = document.getElementById('antigravity-cinema-style');
        if (!cinemaStyle) {
            cinemaStyle = document.createElement('style');
            cinemaStyle.id = 'antigravity-cinema-style';
            cinemaStyle.type = 'text/css';
            cinemaStyle.textContent = {cinema_css_json};
            (document.head || document.documentElement).appendChild(cinemaStyle);
        }

        // 4. Inject Studio Music Mode Stylesheet
        let studioStyle = document.getElementById('antigravity-studio-style');
        if (!studioStyle) {
            studioStyle = document.createElement('style');
            studioStyle.id = 'antigravity-studio-style';
            studioStyle.type = 'text/css';
            studioStyle.textContent = {studio_music_css_json};
            (document.head || document.documentElement).appendChild(studioStyle);
        }

        // 5. Inject Top Controls Container
        let controls = document.getElementById('antigravity-top-controls');
        if (!controls) {
            controls = document.createElement('div');
            controls.id = 'antigravity-top-controls';
            
            // A. Maximize Screen Button
            const fsBtn = document.createElement('button');
            fsBtn.className = 'ag-control-btn';
            fsBtn.id = 'agFsBtn';
            fsBtn.textContent = '⛶ Screen';
            fsBtn.title = 'Maximize / Fullscreen (Esc to exit)';

            // B. Studio Music Mode Button
            const studioBtn = document.createElement('button');
            studioBtn.className = 'ag-control-btn ag-studio-btn';
            studioBtn.id = 'agStudioBtn';
            studioBtn.textContent = '🎵 Music Studio';
            studioBtn.title = 'Switch to Luxury Dark Music Player interface';
            const activateStudioDirect = (e) => {
                if (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.stopImmediatePropagation) e.stopImmediatePropagation();
                }
                if (typeof window.setStudioMode === 'function') {
                    window.setStudioMode(true);
                } else {
                    try { safeSetStorage('ag_studio_active', '1'); } catch(err) {}
                    let sui = document.getElementById('antigravity-studio-music');
                    if (sui) {
                        sui.classList.add('active');
                        sui.style.display = 'flex';
                    }
                    const tc = document.getElementById('antigravity-top-controls');
                    if (tc) tc.style.display = 'none';
                }
            };
            studioBtn.onclick = activateStudioDirect;
            studioBtn.addEventListener('click', activateStudioDirect, true);
            studioBtn.addEventListener('pointerdown', (e) => { if (e) e.stopPropagation(); }, true);

            // C. Seamless Switcher between YouTube and YouTube Music
            const musicBtn = document.createElement('button');
            musicBtn.className = 'ag-control-btn ag-music-btn';
            musicBtn.id = 'agMusicBtn';
            const isMusicSite = window.location.hostname.includes('music.youtube.com');
            musicBtn.textContent = isMusicSite ? '📺 Switch to YouTube' : '🎵 Switch to YT Music';
            musicBtn.title = isMusicSite ? 'Switch to YouTube video player' : 'Switch to YouTube Music (keeps current song playing)';

            // D. Switch to YouTube Web View / Cinema View Button (hidden on YT Music)
            const modeBtn = document.createElement('button');
            modeBtn.className = 'ag-control-btn';
            modeBtn.id = 'agModeBtn';
            modeBtn.textContent = '🌐 YouTube View';
            modeBtn.title = 'Switch between Cinema Mode and YouTube Web Interface';
            
            // E. Download Current Video/Audio Button
            const dlBtn = document.createElement('button');
            dlBtn.className = 'ag-control-btn ag-download-btn';
            dlBtn.id = 'agDlBtn';
            dlBtn.textContent = isMusicSite ? '🎵 Download MP3' : '⬇️ Download Video';
            dlBtn.title = isMusicSite ? 'Download 320kbps MP3 audio' : 'Download current video';

            controls.appendChild(fsBtn);
            controls.appendChild(studioBtn);
            controls.appendChild(musicBtn);
            controls.appendChild(modeBtn);
            controls.appendChild(dlBtn);
            (document.body || document.documentElement).appendChild(controls);
        }

        const isMusicSite = window.location.hostname.includes('music.youtube.com');
        let isCinema = !isMusicSite && window.location.search.includes('v=');
        let isHovered = false;
        let isDownloading = false;
        let hideTimer;
        
        const fsBtn = document.getElementById('agFsBtn');
        const studioBtn = document.getElementById('agStudioBtn');
        const modeBtn = document.getElementById('agModeBtn');
        const musicBtn = document.getElementById('agMusicBtn');
        const dlBtn = document.getElementById('agDlBtn');

        if (isMusicSite) {
            if (cinemaStyle) cinemaStyle.disabled = true;
            if (modeBtn) modeBtn.style.display = 'none';
            if (musicBtn) {
                musicBtn.textContent = '📺 Switch to YouTube';
                musicBtn.title = 'Switch to YouTube video player';
            }
            if (dlBtn) {
                dlBtn.textContent = '🎵 Download MP3';
                dlBtn.title = 'Download 320kbps MP3 audio';
            }
        } else {
            if (!isCinema && cinemaStyle) {
                cinemaStyle.disabled = true;
                if (modeBtn) {
                    modeBtn.textContent = '🎬 Cinema View';
                    modeBtn.style.background = 'rgba(37, 99, 235, 0.92)';
                }
            }
        }

        function updateFullscreenState(state) {
            if (fsBtn) {
                if (state) {
                    fsBtn.textContent = '🗗 Exit (Esc)';
                    fsBtn.style.background = 'rgba(220, 38, 38, 0.92)';
                } else {
                    fsBtn.textContent = '⛶ Screen';
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

        if (studioBtn) {
            const handleStudioClick = (e) => {
                if (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.stopImmediatePropagation) e.stopImmediatePropagation();
                }
                if (typeof window.setStudioMode === 'function') {
                    window.setStudioMode(true);
                } else {
                    try { safeSetStorage('ag_studio_active', '1'); } catch(err) {}
                    let sui = document.getElementById('antigravity-studio-music');
                    if (sui) {
                        sui.classList.add('active');
                        sui.style.display = 'flex';
                    }
                    const tc = document.getElementById('antigravity-top-controls');
                    if (tc) tc.style.display = 'none';
                }
            };
            studioBtn.onclick = handleStudioClick;
            studioBtn.addEventListener('click', handleStudioClick, true);
            studioBtn.addEventListener('pointerdown', (e) => { if (e) e.stopPropagation(); }, true);
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

        // Seamless In-Player Switcher between YouTube and YouTube Music
        if (musicBtn) {
            musicBtn.onclick = () => {
                const isMusic = window.location.hostname.includes('music.youtube.com');
                let videoId = '';
                try {
                    const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                    if (player && typeof player.getVideoData === 'function') {
                        const data = player.getVideoData();
                        if (data && data.video_id) videoId = data.video_id;
                    }
                } catch(e) {}

                if (!videoId) {
                    try {
                        const urlParams = new URLSearchParams(window.location.search);
                        videoId = urlParams.get('v') || '';
                    } catch(e) {}
                }

                if (!videoId) {
                    try {
                        const url = new URL(window.location.href);
                        if (url.pathname.includes('/shorts/')) {
                            videoId = url.pathname.split('/shorts/')[1].split('/')[0].split('?')[0];
                        } else if (url.hostname.includes('youtu.be')) {
                            videoId = url.pathname.replace(/^\//, '').split('?')[0];
                        }
                    } catch(e) {}
                }

                if (isMusic) {
                    window.location.href = videoId ? ('https://www.youtube.com/watch?v=' + videoId) : 'https://www.youtube.com';
                } else {
                    window.location.href = videoId ? ('https://music.youtube.com/watch?v=' + videoId) : 'https://music.youtube.com';
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

                // Support YouTube Music
                if (url.hostname.includes('music.youtube.com')) {
                    const musicTrack = document.querySelector('ytmusic-player-bar .title');
                    if (musicTrack && musicTrack.textContent) {
                        pageTitle = musicTrack.textContent.trim();
                    } else if (document.title) {
                        pageTitle = document.title.replace(' - YouTube Music', '').trim();
                    }
                    if (v && v.length >= 10) {
                        return {
                            url: 'https://www.youtube.com/watch?v=' + v,
                            title: pageTitle
                        };
                    }
                }

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
                const isMusic = window.location.hostname.includes('music.youtube.com');
                const dlType = isMusic ? 'audio' : 'video';

                if (!videoInfo || !videoInfo.url) {
                    dlBtn.textContent = isMusic ? '⚠️ Play a track first!' : '⚠️ Play a video first!';
                    dlBtn.style.background = 'rgba(220, 38, 38, 0.92)';
                    setTimeout(() => {
                        if (dlBtn && !isDownloading) {
                            dlBtn.textContent = isMusic ? '🎵 Download MP3' : '⬇️ Download Video';
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
                        window.pywebview.api.download_current_video(videoInfo.url, videoInfo.title, dlType);
                    } else if (window.pywebviewApi && typeof window.pywebviewApi.download_current_video === 'function') {
                        window.pywebviewApi.download_current_video(videoInfo.url, videoInfo.title, dlType);
                    } else {
                        // Fallback retry in case bridge is still hooking
                        setTimeout(() => {
                            if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.download_current_video === 'function') {
                                window.pywebview.api.download_current_video(videoInfo.url, videoInfo.title, dlType);
                            } else {
                                isDownloading = false;
                                dlBtn.textContent = '⚠️ Bridge Connecting...';
                                dlBtn.style.background = 'rgba(220, 38, 38, 0.92)';
                                setTimeout(() => {
                                    if (dlBtn && !isDownloading) {
                                        dlBtn.textContent = isMusic ? '🎵 Download MP3' : '⬇️ Download Video';
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
            const isMusic = window.location.hostname.includes('music.youtube.com');
            const defaultLabel = isMusic ? '🎵 Download MP3' : '⬇️ Download Video';

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
                        dlBtn.textContent = defaultLabel;
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
        // =========================================================================
        // "NEO-STUDIO HI-FI" LIVING AUDIO WORKSTATION & CONTROLLER
        // =========================================================================
        let agTrustedPolicy = null;
        try {
            if (window.trustedTypes && window.trustedTypes.createPolicy) {
                try {
                    agTrustedPolicy = window.trustedTypes.createPolicy('agPolicy', {
                        createHTML: (s) => s
                    });
                } catch(e) {
                    agTrustedPolicy = window.trustedTypes.defaultPolicy || { createHTML: (s) => s };
                }
            }
        } catch(e) {}

        function setSafeHTML(el, html) {
            try {
                if (agTrustedPolicy && typeof agTrustedPolicy.createHTML === 'function') {
                    el.innerHTML = agTrustedPolicy.createHTML(html);
                    return;
                }
            } catch(e) {}
            try {
                el.innerHTML = html;
            } catch(e) {}
        }

        let STUDIO_ASSETS = {};
        try {
            STUDIO_ASSETS = {studio_assets_json};
        } catch(e) {
            STUDIO_ASSETS = {};
        }

        let studioUI = document.getElementById('antigravity-studio-music');
        if (!studioUI) {
            studioUI = document.createElement('div');
            studioUI.id = 'antigravity-studio-music';
            setSafeHTML(studioUI, `
                <!-- YUMA AMBIENT MESH BACKDROP -->
                <div id="agSmAmbientMesh" class="ag-sm-ambient-mesh"></div>

                <!-- TOP HEADER -->
                <header class="ag-sm-header">
                    <div class="ag-sm-header-left">
                        <div class="ag-sm-brand" id="agSmBrandLogo">
                            <div class="ag-sm-brand-icon">
                                <span></span><span></span><span></span><span></span><span></span>
                            </div>
                            <span class="ag-sm-brand-text">StreamFlow Yuma</span>
                        </div>
                    </div>

                    <div class="ag-sm-header-center">
                        <div class="ag-sm-search-capsule">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                            <input type="text" id="agSmSearchInput" placeholder="Search songs, artists, albums..." autocomplete="off">
                        </div>
                    </div>

                    <div class="ag-sm-header-right">
                        <button class="ag-sm-hdr-btn" id="agSmHdrEqBtn" title="Sound Equalizer">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
                            <span>Sound EQ</span>
                        </button>

                        <button class="ag-sm-hdr-btn ag-sm-hdr-video" id="agSmSwitchToVideoBtn" title="Video Mode">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="15" x="2" y="3" rx="2"/><polyline points="17 2 12 7 7 2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>
                            <span>Video Mode</span>
                        </button>

                        <button class="ag-sm-hdr-icon-btn" id="agSmHdrFsBtn" title="Fullscreen">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
                        </button>
                    </div>
                </header>

                <!-- TWO-COLUMN YUMA CONTENT STAGE -->
                <div class="ag-sm-content-stage">
                    <!-- LEFT: YUMA FULL PLAYER (1:1 with yuma_fullplayer.png) -->
                    <div class="ag-sm-left-player">
                        <!-- Cover Artwork -->
                        <div class="ag-sm-art-wrap" id="agSmHeroStage">
                            <img class="ag-sm-art-img" id="agSmHeroArtImg" src="${STUDIO_ASSETS.hero_art}" alt="Cover">
                        </div>

                        <!-- Title, Artist, Heart -->
                        <div class="ag-sm-info-row">
                            <div class="ag-sm-info-text">
                                <div class="ag-sm-hero-title" id="agSmHeroTitle" style="color:rgba(255,255,255,0.35);font-size:15px;font-weight:500">Play a track to begin</div>
                                <div class="ag-sm-hero-artist" id="agSmHeroArtist" style="color:rgba(255,255,255,0.2)">StreamFlow Yuma</div>
                            </div>
                            <button class="ag-sm-heart-btn" id="agSmHeroHeartBtn" title="Like Track">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                            </button>
                        </div>

                        <!-- Continuous Seekbar -->
                        <div class="ag-sm-seek-wrap">
                            <input type="range" class="ag-sm-slider" id="agSmSlider" min="0" max="100" value="28">
                        </div>

                        <!-- Timestamps & FLAC Badge -->
                        <div class="ag-sm-meta-row">
                            <span id="agSmCurrentTime">0:47</span>
                            <div class="ag-sm-badge-capsule" id="agSmHiFiPill">FLAC | 24-bit / 96.0 kHz</div>
                            <span id="agSmDuration">3:47</span>
                        </div>

                        <!-- Floating Transport Capsule -->
                        <div class="ag-sm-transport-row">
                            <button class="ag-sm-flank-btn" id="agSmShuffleBtn" title="Shuffle">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>
                            </button>

                            <div class="ag-sm-transport-capsule">
                                <button class="ag-sm-trans-btn" id="agSmPrevBtn" title="Previous">
                                    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
                                </button>
                                <button class="ag-sm-play-circle" id="agSmPlayPauseBtn" title="Play / Pause">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1.5"/><rect x="14" y="4" width="4" height="16" rx="1.5"/></svg>
                                </button>
                                <button class="ag-sm-trans-btn" id="agSmNextBtn" title="Next">
                                    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
                                </button>
                            </div>

                            <button class="ag-sm-flank-btn" id="agSmRepeatBtn" title="Repeat">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                            </button>
                        </div>

                        <!-- Bottom Sheet Bar -->
                        <div class="ag-sm-bottom-bar">
                            <button class="ag-sm-sheet-btn" id="agSmLyricsBtn" title="Lyrics">
                                <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                            </button>
                            <div class="ag-sm-drag-handle"></div>
                            <button class="ag-sm-sheet-btn" id="agSmHeroDlBtn" title="Download Audio">
                                <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                            </button>
                        </div>
                    </div>

                    <!-- RIGHT: YUMA QUICK PICKS & QUEUE (1:1 with yuma_main.png) -->
                    <div class="ag-sm-right-stage">
                        <!-- Sound Equalizer Drawer -->
                        <div class="ag-sm-eq-drawer" id="agSmEqDrawer">
                            <div class="ag-sm-eq-row">
                                <div class="ag-sm-eq-group">
                                    <span class="ag-sm-eq-label">PRESET</span>
                                    <button class="ag-sm-eq-chip active" data-preset="flat">Pure</button>
                                    <button class="ag-sm-eq-chip" data-preset="bass">Bass</button>
                                    <button class="ag-sm-eq-chip" data-preset="vocal">Vocal</button>
                                    <button class="ag-sm-eq-chip" data-preset="club">Club</button>
                                    <button class="ag-sm-eq-chip" data-preset="acoustic">Acoustic</button>
                                </div>
                            </div>
                            <div class="ag-sm-eq-sliders">
                                <div class="ag-sm-band"><span class="ag-sm-band-name">60Hz</span><input type="range" class="ag-sm-band-slider" min="-12" max="12" value="0" data-band="60"><span class="ag-sm-band-val">0dB</span></div>
                                <div class="ag-sm-band"><span class="ag-sm-band-name">250Hz</span><input type="range" class="ag-sm-band-slider" min="-12" max="12" value="0" data-band="250"><span class="ag-sm-band-val">0dB</span></div>
                                <div class="ag-sm-band"><span class="ag-sm-band-name">1kHz</span><input type="range" class="ag-sm-band-slider" min="-12" max="12" value="0" data-band="1000"><span class="ag-sm-band-val">0dB</span></div>
                                <div class="ag-sm-band"><span class="ag-sm-band-name">4kHz</span><input type="range" class="ag-sm-band-slider" min="-12" max="12" value="0" data-band="4000"><span class="ag-sm-band-val">0dB</span></div>
                                <div class="ag-sm-band"><span class="ag-sm-band-name">12kHz</span><input type="range" class="ag-sm-band-slider" min="-12" max="12" value="0" data-band="12000"><span class="ag-sm-band-val">0dB</span></div>
                            </div>
                        </div>

                        <!-- Mood Filter Chips -->
                        <div class="ag-sm-chips-row">
                            <button class="ag-sm-chip active" data-query="">All Recommendations</button>
                            <button class="ag-sm-chip" data-query="energize high energy electronic dance music">Energize</button>
                            <button class="ag-sm-chip" data-query="feel good positive acoustic pop vibes">Feel good</button>
                            <button class="ag-sm-chip" data-query="relax lo-fi chillout ambient beats">Relax</button>
                            <button class="ag-sm-chip" data-query="workout gym cardio phonk motivational beats">Workout</button>
                            <button class="ag-sm-chip" data-query="deep focus ambient electronic study mix">Focus</button>
                        </div>

                        <!-- Section Header -->
                        <div class="ag-sm-sec-header">
                            <div class="ag-sm-sec-title">Up Next</div>
                            <div class="ag-sm-sec-sub" id="agSmRecSubtitle">Continuous playback</div>
                        </div>

                        <!-- Up Next Cards List -->
                        <div class="ag-sm-queue-list" id="agSmRelatedList">
                            <div class="ag-sm-card active-playing">
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">Peter x Gwen Edit</div>
                                    <div class="ag-sm-card-artist">Saarang & Sarvaang</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">2:49</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>Download</span></button>
                                </div>
                            </div>
                            <div class="ag-sm-card" data-title="Recollect - Konomi Suzuki">
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">Recollect</div>
                                    <div class="ag-sm-card-artist">Konomi Suzuki, Ashnikko</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">3:18</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>Download</span></button>
                                </div>
                            </div>
                            <div class="ag-sm-card" data-title="FLASH BACK - natori">
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">FLASH BACK</div>
                                    <div class="ag-sm-card-artist">natori</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">3:05</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>Download</span></button>
                                </div>
                            </div>
                            <div class="ag-sm-card" data-title="Deep down - Aimer">
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">Deep down</div>
                                    <div class="ag-sm-card-artist">Aimer</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">3:47</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>Download</span></button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `);
            (document.body || document.documentElement).appendChild(studioUI);
        }

        // =========================================================================
        // STUDIO MUSIC STATE & AUDIO SYNCHRONIZATION CONTROLLER
        // =========================================================================

        // Global Studio State Variables (Declared at top to prevent Temporal Dead Zone)
        var isStudioActive = safeGetStorage('ag_studio_active') === '1';
        var isFetchingRecs = false;
        var lastVId = '';
        var visRunning = false;
        var audioCtx = null;
        var eqFilters = [];
        var sleepTimerId = null;

        function formatTime(seconds) {
            if (isNaN(seconds) || seconds < 0) return '0:00';
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return mins + ':' + (secs < 10 ? '0' : '') + secs;
        }

        // Smart YouTube Video Title & Artist Sanitizer (Obsidian Studio Engine 2026)
        function cleanTrackTitle(raw) {
            if (!raw) return 'Unknown Title';
            let t = String(raw).trim();
            // Remove emojis and special symbols
            t = t.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1FA70}-\u{1FAFF}]/gu, '');
            t = t.replace(/^(?:full\s*song|video\s*song|official\s*(?:video|audio|music)|lyrical(?:\s*video)?|audio\s*song)[\s_:–\-—]+/gi, '');
            t = t.replace(/[\(\[\{]+\s*(?:official\s*(?:music\s*)?(?:video|audio|song|lyric|visualizer|hd|4k|uhd)?|full\s*(?:song|video|audio)|video\s*song|audio\s*song|lyrics?|lyric\s*video|visualizer|remastered|extended|hq|audio|4k|1080p|hd|uhd|hdr|60fps|8k|prod\.[^\)\]\}]+|jhankaar[^\)\]\}]*)\s*[\)\]\}]+/gi, ' ');
            t = t.replace(/[\(\[\{]\s*[\)\]\}]/g, '');
            t = t.replace(/\s*M\/V$/gi, '');
            t = t.replace(/\s*MV$/gi, '');
            if (t.includes('|')) {
                const parts = t.split('|').map(s => s.trim()).filter(Boolean);
                if (parts.length > 1) t = parts[0];
            }
            t = t.replace(/\s*-\s*(?:official\s*)?(?:lyric\s*video|music\s*video|audio\s*video|lyric|video|audio|full\s*song).*$/gi, ' ');
            t = t.replace(/\s+(?:full\s*song(?:\s*with\s*lyrics)?|video\s*song(?:\s*with\s*lyrics)?|full\s*video(?:\s*song)?|audio\s*song|song\s*with\s*lyrics|8k\/4k\s*mus.*)$/gi, ' ');
            t = t.replace(/\b(?:full\s*song|video\s*song|official\s*music)\b/gi, ' ');
            t = t.replace(/__+/g, ' ');
            t = t.replace(/--+/g, '-');
            t = t.replace(/[_]+/g, ' ');
            t = t.replace(/^["'\s\-—]+|["'\s\-—]+$/g, '');
            t = t.replace(/\s+/g, ' ').trim();
            if (t === t.toUpperCase() && t.length > 6 && !t.includes(' ')) {
                t = t.charAt(0) + t.slice(1).toLowerCase();
            }
            return t || raw;
        }

        function cleanArtistName(raw, trackTitle) {
            let a = String(raw || '').trim();
            a = a.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1FA70}-\u{1FAFF}]/gu, '');
            a = a.replace(/^@+/, '');
            a = a.replace(/\s*-\s*Topic$/i, '');
            a = a.replace(/VEVO$/i, '');
            a = a.replace(/\s*(?:official\s*(?:channel|artist\s*channel|music|audio)?)$/gi, '');
            a = a.replace(/\s+/g, ' ').trim();

            if ((!a || a === 'YouTube Music' || a === 'Studio Audio' || a === 'Various Artists' || a === 'StreamFlow Master') && trackTitle && (trackTitle.includes(' - ') || trackTitle.includes(' : '))) {
                const sep = trackTitle.includes(' - ') ? ' - ' : ' : ';
                const parts = trackTitle.split(sep).map(s => s.trim());
                if (parts.length === 2) {
                    if (/feat|ft\.|trivedi|singh|kumar|khan|sharma|shreya|arijit|armaan|sonu|king|divine|pritam|badshah|honey|rahman/i.test(parts[1])) {
                        a = parts[1];
                    } else if (/feat|ft\.|trivedi|singh|kumar|khan|sharma|shreya|arijit|armaan|sonu|king|divine|pritam|badshah|honey|rahman/i.test(parts[0])) {
                        a = parts[0];
                    } else {
                        a = parts[1];
                    }
                }
            }

            if (!a || a === 'YouTube Music' || a === 'Studio Audio' || a === 'StreamFlow Master') {
                a = 'Original Artist';
            }
            return a;
        }

        window.setStudioMode = function(active) {
            isStudioActive = !!active;
            try {
                safeSetStorage('ag_studio_active', active ? '1' : '0');
            } catch(err) {}
            let studioUI = document.getElementById('antigravity-studio-music');
            const topControls = document.getElementById('antigravity-top-controls');
            if (active) {
                if (!studioUI) {
                    studioUI = document.getElementById('antigravity-studio-music');
                }
                if (studioUI) {
                    studioUI.classList.add('active');
                    studioUI.style.display = 'flex';
                    studioUI.style.visibility = 'visible';
                    studioUI.style.opacity = '1';
                }
                if (topControls) topControls.style.display = 'none';
                try { syncStudioPlayer(); } catch(err) {}
                try { fetchContextualRecommendations(); } catch(err) {}
                try { startVisualizer(); } catch(err) {}
            } else {
                if (studioUI) {
                    studioUI.classList.remove('active');
                    studioUI.style.display = 'none';
                }
                if (topControls) topControls.style.display = 'flex';
            }
        };
        const setStudioMode = window.setStudioMode;

        if (isStudioActive) {
            setStudioMode(true);
        }

        // Navigation button listeners (using capture phase so YouTube player cannot intercept clicks)
        document.addEventListener('click', (e) => {
            const target = e.target;
            if (!target) return;
            if (target.id === 'agStudioBtn' || target.closest('#agStudioBtn')) {
                e.preventDefault();
                e.stopPropagation();
                setStudioMode(true);
            } else if (target.id === 'agSmSwitchToVideoBtn' || target.closest('#agSmSwitchToVideoBtn') || target.id === 'agSmHeroSwitchVideoBtn' || target.closest('#agSmHeroSwitchVideoBtn')) {
                e.preventDefault();
                e.stopPropagation();
                setStudioMode(false);
            } else if (target.id === 'agSmBackArrow' || target.closest('#agSmBackArrow')) {
                window.history.back();
            } else if (target.id === 'agSmFwdArrow' || target.closest('#agSmFwdArrow')) {
                window.history.forward();
            } else if (target.id === 'agSmHdrFsBtn' || target.closest('#agSmHdrFsBtn')) {
                const fb = document.getElementById('agFsBtn');
                if (fb) fb.click();
            }
        }, true);

        // ---------------- 5-Band Web Audio Equalizer ----------------

        const EQ_FREQS = [60, 250, 1000, 4000, 12000];
        const EQ_TYPES = ['lowshelf', 'peaking', 'peaking', 'peaking', 'highshelf'];

        function initWebAudio() {
            try {
                if (audioCtx) return;
                const video = document.querySelector('video');
                if (!video) return;
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                audioCtx = new AudioContext();
                const source = audioCtx.createMediaElementSource(video);

                // Build 5-band filter chain
                let prevNode = source;
                eqFilters = [];
                for (let i = 0; i < EQ_FREQS.length; i++) {
                    const f = audioCtx.createBiquadFilter();
                    f.type = EQ_TYPES[i];
                    f.frequency.value = EQ_FREQS[i];
                    f.gain.value = 0;
                    prevNode.connect(f);
                    prevNode = f;
                    eqFilters.push(f);
                }
                prevNode.connect(audioCtx.destination);
            } catch(e) {}
        }

        function setBandGain(bandIdx, gainVal) {
            initWebAudio();
            if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
            if (eqFilters[bandIdx]) {
                eqFilters[bandIdx].gain.value = gainVal;
                const valEl = document.getElementById('agEqBand' + bandIdx + 'Val');
                if (valEl) valEl.textContent = (gainVal > 0 ? '+' : '') + gainVal + 'dB';
                const slider = document.getElementById('agEqBand' + bandIdx);
                if (slider) slider.value = gainVal;
            }
        }

        function applyEqPreset(preset) {
            initWebAudio();
            if (preset === 'bass') {
                setBandGain(0, 8);
                setBandGain(1, 5);
                setBandGain(2, 0);
                setBandGain(3, -1);
                setBandGain(4, 2);
            } else if (preset === 'vocal') {
                setBandGain(0, -2);
                setBandGain(1, 0);
                setBandGain(2, 5);
                setBandGain(3, 4);
                setBandGain(4, 1);
            } else if (preset === 'treble') {
                setBandGain(0, -1);
                setBandGain(1, 0);
                setBandGain(2, 1);
                setBandGain(3, 5);
                setBandGain(4, 8);
            } else if (preset === 'lofi') {
                setBandGain(0, 4);
                setBandGain(1, 3);
                setBandGain(2, -2);
                setBandGain(3, -4);
                setBandGain(4, -6);
            } else if (preset === 'acoustic') {
                setBandGain(0, 2);
                setBandGain(1, 4);
                setBandGain(2, 3);
                setBandGain(3, 2);
                setBandGain(4, 3);
            } else { // flat
                for (let i = 0; i < 5; i++) setBandGain(i, 0);
            }
        }

        for (let i = 0; i < 5; i++) {
            const slider = document.getElementById('agEqBand' + i);
            if (slider) {
                slider.oninput = () => setBandGain(i, parseInt(slider.value, 10));
            }
        }

        function toggleEqDrawer() {
            const drawer = document.getElementById('agSmEqDrawer');
            if (drawer) {
                drawer.classList.toggle('open');
                const isOpen = drawer.classList.contains('open');
                drawer.style.display = isOpen ? 'block' : 'none';
                if (isOpen) {
                    drawer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        }

        const barEqBtn = document.getElementById('agSmBarEqBtn');
        if (barEqBtn) barEqBtn.onclick = toggleEqDrawer;
        const heroEqBtn = document.getElementById('agSmHeroEqToggleBtn');
        if (heroEqBtn) heroEqBtn.onclick = toggleEqDrawer;
        const sideEqBtn = document.getElementById('agSmSideEqBtn');
        if (sideEqBtn) sideEqBtn.onclick = toggleEqDrawer;
        const hdrEqBtn = document.getElementById('agSmHdrEqBtn');
        if (hdrEqBtn) hdrEqBtn.onclick = toggleEqDrawer;
        const sideSpeedBtn = document.getElementById('agSmSideSpeedBtn');
        if (sideSpeedBtn) sideSpeedBtn.onclick = () => {
            toggleEqDrawer();
            const drawer = document.getElementById('agSmEqDrawer');
            if (drawer) drawer.style.display = 'block';
        };
        const sideTimerBtn = document.getElementById('agSmSideTimerBtn');
        if (sideTimerBtn) sideTimerBtn.onclick = () => {
            toggleEqDrawer();
            const drawer = document.getElementById('agSmEqDrawer');
            if (drawer) drawer.style.display = 'block';
        };

        document.querySelectorAll('.ag-sm-eq-chip[data-eq]').forEach(chip => {
            chip.onclick = () => {
                document.querySelectorAll('.ag-sm-eq-chip[data-eq]').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                applyEqPreset(chip.getAttribute('data-eq'));
            };
        });

        document.querySelectorAll('.ag-sm-eq-chip[data-speed]').forEach(chip => {
            chip.onclick = () => {
                document.querySelectorAll('.ag-sm-eq-chip[data-speed]').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                const spd = parseFloat(chip.getAttribute('data-speed')) || 1.0;
                const video = document.querySelector('video');
                if (video) video.playbackRate = spd;
            };
        });

        document.querySelectorAll('.ag-sm-eq-chip[data-timer]').forEach(chip => {
            chip.onclick = () => {
                document.querySelectorAll('.ag-sm-eq-chip[data-timer]').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                if (sleepTimerId) clearTimeout(sleepTimerId);
                const mins = parseInt(chip.getAttribute('data-timer'), 10) || 0;
                if (mins > 0) {
                    sleepTimerId = setTimeout(() => {
                        const video = document.querySelector('video');
                        if (video) video.pause();
                        syncStudioPlayer();
                    }, mins * 60 * 1000);
                }
            };
        });

        // ---------------- Audio Visualizer Canvas ----------------
        function startVisualizer() {
            if (visRunning) return;
            const canvas = document.getElementById('agSmVisualizerCanvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;
            visRunning = true;
            canvas.width = canvas.offsetWidth || 280;
            canvas.height = canvas.offsetHeight || 18;

            let phase = 0;
            // Immediate first draw
            setTimeout(() => { try { draw(); } catch(e){} }, 50);
            function draw() {
                if (!document.getElementById('antigravity-studio-music') || !document.getElementById('antigravity-studio-music').classList.contains('active')) {
                    visRunning = false;
                    return;
                }
                requestAnimationFrame(draw);
                const w = canvas.width;
                const h = canvas.height;
                ctx.clearRect(0, 0, w, h);

                const video = document.querySelector('video');
                const isPlaying = video && !video.paused && video.currentTime > 0;
                phase += isPlaying ? 0.12 : 0.02;

                const grad = ctx.createLinearGradient(0, 0, w, 0);
                grad.addColorStop(0.0, '#06b6d4');
                grad.addColorStop(0.30, '#38bdf8');
                grad.addColorStop(0.55, '#818cf8');
                grad.addColorStop(0.80, '#c084fc');
                grad.addColorStop(1.0, '#ec4899');

                const bars = 44;
                const gap = 2.0;
                const barW = (w - (bars - 1) * gap) / bars;

                for (let i = 0; i < bars; i++) {
                    const norm = i / bars;
                    const bell = Math.exp(-Math.pow((norm - 0.45) * 3.5, 2));
                    const sinVal = Math.sin(phase + norm * 8) * 0.5 + 0.5;
                    let heightRatio = isPlaying ? (bell * 0.6 + sinVal * 0.4) : (bell * 0.75 + 0.25);
                    const barH = Math.max(2.5, heightRatio * h * 0.9);
                    const x = i * (barW + gap);
                    const y = (h - barH) / 2;

                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    if (ctx.roundRect) {
                        ctx.roundRect(x, y, barW, barH, 1.2);
                    } else {
                        ctx.rect(x, y, barW, barH);
                    }
                    ctx.fill();
                }
            }
            requestAnimationFrame(draw);
        }

        // ---------------- Player Sync Loop ----------------
        // ---------------- Yuma Ambient Color Palette Extraction Engine ----------------
        function updateYumaAmbientTheme(imgUrl, seedStr) {
            try {
                const studioEl = document.getElementById('antigravity-studio-music');
                if (!studioEl) return;
                
                function applyColors(c1, c2, accent) {
                    studioEl.style.setProperty('--ambient-color-1', c1);
                    studioEl.style.setProperty('--ambient-color-2', c2);
                    studioEl.style.setProperty('--yuma-accent', accent);
                    studioEl.style.setProperty('--yuma-accent-glow', accent.replace('rgb', 'rgba').replace(')', ', 0.35)'));
                }

                function fallbackPalette(seed) {
                    let hash = 0;
                    const s = seed || 'streamflow-studio';
                    for (let i = 0; i < s.length; i++) hash = ((hash << 5) - hash) + s.charCodeAt(i);
                    const palettes = [
                        ['rgba(99, 102, 241, 0.55)', 'rgba(6, 182, 212, 0.45)', 'rgb(56, 189, 248)'],
                        ['rgba(236, 72, 153, 0.50)', 'rgba(139, 92, 246, 0.45)', 'rgb(244, 114, 182)'],
                        ['rgba(16, 185, 129, 0.50)', 'rgba(14, 165, 233, 0.45)', 'rgb(52, 211, 153)'],
                        ['rgba(245, 158, 11, 0.50)', 'rgba(239, 68, 68, 0.40)', 'rgb(251, 191, 36)'],
                        ['rgba(168, 85, 247, 0.55)', 'rgba(236, 72, 153, 0.40)', 'rgb(192, 132, 252)']
                    ];
                    const p = palettes[Math.abs(hash) % palettes.length];
                    applyColors(p[0], p[1], p[2]);
                }

                const img = new Image();
                img.crossOrigin = 'Anonymous';
                img.onload = function() {
                    try {
                        const cvs = document.createElement('canvas');
                        cvs.width = 16; cvs.height = 16;
                        const ctx = cvs.getContext('2d');
                        ctx.drawImage(img, 0, 0, 16, 16);
                        const d = ctx.getImageData(0, 0, 16, 16).data;
                        let r1 = 0, g1 = 0, b1 = 0, c1 = 0;
                        let r2 = 0, g2 = 0, b2 = 0, c2 = 0;
                        for (let i = 0; i < d.length; i += 16) {
                            const r = d[i], g = d[i+1], b = d[i+2];
                            const br = (r*299 + g*587 + b*114) / 1000;
                            if (br > 25 && br < 235) {
                                if (i < d.length / 2) { r1 += r; g1 += g; b1 += b; c1++; }
                                else { r2 += r; g2 += g; b2 += b; c2++; }
                            }
                        }
                        if (c1 > 0 && c2 > 0) {
                            const col1 = `rgba(${Math.round(r1/c1)}, ${Math.round(g1/c1)}, ${Math.round(b1/c1)}, 0.55)`;
                            const col2 = `rgba(${Math.round(r2/c2)}, ${Math.round(g2/c2)}, ${Math.round(b2/c2)}, 0.45)`;
                            const acc = `rgb(${Math.min(255, Math.round(r1/c1)+45)}, ${Math.min(255, Math.round(g1/c1)+45)}, ${Math.min(255, Math.round(b1/c1)+45)})`;
                            applyColors(col1, col2, acc);
                            return;
                        }
                    } catch(err) {}
                    fallbackPalette(seedStr);
                };
                img.onerror = () => fallbackPalette(seedStr);
                img.src = imgUrl;
            } catch(e) {
                fallbackPalette(seedStr);
            }
        }

        function syncStudioPlayer() {
            try {
                const video = document.querySelector('video');
                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                const playPauseBtn = document.getElementById('agSmPlayPauseBtn');
                const heroPlayBtn = document.getElementById('agSmHeroPlayBtn');
                const heroPlayIcon = document.getElementById('agSmHeroPlayIcon');
                const heroPlayText = document.getElementById('agSmHeroPlayText');
                const heroStage = document.getElementById('agSmHeroStage');
                const vinylDisc = document.getElementById('agSmVinylDisc');
                const curTimeEl = document.getElementById('agSmCurrentTime');
                const durEl = document.getElementById('agSmDuration');
                const sliderEl = document.getElementById('agSmSlider');
                const muteBtn = document.getElementById('agSmMuteBtn');
                const volSlider = document.getElementById('agSmVolSlider');
                const bottomTitle = document.getElementById('agSmBottomTitle');
                const bottomArtist = document.getElementById('agSmBottomArtist');
                const bottomThumb = document.getElementById('agSmBottomThumb');
                const heroTitle = document.getElementById('agSmHeroTitle');
                const heroArtist = document.getElementById('agSmHeroArtist') || document.getElementById('agSmHeroArtistName');
                const heroArt = document.getElementById('agSmHeroArtImg');
                const heroBackdrop = document.getElementById('agSmHeroBackdrop');
                const sideMiniTitle = document.getElementById('agSmSideMiniTitle');
                const sideMiniArtist = document.getElementById('agSmSideMiniArtist');
                const sideMiniImg = document.getElementById('agSmSideMiniImg');

                if (video) {
                    const isPaused = video.paused;
                    const playSvg = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
                    const pauseSvg = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>';
                    const heroPlaySvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
                    const heroPauseSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>';
                    
                    const bottomPlayWrap = document.getElementById('agSmBottomPlayWrap');
                    if (bottomPlayWrap) setSafeHTML(bottomPlayWrap, isPaused ? playSvg : pauseSvg);
                    const heroPlayWrap = document.getElementById('agSmHeroPlayIconWrap');
                    if (heroPlayWrap) setSafeHTML(heroPlayWrap, isPaused ? heroPlaySvg : heroPauseSvg);
                    if (heroPlayText) heroPlayText.textContent = isPaused ? 'PLAY' : 'PAUSE';

                    if (playPauseBtn) {
                        const yumaPlaySvg = '<svg width="22" height="22" viewBox="0 0 24 24" fill="#080a12"><polygon points="6 4 20 12 6 20 6 4"/></svg>';
                        const yumaPauseSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="#080a12"><rect x="6" y="4" width="4" height="16" rx="1.5"/><rect x="14" y="4" width="4" height="16" rx="1.5"/></svg>';
                        setSafeHTML(playPauseBtn, isPaused ? yumaPlaySvg : yumaPauseSvg);
                    }

                    if (heroStage) {
                        if (!isPaused) heroStage.classList.add('is-playing');
                        else heroStage.classList.remove('is-playing');
                    }

                    const heroCurTime = document.getElementById('agSmHeroCurTime');
                    const heroTotalTime = document.getElementById('agSmHeroTotalTime');
                    if (!isNaN(video.currentTime)) {
                        const curFormatted = formatTime(video.currentTime);
                        if (curTimeEl) curTimeEl.textContent = curFormatted;
                        if (heroCurTime) heroCurTime.textContent = curFormatted;
                    }
                    if (!isNaN(video.duration) && video.duration > 0) {
                        const durFormatted = formatTime(video.duration);
                        if (durEl) durEl.textContent = durFormatted;
                        if (heroTotalTime) heroTotalTime.textContent = durFormatted;
                        if (sliderEl && !sliderEl._isSeeking) {
                            const pct = (video.currentTime / video.duration) * 100;
                            sliderEl.value = pct;
                            sliderEl.style.background = `linear-gradient(to right, #ffffff 0%, #ffffff ${pct}%, rgba(255, 255, 255, 0.18) ${pct}%, rgba(255, 255, 255, 0.18) 100%)`;
                        }
                    }

                    const volWrap = document.getElementById('agSmVolIconWrap');
                    if (volWrap) {
                        const muteSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>';
                        const unmutedSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>';
                        setSafeHTML(volWrap, video.muted ? muteSvg : unmutedSvg);
                    }
                    if (volSlider && !volSlider._isSeeking) volSlider.value = video.muted ? 0 : (video.volume * 100);
                }

                // Extract active video info
                let curTitle = '';
                let curAuthor = '';
                let vId = '';

                if (player && typeof player.getVideoData === 'function') {
                    const d = player.getVideoData();
                    if (d) {
                        curTitle = d.title || '';
                        curAuthor = d.author || '';
                        vId = d.video_id || '';
                    }
                }

                if (!curTitle) {
                    const titleEl = document.querySelector('h1.ytd-video-primary-info-renderer, h1.ytd-watch-metadata, ytmusic-player-bar .title, title');
                    if (titleEl) curTitle = titleEl.textContent.replace(' - YouTube', '').replace(' - YouTube Music', '').trim();
                }
                if (!curAuthor) {
                    const authorEl = document.querySelector('#owner #channel-name, ytd-channel-name a, ytmusic-player-bar .subtitle a');
                    if (authorEl) curAuthor = authorEl.textContent.trim();
                }
                if (!vId) {
                    const p = new URLSearchParams(window.location.search);
                    vId = p.get('v') || '';
                }

                // Sanitize title and artist names
                const displayTitle = cleanTrackTitle(curTitle);
                const displayAuthor = cleanArtistName(curAuthor);

                if (displayTitle && heroTitle && heroTitle.textContent !== displayTitle) {
                    heroTitle.textContent = displayTitle;
                    heroTitle.removeAttribute('style');
                    if (bottomTitle) bottomTitle.textContent = displayTitle;
                    if (sideMiniTitle) sideMiniTitle.textContent = displayTitle;
                    const recSub = document.getElementById('agSmRecSubtitle');
                    if (recSub) recSub.textContent = 'Tailored to ' + displayTitle.slice(0, 42);
                }
                if (displayAuthor && heroArtist && heroArtist.textContent !== displayAuthor) {
                    heroArtist.textContent = displayAuthor;
                    heroArtist.removeAttribute('style');
                    if (bottomArtist) bottomArtist.textContent = displayAuthor;
                    if (sideMiniArtist) sideMiniArtist.textContent = displayAuthor;
                }

                if (vId && vId !== lastVId) {
                    lastVId = vId;
                    const thumb = `https://img.youtube.com/vi/${vId}/hqdefault.jpg`;
                    const maxThumb = `https://img.youtube.com/vi/${vId}/maxresdefault.jpg`;
                    
                    if (bottomThumb) {
                        bottomThumb.onload = () => bottomThumb.classList.add('loaded');
                        bottomThumb.src = thumb;
                    }
                    if (sideMiniImg) {
                        sideMiniImg.onload = () => sideMiniImg.classList.add('loaded');
                        sideMiniImg.src = thumb;
                    }
                    if (heroArt) {
                        heroArt.onload = () => heroArt.classList.add('loaded');
                        heroArt.src = thumb;
                        const testImg = new Image();
                        testImg.onload = () => { if (testImg.naturalWidth > 120) heroArt.src = maxThumb; };
                        testImg.src = maxThumb;
                    }
                    if (heroBackdrop) {
                        heroBackdrop.style.backgroundImage = `url("${thumb}")`;
                    }
                    updateYumaAmbientTheme(thumb, vId + (displayTitle || ''));
                    setTimeout(fetchContextualRecommendations, 800);
                }
            } catch(e) {}
        }

        setInterval(syncStudioPlayer, 300);

        // ---------------- Contextual Song Recommendations Engine ----------------
        function fetchContextualRecommendations(customQuery) {
            try {
                const listEl = document.getElementById('agSmRelatedList');
                if (!listEl || isFetchingRecs) return;

                const vId = lastVId || (new URLSearchParams(window.location.search)).get('v') || '';
                if (!vId && !customQuery) return;

                isFetchingRecs = true;

                // Show skeleton loading cards immediately
                const skeletonHtml = Array(5).fill(0).map(() => `
                    <div class="ag-sm-skeleton-card">
                        <div class="ag-sm-skel-thumb"></div>
                        <div class="ag-sm-skel-lines">
                            <div class="ag-sm-skel-line"></div>
                            <div class="ag-sm-skel-line"></div>
                        </div>
                    </div>
                `).join('');
                setSafeHTML(listEl, skeletonHtml);
                const renderCards = (tracks) => {
                    isFetchingRecs = false;
                    if (!tracks || tracks.length === 0) return;
                    let cardsHtml = '';
                    tracks.forEach((t, idx) => {
                        const cleanT = cleanTrackTitle(t.title);
                        const cleanA = cleanArtistName(t.artist, t.title);
                        const durTag = t.duration ? `<span class="ag-sm-queue-dur">${t.duration}</span>` : '';
                        const trackIdx = (idx + 1 < 10 ? '0' : '') + (idx + 1);
                        const isCurTrack = (t.id === lastVId);
                        const activeClass = isCurTrack ? ' active-playing' : '';
                        const idxDisplay = isCurTrack
                            ? '<div class="ag-sm-live-eq"><span></span><span></span><span></span><span></span></div>'
                            : `<span class="ag-sm-card-num">${trackIdx}</span>`;

                        const durBadge = t.duration ? `<span class="ag-sm-card-dur-badge">${t.duration}</span>` : '';
                        const durText = t.duration || '3:30';

                        cardsHtml += `
                            <div class="ag-sm-card${activeClass}" data-id="${t.id}" data-url="${t.url}" data-title="${cleanT.replace(/"/g, '&quot;')}">
                                <div class="ag-sm-card-thumb">
                                    <img src="${t.thumb}" alt="Art" loading="lazy">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">${cleanT}</div>
                                    <div class="ag-sm-card-artist">${cleanA}</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">${durText}</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>Download</span></button>
                                </div>
                            </div>
                        `;
                    });

                    setSafeHTML(listEl, cardsHtml);

                    // Attach click handlers
                    listEl.querySelectorAll('.ag-sm-card').forEach(card => {
                        card.onclick = (ev) => {
                            // Check if download button was clicked
                            if (ev.target.getAttribute('data-action') === 'dl' || ev.target.closest('[data-action="dl"]')) {
                                ev.stopPropagation();
                                const url = card.getAttribute('data-url');
                                const title = card.getAttribute('data-title');
                                const btn = ev.target.getAttribute('data-action') === 'dl' ? ev.target : ev.target.closest('[data-action="dl"]');
                                if (btn) {
                                    const dlSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
                                    const okSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
                                    setSafeHTML(btn, `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:agEqDance 0.6s linear infinite"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span>Queuing…</span>`);
                                    btn.style.opacity = '0.7';
                                    btn.style.pointerEvents = 'none';
                                    if (window.pywebview && window.pywebview.api) {
                                        window.pywebview.api.download_current_video(url, title, 'audio')
                                            .then(() => {
                                                setSafeHTML(btn, `${okSvg}<span>Done</span>`);
                                                btn.style.opacity = '1';
                                                setTimeout(() => {
                                                    setSafeHTML(btn, `${dlSvg}<span>Download</span>`);
                                                    btn.style.pointerEvents = '';
                                                }, 2500);
                                            })
                                            .catch(() => {
                                                setSafeHTML(btn, `${dlSvg}<span>Retry</span>`);
                                                btn.style.opacity = '1';
                                                btn.style.pointerEvents = '';
                                            });
                                    }
                                }
                                return;
                            }

                            // Play song instantly
                            const songId = card.getAttribute('data-id');
                            const songUrl = card.getAttribute('data-url');
                            playSongInstantly(songId, songUrl);
                        };
                    });
                };

                window.onSongRecommendations = function(tracks) {
                    isFetchingRecs = false;
                    if (tracks && tracks.length > 0) {
                        renderCards(tracks);
                    }
                };

                // Request from Python BridgeAPI
                const fallbackScrapeDom = () => {
                    isFetchingRecs = false;
                    const domTracks = [];
                    const nodes = document.querySelectorAll('ytd-compact-video-renderer, ytd-video-renderer, yt-lockup-view-model');
                    nodes.forEach(n => {
                        if (domTracks.length >= 20) return;
                        const tEl = n.querySelector('#video-title, .title, h3');
                        const cEl = n.querySelector('#channel-name, .subtitle, ytd-channel-name');
                        const aEl = n.querySelector('a[href*="watch?v="]');
                        if (tEl && aEl && aEl.href) {
                            const vMatch = aEl.href.match(/v=([a-zA-Z0-9_-]{11})/);
                            const songId = vMatch ? vMatch[1] : '';
                            if (songId) {
                                domTracks.push({
                                    id: songId,
                                    title: tEl.textContent.trim(),
                                    artist: cEl ? cEl.textContent.trim() : 'Studio Audio',
                                    duration: '',
                                    thumb: 'https://i.ytimg.com/vi/' + songId + '/mqdefault.jpg',
                                    url: 'https://www.youtube.com/watch?v=' + songId
                                });
                            }
                        }
                    });
                    if (domTracks.length > 0) renderCards(domTracks);
                };

                if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.request_song_recommendations === 'function') {
                    window.pywebview.api.request_song_recommendations(customQuery ? '' : vId, customQuery || '');
                    // Safe timeout fallback to DOM if python takes longer than 3.5s
                    setTimeout(() => {
                        const count = document.querySelectorAll('#agSmRelatedList .ag-sm-card').length;
                        if (count === 0) fallbackScrapeDom();
                    }, 3500);
                } else if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_song_recommendations === 'function') {
                    window.pywebview.api.get_song_recommendations(customQuery ? '' : vId, customQuery || '');
                    setTimeout(() => {
                        const count = document.querySelectorAll('#agSmRelatedList .ag-sm-card').length;
                        if (count === 0) fallbackScrapeDom();
                    }, 3500);
                } else {
                    fallbackScrapeDom();
                }
            } catch(e) {
                isFetchingRecs = false;
            }
        }

        function playSongInstantly(songId, songUrl) {
            try {
                safeSetStorage('ag_studio_active', '1');
                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                if (songId && player && typeof player.loadVideoById === 'function') {
                    player.loadVideoById(songId);
                    window.history.pushState(null, '', '/watch?v=' + songId);
                    syncStudioPlayer();
                    setTimeout(fetchContextualRecommendations, 600);
                } else {
                    window.location.href = songUrl || ('https://www.youtube.com/watch?v=' + songId);
                }
            } catch(e) {
                window.location.href = songUrl || ('https://www.youtube.com/watch?v=' + songId);
            }
        }

        function playMoodQuery(query) {
            safeSetStorage('ag_studio_active', '1');
            const recSub = document.getElementById('agSmRecSubtitle');
            if (recSub) recSub.textContent = 'Curated: ' + query;
            fetchContextualRecommendations(query);
        }

        
        // ---------------- Complete Studio Event Delegation & Controller ----------------
        const smRelatedList = document.getElementById('agSmRelatedList');
        if (smRelatedList) {
            smRelatedList.addEventListener('click', (ev) => {
                const menuBtn = ev.target.closest('.ag-sm-card-menu, [data-action="dl"]');
                const card = ev.target.closest('.ag-sm-card');
                if (!card) return;

                const titleEl = card.querySelector('.ag-sm-card-title');
                const title = card.getAttribute('data-title') || (titleEl ? titleEl.textContent : 'Music Track');
                const url = card.getAttribute('data-url') || ('https://www.youtube.com/results?search_query=' + encodeURIComponent(title));
                const songId = card.getAttribute('data-id');

                if (menuBtn) {
                    ev.stopPropagation();
                    menuBtn.textContent = '⏳';
                    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.download_current_video === 'function') {
                        window.pywebview.api.download_current_video(url, title, 'audio')
                            .then(() => {
                                menuBtn.textContent = '✅';
                                setTimeout(() => { menuBtn.textContent = '⋮'; }, 2500);
                            })
                            .catch(() => { menuBtn.textContent = '⋮'; });
                    } else {
                        setTimeout(() => { menuBtn.textContent = '⋮'; }, 1000);
                    }
                    return;
                }

                if (songId) {
                    playSongInstantly(songId, url);
                } else if (title) {
                    fetchContextualRecommendations(title);
                }
            });
        }

        


        // Like / Heart Button Toggle (Hero + Dock)
        function toggleHeart(btn) {
            if (!btn) return;
            btn.classList.toggle('active');
            const isLiked = btn.classList.contains('active');
            const heroHeart = document.getElementById('agSmHeroHeartBtn');
            const dockHeart = document.getElementById('agSmDockHeartBtn');
            [heroHeart, dockHeart].forEach(h => {
                if (h) {
                    h.classList.toggle('active', isLiked);
                    h.style.color = isLiked ? '#ec4899' : '#94a3b8';
                    if (isLiked) h.style.background = 'rgba(236, 72, 153, 0.3)';
                    else h.style.background = 'transparent';
                }
            });
        }
        const heroHeartBtn = document.getElementById('agSmHeroHeartBtn');
        if (heroHeartBtn) heroHeartBtn.onclick = () => toggleHeart(heroHeartBtn);
        const dockHeartBtn = document.getElementById('agSmDockHeartBtn');
        if (dockHeartBtn) dockHeartBtn.onclick = () => toggleHeart(dockHeartBtn);

        // Shuffle & Repeat Toggles
        const shuffleBtns = [document.getElementById('agSmHeroShuffleBtn'), document.getElementById('agSmShuffleBtn')];
        shuffleBtns.forEach(btn => {
            if (btn) {
                btn.onclick = () => {
                    const active = !btn.classList.contains('active');
                    shuffleBtns.forEach(b => {
                        if (b) {
                            b.classList.toggle('active', active);
                            b.style.color = active ? '#38bdf8' : '#cbd5e1';
                        }
                    });
                };
            }
        });

        const repeatBtns = [document.getElementById('agSmHeroRepeatBtn'), document.getElementById('agSmRepeatBtn')];
        repeatBtns.forEach(btn => {
            if (btn) {
                btn.onclick = () => {
                    const video = document.querySelector('video');
                    const active = !btn.classList.contains('active');
                    if (video) video.loop = active;
                    repeatBtns.forEach(b => {
                        if (b) {
                            b.classList.toggle('active', active);
                            b.style.color = active ? '#38bdf8' : '#cbd5e1';
                        }
                    });
                };
            }
        });

        // Queue Button Scroll into View
        const queueBtn = document.getElementById('agSmDockQueueBtn');
        if (queueBtn) {
            queueBtn.onclick = () => {
                const list = document.getElementById('agSmRelatedSection');
                if (list) list.scrollIntoView({ behavior: 'smooth' });
            };
        }

        // See All Links
        const recSeeAll = document.getElementById('agSmRecSeeAll');
        if (recSeeAll) recSeeAll.onclick = () => fetchContextualRecommendations('top trending songs 2026');
        const soundSeeAll = document.getElementById('agSmSoundscapesSeeAll');
        if (soundSeeAll) soundSeeAll.onclick = () => {
            const moodSec = document.getElementById('agSmMoodSection');
            if (moodSec) moodSec.scrollIntoView({ behavior: 'smooth' });
        };

        // Brand Logo click
        const brandLogo = document.getElementById('agSmBrandLogo');
        if (brandLogo) {
            brandLogo.onclick = () => {
                const mainEl = document.querySelector('.ag-sm-main');
                if (mainEl) mainEl.scrollTo({ top: 0, behavior: 'smooth' });
            };
        }

        // Attach clicks to mood chips & cards
        document.querySelectorAll('.ag-sm-side-item[data-query], .ag-sm-soundscape-card[data-query], .ag-sm-mood-card[data-query]').forEach(el => {
            el.onclick = () => {
                document.querySelectorAll('.ag-sm-side-item[data-query]').forEach(c => c.classList.remove('active'));
                el.classList.add('active');
                playMoodQuery(el.getAttribute('data-query'));
            };
        });

        const sideMiniCard = document.getElementById('agSmSideMiniCard');
        if (sideMiniCard) {
            sideMiniCard.onclick = () => {
                const hero = document.getElementById('agSmHeroStage');
                if (hero) hero.scrollIntoView({ behavior: 'smooth' });
            };
        }

        // Search Bar in Header
        const searchInput = document.getElementById('agSmSearchInput');
        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const q = searchInput.value.trim();
                    if (q) playMoodQuery(q);
                }
            });
        }

        // Hero Play Button
        const heroPlay = document.getElementById('agSmHeroPlayBtn');
        if (heroPlay) {
            heroPlay.onclick = () => {
                const video = document.querySelector('video');
                if (video) {
                    if (video.paused) video.play().catch(() => {});
                    else video.pause();
                    syncStudioPlayer();
                }
            };
        }

        // Transport Controls
        const smPlayPause = document.getElementById('agSmPlayPauseBtn');
        if (smPlayPause) {
            smPlayPause.onclick = () => {
                const video = document.querySelector('video');
                if (video) {
                    if (video.paused) video.play().catch(() => {});
                    else video.pause();
                    syncStudioPlayer();
                }
            };
        }

        const smPrev = document.getElementById('agSmPrevBtn');
        if (smPrev) {
            smPrev.onclick = () => {
                const video = document.querySelector('video');
                if (video && video.currentTime > 3) video.currentTime = 0;
                else window.history.back();
            };
        }

        const smNext = document.getElementById('agSmNextBtn');
        if (smNext) {
            smNext.onclick = () => {
                const nextBtn = document.querySelector('.ytp-next-button');
                if (nextBtn) nextBtn.click();
            };
        }

        const smSlider = document.getElementById('agSmSlider');
        if (smSlider) {
            smSlider.oninput = () => {
                smSlider._isSeeking = true;
                const pct = smSlider.value;
                smSlider.style.background = `linear-gradient(to right, #00F2FE 0%, #8B5CF6 ${pct}%, rgba(255, 255, 255, 0.15) ${pct}%, rgba(255, 255, 255, 0.15) 100%)`;
            };
            smSlider.onchange = () => {
                const video = document.querySelector('video');
                if (video && !isNaN(video.duration)) {
                    video.currentTime = (smSlider.value / 100) * video.duration;
                }
                smSlider._isSeeking = false;
                syncStudioPlayer();
            };
        }

        const smMute = document.getElementById('agSmMuteBtn');
        const smVol = document.getElementById('agSmVolSlider');
        if (smMute) {
            smMute.onclick = () => {
                const video = document.querySelector('video');
                if (video) {
                    video.muted = !video.muted;
                    syncStudioPlayer();
                }
            };
        }
        if (smVol) {
            smVol.oninput = () => {
                smVol._isSeeking = true;
                const video = document.querySelector('video');
                if (video) {
                    video.volume = smVol.value / 100;
                    video.muted = false;
                }
            };
            smVol.onchange = () => { smVol._isSeeking = false; };
        }

        // MP3 Download Action (Hero + Bottom Bar)
        function handleMp3Download(btn) {
            const videoInfo = getCleanVideoUrl();
            if (!videoInfo || !videoInfo.url) {
                if (btn) {
                    btn.textContent = '⚠️ Play track first!';
                    setTimeout(() => { btn.textContent = '🎵 Download MP3'; }, 2500);
                }
                return;
            }
            if (btn) {
                btn.textContent = '⏳ Adding to Queue...';
                btn.style.background = 'rgba(234, 88, 12, 0.4)';
            }
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.download_current_video(videoInfo.url, videoInfo.title, 'audio')
                    .then(() => {
                        if (btn) {
                            btn.textContent = '✅ MP3 Queued!';
                            btn.style.background = 'rgba(16, 185, 129, 0.4)';
                            setTimeout(() => {
                                btn.textContent = '🎵 Download MP3';
                                btn.style.background = '';
                            }, 3500);
                        }
                    })
                    .catch(() => {
                        if (btn) {
                            btn.textContent = '❌ Failed';
                            setTimeout(() => {
                                btn.textContent = '🎵 Download MP3';
                                btn.style.background = '';
                            }, 2500);
                        }
                    });
            }
        }

        
        // Universal Category & Soundscape Click Listener
        document.addEventListener('click', (e) => {
            const qEl = e.target.closest('[data-query]');
            if (qEl) {
                const query = qEl.getAttribute('data-query');
                if (query) {
                    const searchInput = document.getElementById('agSmSearchInput');
                    if (searchInput) searchInput.value = query;
                    document.querySelectorAll('.ag-sm-side-item[data-query]').forEach(item => {
                        item.classList.toggle('active', item === qEl);
                    });
                    fetchContextualRecommendations(query);
                }
            }
        });

        // Top Search Input Listener
        const studioSearchInput = document.getElementById('agSmSearchInput');
        if (studioSearchInput) {
            studioSearchInput.onkeydown = (ev) => {
                if (ev.key === 'Enter') {
                    const q = studioSearchInput.value.trim();
                    if (q) fetchContextualRecommendations(q);
                }
            };
        }

        // Yuma Mood Filter Chips
        document.querySelectorAll('.ag-sm-chip').forEach(chip => {
            chip.onclick = () => {
                document.querySelectorAll('.ag-sm-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                const q = chip.getAttribute('data-query');
                const searchInp = document.getElementById('agSmSearchInput');
                if (searchInp && q) searchInp.value = q;
                if (q) fetchContextualRecommendations(q);
            };
        });

        const smDlMp3 = document.getElementById('agSmDownloadMp3Btn');
        if (smDlMp3) smDlMp3.onclick = () => handleMp3Download(smDlMp3);
        const heroDlBtn = document.getElementById('agSmHeroDlBtn');
        if (heroDlBtn) heroDlBtn.onclick = () => handleMp3Download(heroDlBtn);

        const smFs = document.getElementById('agSmFsBtn');
        if (smFs && fsBtn) smFs.onclick = () => fsBtn.click();
        const hdrFs = document.getElementById('agSmHdrFsBtn');
        if (hdrFs && fsBtn) hdrFs.onclick = () => fsBtn.click();

        // Hero Controls Wiring
        const heroPrev = document.getElementById('agSmHeroPrevBtn');
        if (heroPrev) heroPrev.onclick = () => { if (smPrev) smPrev.click(); };
        const heroNext = document.getElementById('agSmHeroNextBtn');
        if (heroNext) heroNext.onclick = () => { if (smNext) smNext.click(); };
        const heroShuffle = document.getElementById('agSmHeroShuffleBtn');
        if (heroShuffle) heroShuffle.onclick = () => {
            const shufBtn = document.querySelector('.ytp-shuffle-button');
            if (shufBtn) shufBtn.click();
        };
        const heroRepeat = document.getElementById('agSmHeroRepeatBtn');
        if (heroRepeat) heroRepeat.onclick = () => {
            const video = document.querySelector('video');
            if (video) video.loop = !video.loop;
            heroRepeat.style.color = (video && video.loop) ? '#06b6d4' : '#94a3b8';
        };

        // Like Buttons
        const heroHeart = document.getElementById('agSmHeroHeartBtn');
        const dockHeart = document.getElementById('agSmDockHeartBtn');
        function toggleTrackLike() {
            const isLiked = heroHeart ? heroHeart.classList.toggle('liked') : false;
            if (dockHeart) dockHeart.classList.toggle('liked', isLiked);
            const color = isLiked ? '#f43f5e' : '#94a3b8';
            if (heroHeart) heroHeart.style.color = color;
            if (dockHeart) dockHeart.style.color = color;
        }
        if (heroHeart) heroHeart.onclick = toggleTrackLike;
        if (dockHeart) dockHeart.onclick = toggleTrackLike;

        // Equalizer Drawer Toggles
        const heroEqToggle = document.getElementById('agSmHeroEqToggleBtn');
        const hdrEqToggle = document.getElementById('agSmHdrEqBtn');
        const sideEqToggle = document.getElementById('agSmSideEqBtn');
        const barEqToggle = document.getElementById('agSmBarEqBtn');
        function toggleStudioEq() {
            const eq = document.getElementById('agSmEqDrawer');
            if (eq) eq.classList.toggle('open');
        }
        if (heroEqToggle) heroEqToggle.onclick = toggleStudioEq;
        if (hdrEqToggle) hdrEqToggle.onclick = toggleStudioEq;
        if (sideEqToggle) sideEqToggle.onclick = toggleStudioEq;
        if (barEqToggle) barEqToggle.onclick = toggleStudioEq;

        const sideSpeed = document.getElementById('agSmSideSpeedBtn');
        if (sideSpeed) sideSpeed.onclick = toggleStudioEq;
        const sideTimer = document.getElementById('agSmSideTimerBtn');
        if (sideTimer) sideTimer.onclick = toggleStudioEq;

        // Video Mode Switches
        const heroVidSwitch = document.getElementById('agSmHeroSwitchVideoBtn');
        const hdrVidSwitch = document.getElementById('agSmSwitchToVideoBtn');
        const exitStudio = (e) => {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) e.stopImmediatePropagation();
            }
            setStudioMode(false);
        };
        if (heroVidSwitch) {
            heroVidSwitch.onclick = exitStudio;
            heroVidSwitch.addEventListener('click', exitStudio, true);
        }
        if (hdrVidSwitch) {
            hdrVidSwitch.onclick = exitStudio;
            hdrVidSwitch.addEventListener('click', exitStudio, true);
        }


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
    """Inject permanent adblock CSS shield, cinema styling, controls styling, studio music styling, view switcher, and stealth ad-blocker engine"""
    js_payload = CINEMA_JS.replace("{adblock_css_json}", json.dumps(ADBLOCK_CSS))\
                          .replace("{cinema_css_json}", json.dumps(CINEMA_CSS))\
                          .replace("{controls_css_json}", json.dumps(CONTROLS_CSS))\
                          .replace("{studio_music_css_json}", json.dumps(STUDIO_MUSIC_CSS))\
                          .replace("{studio_assets_json}", json.dumps(STUDIO_ASSETS))
    window.evaluate_js(js_payload)

def main():
    global active_window
    if len(sys.argv) < 2:
        video_id = "https://www.youtube.com"
        title = "YouTube Ad-Free Player"
    else:
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
