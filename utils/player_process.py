import sys
import os
import re
import threading
import ctypes
import time
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from xml.etree import ElementTree
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
_lyrics_cache = {}

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


# BitChord's lyrics repository is provider-first rather than LRCLIB-only. The
# embedded player cannot load its React/extension stack, so the compatible
# provider chain lives in the native bridge and returns the same useful
# distinctions: word-timed, line-timed, or plain lyrics.
LYRICS_PROVIDER_ORDER = (
    "lrc-red",
    "bini",
    "better-lyrics",
    "better-lyrics-portato",
    "lyrics-plus",
    "unison",
    "lrclib",
    "kugou",
    "genius",
)


def _lyrics_get(url, timeout=5.0):
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "StreamFlow-Pro/1.0",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.8",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                return None
            return response.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _lyrics_url(base, **params):
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    return f"{base}?{query}" if query else base


def _lyrics_search_title(title):
    """Match BitChord's removal of packaging/credit text before searching."""
    value = str(title or "").strip()
    patterns = (
        r"\s*[([]\s*(feat|ft|featuring|with)\b[^)\]]*[)\]]",
        r"\s+(feat|ft|featuring)\.?\s+.*$",
        r"\s*[([]\s*(official\s*)?(music\s*)?(video|audio|visualizer|lyrics?\s*video|lyrics?|m/v|hd|hq|4k|full\s*song)\s*[)\]]",
        r"\s*[([]\s*official\s*[)\]]",
    )
    for pattern in patterns:
        value = re.sub(pattern, " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip().rstrip(",–—-").strip()
    return value or str(title or "").strip()


def _lyrics_search_artist(artist):
    value = str(artist or "").strip()
    return re.sub(r"\s+-\s+Topic$", "", value, flags=re.I).strip() or value


def _lyrics_time_ms(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("ms"):
            return int(float(raw[:-2]))
        if raw.endswith("s"):
            return int(float(raw[:-1]) * 1000)
        parts = raw.split(":")
        if len(parts) == 1:
            return int(float(parts[0]) * 1000)
        if len(parts) == 2:
            return int((int(parts[0]) * 60 + float(parts[1])) * 1000)
        if len(parts) == 3:
            return int((int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])) * 1000)
    except (TypeError, ValueError):
        return None
    return None


def _lrc_timestamp(ms):
    total_seconds = max(0, int(ms)) / 1000
    minutes = int(total_seconds // 60)
    seconds = total_seconds - (minutes * 60)
    return f"[{minutes:02d}:{seconds:05.2f}]"


def _plain_from_lrc(lrc):
    lines = []
    for row in str(lrc or "").splitlines():
        text = re.sub(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]", "", row).strip()
        if text and not re.match(r"^\[[A-Za-z]+:.*\]$", text):
            lines.append(text)
    return "\n".join(lines)


def _ttml_to_lrc(document):
    try:
        root = ElementTree.fromstring(document)
    except Exception:
        return "", False

    rows = []
    word_timed = False
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "p":
            continue
        text = "".join(element.itertext()).strip()
        if not text:
            continue
        start = _lyrics_time_ms(element.attrib.get("begin"))
        if start is None:
            for child in element.iter():
                start = _lyrics_time_ms(child.attrib.get("begin"))
                if start is not None:
                    word_timed = True
                    break
        if start is None:
            continue
        if any(_lyrics_time_ms(child.attrib.get("begin")) is not None for child in element.iter() if child is not element):
            word_timed = True
        rows.append((start, text))
    rows.sort(key=lambda row: row[0])
    return "\n".join(f"{_lrc_timestamp(start)}{text}" for start, text in rows), word_timed


def _strip_html_text(document):
    text = re.sub(r"<br\s*/?>", "\n", document, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _normalise_lyrics_document(document):
    """Return (synced LRC, plain text, word_synced) like BitChord's Parsed."""
    if document is None:
        return "", "", False
    if isinstance(document, (dict, list)):
        if isinstance(document, dict):
            synced = document.get("syncedLyrics") or document.get("synced_lyrics") or document.get("lrc")
            plain = document.get("plainLyrics") or document.get("plain_lyrics")
            if synced:
                synced_lrc, word = _normalise_lyrics_document(synced)
                return synced_lrc, str(plain or _plain_from_lrc(synced_lrc)), word
            for key in ("ttml", "ttmlContent", "lyrics", "content", "text", "data", "result", "response"):
                if key in document:
                    result = _normalise_lyrics_document(document[key])
                    if result[0] or result[1]:
                        return result
            return "", "", False
        for item in document:
            result = _normalise_lyrics_document(item)
            if result[0] or result[1]:
                return result
        return "", "", False

    raw = str(document).replace("\ufeff", "").strip()
    if not raw:
        return "", "", False
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, (dict, list)):
            return _normalise_lyrics_document(parsed)
    except (TypeError, ValueError):
        pass

    if re.search(r"<tt(?:\s|>)|http://www\.w3\.org/ns/ttml", raw, flags=re.I):
        lrc, word = _ttml_to_lrc(html_lib.unescape(raw))
        return lrc, _plain_from_lrc(lrc), word
    if re.search(r"^\s*\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]", raw, flags=re.M):
        return raw, _plain_from_lrc(raw), False
    if "<" in raw and ">" in raw:
        raw = _strip_html_text(raw)
    return "", raw, False


def _lyrics_result(source, label, document):
    synced, plain, word_synced = _normalise_lyrics_document(document)
    if not synced and not plain:
        return None
    return {
        "status": "success",
        "source": source,
        "provider": label,
        "plain_lyrics": plain,
        "synced_lyrics": synced,
        "word_synced": word_synced,
    }


def _provider_lrc_red(title, artist, duration):
    body = _lyrics_get(_lyrics_url("https://lrc.red/search.json", q=f"{title} {artist}"))
    try:
        hits = json.loads(body or "{}").get("hits", [])
    except (TypeError, ValueError):
        return None
    wanted = title.casefold()
    seconds = duration if duration and duration > 0 else 0
    candidates = [
        hit for hit in hits
        if hit.get("isrc") and hit.get("title") and wanted in str(hit.get("title", "")).casefold()
        and (not seconds or not hit.get("duration") or abs(float(hit["duration"]) - seconds) <= 3)
    ]
    candidates.sort(key=lambda hit: abs(float(hit.get("duration", seconds)) - seconds) if seconds else 0)
    for hit in candidates:
        isrc = re.sub(r"[^A-Za-z0-9]", "", str(hit.get("isrc", "")).upper())
        if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", isrc):
            document = _lyrics_get(f"https://lrc.red/s/{isrc}.ttml")
            result = _lyrics_result("lrc-red", "lrc.red", document)
            if result:
                return result
    return None


def _provider_bini(title, artist, duration):
    body = _lyrics_get(_lyrics_url("https://lyrics-api.binimum.org/", track=title, artist=artist, duration=duration or None))
    try:
        found = (json.loads(body or "{}").get("results") or [None])[0]
    except (TypeError, ValueError, IndexError):
        found = None
    url = found.get("lyricsUrl") if isinstance(found, dict) else None
    return _lyrics_result("bini", "BiniLyrics", _lyrics_get(url)) if url else None


def _provider_better_lyrics(title, artist, duration, portato=False):
    endpoint = "https://lyrics-api.boidu.dev/qq/getLyrics" if portato else "https://lyrics-api.boidu.dev/getLyrics"
    document = _lyrics_get(_lyrics_url(endpoint, s=title, a=artist, d=duration or None))
    return _lyrics_result("better-lyrics-portato" if portato else "better-lyrics", "BetterLyrics Portato" if portato else "BetterLyrics", document)


def _provider_lyrics_plus(title, artist, duration):
    for host in ("https://lyricsplus.prjktla.my.id", "https://lyricsplus.binimum.org"):
        body = _lyrics_get(_lyrics_url(f"{host}/v2/lyrics/get", title=title, artist=artist, duration=duration or None))
        try:
            payload = json.loads(body or "{}")
        except (TypeError, ValueError):
            continue
        rows = []
        for row in payload.get("lyrics", []) if isinstance(payload, dict) else []:
            if not isinstance(row, dict) or not isinstance(row.get("time"), (int, float)):
                continue
            text = str(row.get("text") or "").strip()
            if text:
                rows.append(f"{_lrc_timestamp(row['time'])}{text}")
        result = _lyrics_result("lyrics-plus", "LyricsPlus", "\n".join(rows))
        if result:
            return result
    return None


def _provider_unison(title, artist, duration):
    body = _lyrics_get(_lyrics_url("https://unison.boidu.dev/lyrics", song=title, artist=artist, duration=duration or None))
    return _lyrics_result("unison", "Unison", body)


def _provider_lrclib(title, artist, duration):
    exact = _lyrics_get(_lyrics_url("https://lrclib.net/api/get", track_name=title, artist_name=artist, duration=duration or None))
    result = _lyrics_result("lrclib", "LRCLIB", exact)
    if result:
        return result
    body = _lyrics_get(_lyrics_url("https://lrclib.net/api/search", track_name=title, artist_name=artist))
    try:
        hits = json.loads(body or "[]")
    except (TypeError, ValueError):
        return None
    hits = [hit for hit in hits if isinstance(hit, dict) and (hit.get("syncedLyrics") or hit.get("plainLyrics"))]
    hits.sort(key=lambda hit: abs(float(hit.get("duration", duration or 0)) - (duration or 0)))
    return _lyrics_result("lrclib", "LRCLIB", hits[0] if hits else None)


def _provider_kugou(title, artist, duration):
    keyword = f"{title} - {artist}".strip(" -")
    body = _lyrics_get(_lyrics_url("https://mobileservice.kugou.com/api/v3/search/song", version=9108, plat=0, pagesize=8, showtype=0, keyword=keyword))
    try:
        songs = json.loads(body or "{}").get("data", {}).get("info", [])
    except (TypeError, ValueError):
        return None
    seconds = duration or 0
    songs = [song for song in songs if not seconds or not song.get("duration") or abs(float(song["duration"]) - seconds) <= 8]
    songs.sort(key=lambda song: abs(float(song.get("duration", seconds)) - seconds) if seconds else 0)
    for song in songs:
        search = _lyrics_get(_lyrics_url("https://lyrics.kugou.com/search", ver=1, man="yes", client="pc", hash=song.get("hash")))
        try:
            candidate = (json.loads(search or "{}").get("candidates") or [None])[0]
        except (TypeError, ValueError, IndexError):
            candidate = None
        if not candidate:
            continue
        downloaded = _lyrics_get(_lyrics_url("https://lyrics.kugou.com/download", fmt="lrc", charset="utf8", client="pc", ver=1, id=candidate.get("id"), accesskey=candidate.get("accesskey")))
        try:
            encoded = json.loads(downloaded or "{}").get("content")
            lrc = base64.b64decode(encoded).decode("utf-8", errors="replace") if encoded else ""
        except (TypeError, ValueError, KeyError):
            lrc = ""
        result = _lyrics_result("kugou", "KuGou", lrc)
        if result and not re.search(r"纯音乐.*欣赏", result["plain_lyrics"]):
            return result
    return None


def _provider_genius(title, artist):
    body = _lyrics_get(_lyrics_url("https://genius.com/api/search/multi", q=f"{artist} {title}"), timeout=6.0)
    try:
        sections = json.loads(body or "{}").get("response", {}).get("sections", [])
        hits = next((section.get("hits", []) for section in sections if section.get("type") == "song"), [])
    except (TypeError, ValueError):
        return None
    wanted_title = title.casefold()
    wanted_artist = artist.casefold()
    scored = []
    for entry in hits:
        result = entry.get("result", {}) if isinstance(entry, dict) else {}
        hit_title = str(result.get("title", ""))
        hit_artist = str(result.get("artist_names", ""))
        score = (50 if hit_title.casefold() == wanted_title else 25 if wanted_title in hit_title.casefold() else 0)
        score += 40 if hit_artist.casefold() == wanted_artist else 20 if wanted_artist in hit_artist.casefold() else 0
        if score and result.get("url"):
            scored.append((score, result["url"]))
    for _, url in sorted(scored, reverse=True):
        page = _lyrics_get(url, timeout=6.0)
        if not page:
            continue
        containers = re.findall(r'<div[^>]+data-lyrics-container="true"[^>]*>(.*?)</div>', page, flags=re.I | re.S)
        if not containers:
            containers = re.findall(r'<div[^>]*class="lyrics"[^>]*>(.*?)</div>', page, flags=re.I | re.S)
        text = "\n".join(_strip_html_text(container) for container in containers).strip()
        result = _lyrics_result("genius", "Genius", text)
        if result:
            return result
    return None


def _lookup_lyrics(title, artist, duration):
    title = _lyrics_search_title(title)
    artist = _lyrics_search_artist(artist)
    providers = {
        "lrc-red": lambda: _provider_lrc_red(title, artist, duration),
        "bini": lambda: _provider_bini(title, artist, duration),
        "better-lyrics": lambda: _provider_better_lyrics(title, artist, duration),
        "better-lyrics-portato": lambda: _provider_better_lyrics(title, artist, duration, True),
        "lyrics-plus": lambda: _provider_lyrics_plus(title, artist, duration),
        "unison": lambda: _provider_unison(title, artist, duration),
        "lrclib": lambda: _provider_lrclib(title, artist, duration),
        "kugou": lambda: _provider_kugou(title, artist, duration),
        "genius": lambda: _provider_genius(title, artist),
    }
    results = {}
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(providers[source]): source for source in providers}
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                if result:
                    results[source] = result
            except Exception:
                continue

    plain = None
    line_synced = None
    for source in LYRICS_PROVIDER_ORDER:
        result = results.get(source)
        if not result:
            continue
        result["synced"] = bool(result.get("synced_lyrics"))
        if result.get("word_synced"):
            return result
        if result["synced"]:
            line_synced = line_synced or result
        else:
            plain = plain or result
    return line_synced or plain


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

    def get_lyrics(self, title="", artist="", duration=None):
        """Run BitChord's prioritized multi-provider lyrics lookup."""
        global _lyrics_cache
        track_name = str(title or "").strip()[:180]
        artist_name = str(artist or "").strip()[:180]
        if not track_name:
            return {"status": "empty", "message": "Play a track to load lyrics."}

        duration_seconds = 0
        try:
            duration_seconds = max(0, int(float(duration or 0)))
        except (TypeError, ValueError):
            pass
        key = (track_name.casefold(), artist_name.casefold(), duration_seconds)
        now = time.time()
        cached = _lyrics_cache.get(key)
        if cached and now - cached["time"] < 900:
            return cached["data"]

        try:
            result = _lookup_lyrics(track_name, artist_name, duration_seconds)
            if not result:
                result = {"status": "not_found", "message": "None of the lyric providers has this song."}
        except Exception:
            result = {"status": "not_found", "message": "Lyrics are unavailable for this track."}

        _lyrics_cache[key] = {"time": now, "data": result}
        return result

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
#player-ads,
.ytp-ad-player-overlay,
.ytp-ad-player-overlay-layout,
.ytp-ad-persistent-progress-bar-container,
.ytp-ad-preview-slot,
.ytp-ad-action-interstitial-background,
.ytp-ad-action-interstitial-slot,
ytd-player-legacy-desktop-watch-ads-renderer,
#companion,
#panels:has(ytd-ads-engagement-panel-content-renderer) {
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
ytd-engagement-panel-section-list-renderer[target-id*="ad"],
/* Brave procedural cosmetic filters for empty grid slots */
ytd-rich-item-renderer:has(ytd-ad-slot-renderer),
ytd-rich-item-renderer:has(ytd-in-feed-ad-layout-renderer),
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
ytd-mealbar-promo-renderer,
tp-yt-iron-overlay-backdrop:has(+ tp-yt-paper-dialog ytd-enforcement-message-view-model) {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
"""

DOCUMENT_START_ADBLOCK_JS = r"""
(function() {
    'use strict';
    try {
        const injectCss = () => {
            if (document.getElementById('ag-early-adblock-style')) return;
            const style = document.createElement('style');
            style.id = 'ag-early-adblock-style';
            style.textContent = `
                ytd-ad-slot-renderer,
                ytd-in-feed-ad-layout-renderer,
                ytd-player-legacy-desktop-watch-ads-renderer,
                .ytp-ad-module,
                .ytp-ad-overlay-container,
                .ytp-ad-player-overlay,
                .ytp-ad-player-overlay-layout,
                .ytp-ad-image-overlay,
                .ytp-ad-text-overlay,
                #player-ads,
                #masthead-ad,
                ytd-banner-promo-renderer,
                ytd-enforcement-message-view-model,
                tp-yt-paper-dialog:has(ytd-enforcement-message-view-model),
                tp-yt-paper-dialog:has(yt-upsell-dialog-renderer),
                yt-upsell-dialog-renderer {
                    display: none !important;
                    visibility: hidden !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                }
            `;
            const root = document.head || document.documentElement;
            if (root) root.appendChild(style);
        };
        injectCss();
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', injectCss);
        }
    } catch(err) {}
})();
"""

def setup_strict_adblock():
    """
    Installs safe document-start CSS pre-injection via CoreWebView2.
    Hides all ad placeholders and anti-adblock modals instantly from frame 0.
    """
    try:
        import webview.platforms.edgechromium as edge
        orig_ready = edge.EdgeChrome.on_webview_ready
        
        def patched_webview_ready(self, sender, args):
            orig_ready(self, sender, args)
            if hasattr(sender, "CoreWebView2") and sender.CoreWebView2:
                try:
                    sender.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(DOCUMENT_START_ADBLOCK_JS)
                except Exception as e:
                    logging.debug(f"Document-start adblock hook: {e}")
                try:
                    sender.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(get_cinema_payload())
                except Exception as e:
                    logging.debug(f"Document-start cinema hook: {e}")
                    
        edge.EdgeChrome.on_webview_ready = patched_webview_ready
        logging.info("Strict safe document-start adblock and cinema controls shield installed.")
    except Exception as e:
        logging.info(f"Document-start shield fallback: {e}")



CINEMA_CSS = """
/* Hide external YouTube UI: headers, sidebar recommendations, comments ONLY in Cinema Mode */
body.ag-cinema-active #masthead-container, 
body.ag-cinema-active #masthead, 
body.ag-cinema-active #guide, 
body.ag-cinema-active #guide-wrapper, 
body.ag-cinema-active #secondary, 
body.ag-cinema-active #comments, 
body.ag-cinema-active #below, 
body.ag-cinema-active #chat, 
body.ag-cinema-active #ticker, 
body.ag-cinema-active #voice-search-button, 
body.ag-cinema-active #chips, 
body.ag-cinema-active ytd-feed-filter-chip-bar-renderer {
    display: none !important;
}

/* Base full viewport reset ONLY in Cinema Mode */
body.ag-cinema-active,
body.ag-cinema-active html {
    overflow: hidden !important;
    background-color: #000000 !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
}

/* Master Player Container Expansion ONLY in Cinema Mode */
body.ag-cinema-active #movie_player, 
body.ag-cinema-active .html5-video-player {
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

/* Ensure Video Container fills the space correctly in Cinema Mode */
body.ag-cinema-active .html5-video-container {
    width: 100% !important;
    height: 100% !important;
}

body.ag-cinema-active .html5-video-container video {
    width: 100% !important;
    height: 100% !important;
    top: 0 !important;
    left: 0 !important;
    object-fit: contain !important;
}

/* Ensure Controls Bar, Settings Menu, Subtitles, and Seekbar are ON TOP in Cinema Mode */
body.ag-cinema-active .ytp-chrome-bottom, 
body.ag-cinema-active .ytp-chrome-top, 
body.ag-cinema-active .ytp-gradient-bottom, 
body.ag-cinema-active .ytp-gradient-top, 
body.ag-cinema-active .ytp-popup, 
body.ag-cinema-active .ytp-settings-menu, 
body.ag-cinema-active .ytp-panel, 
body.ag-cinema-active .ytp-menuitem, 
body.ag-cinema-active .ytp-caption-window-container {
    z-index: 2000000000 !important;
}
"""

CONTROLS_CSS = """
/* StreamFlow Floating Control Dock - Collapsed by default into sleek pill, expands smoothly on hover */
#antigravity-top-controls {
    position: fixed;
    bottom: 24px;
    right: 24px;
    top: auto;
    left: auto;
    transform: none;
    z-index: 2147483647;
    pointer-events: auto;
    display: inline-flex;
    flex-direction: row-reverse;
    align-items: center;
    gap: 8px;
    opacity: 0.95;
    transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1), 
                transform 0.3s cubic-bezier(0.16, 1, 0.3, 1),
                box-shadow 0.3s ease,
                background 0.3s ease;
    max-width: 96vw;
    background: rgba(15, 23, 42, 0.88);
    padding: 4px 6px;
    border-radius: 9999px;
    border: 1px solid rgba(255, 255, 255, 0.18);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    cursor: default;
    user-select: none;
}

#antigravity-top-controls:hover,
#antigravity-top-controls.ag-dock-expanded,
#antigravity-top-controls.ag-dock-pinned {
    opacity: 1;
    background: rgba(15, 23, 42, 0.95);
    border-color: rgba(255, 255, 255, 0.28);
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.65), 0 0 20px rgba(245, 158, 11, 0.15);
}

/* In Cinema Mode (YouTube header hidden, player fills screen), float top center */
body.ag-cinema-active #antigravity-top-controls {
    bottom: auto;
    right: auto;
    top: 14px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(15, 23, 42, 0.75);
}

/* On YouTube Music, float right just above the bottom player bar */
body.ag-music-site #antigravity-top-controls {
    bottom: 84px;
    right: 24px;
}

#antigravity-top-controls.hidden {
    opacity: 0 !important;
    pointer-events: none !important;
    transform: translateY(12px);
}

body.ag-cinema-active #antigravity-top-controls.hidden {
    transform: translateX(-50%) translateY(-12px);
}

/* Smooth expandable actions container: collapsed by default, expands on hover */
.ag-dock-actions {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: 0;
    opacity: 0;
    overflow: hidden;
    pointer-events: none;
    transform: scale(0.95);
    transition: max-width 0.35s cubic-bezier(0.16, 1, 0.3, 1), 
                opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1), 
                transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    white-space: nowrap;
}

#antigravity-top-controls:hover .ag-dock-actions,
#antigravity-top-controls.ag-dock-hovered .ag-dock-actions,
#antigravity-top-controls.ag-dock-expanded .ag-dock-actions {
    max-width: 1000px;
    opacity: 1;
    pointer-events: auto;
    transform: scale(1);
}

/* Persistent Top-Left Page Navigation Back Button for YouTube */
#antigravity-page-back-btn {
    position: fixed !important;
    top: 9px !important;
    left: 14px !important;
    z-index: 2147483646 !important;
    width: 38px !important;
    height: 38px !important;
    border-radius: 50% !important;
    background: rgba(15, 23, 42, 0.88) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255, 255, 255, 0.22) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1),
                transform 0.2s cubic-bezier(0.16, 1, 0.3, 1),
                background 0.2s ease,
                border-color 0.2s ease,
                box-shadow 0.2s ease !important;
    user-select: none !important;
    pointer-events: auto !important;
}

#antigravity-page-back-btn:hover {
    background: #2563EB !important;
    border-color: #60A5FA !important;
    transform: scale(1.08) !important;
    box-shadow: 0 6px 22px rgba(37, 99, 235, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.35) !important;
}

#antigravity-page-back-btn:active {
    transform: scale(0.94) !important;
}

#antigravity-page-back-btn svg {
    width: 18px !important;
    height: 18px !important;
    stroke: #FFFFFF !important;
    transition: transform 0.2s ease !important;
}

#antigravity-page-back-btn:hover svg {
    transform: translateX(-2px) !important;
}

#antigravity-page-back-btn.hidden {
    opacity: 0 !important;
    pointer-events: none !important;
    transform: translateX(-12px) !important;
}

/* In regular YouTube, shift masthead start by 48px so back button sits cleanly */
ytd-masthead #start,
#masthead #start {
    margin-left: 48px !important;
}

/* In Cinema Mode, adjust position and handle inactivity fade */
body.ag-cinema-active #antigravity-page-back-btn {
    top: 14px !important;
    left: 18px !important;
    background: rgba(15, 23, 42, 0.85) !important;
}

.ag-back-btn {
    background: rgba(30, 41, 59, 0.92) !important;
    border-color: rgba(255, 255, 255, 0.28) !important;
    color: #F8FAFC !important;
}

.ag-back-btn:hover {
    background: #2563EB !important;
    border-color: #60A5FA !important;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4) !important;
}

/* Sleek StreamFlow Brand Trigger Pill */
.ag-toggle-btn {
    background: rgba(255, 255, 255, 0.10) !important;
    border: 1px solid rgba(255, 255, 255, 0.22) !important;
    color: #FFFFFF !important;
    padding: 6px 14px !important;
    border-radius: 9999px !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: -0.2px !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 7px !important;
    cursor: pointer !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.ag-toggle-btn:hover {
    background: rgba(255, 255, 255, 0.18) !important;
    border-color: rgba(255, 255, 255, 0.38) !important;
    transform: scale(1.03) !important;
}

#antigravity-top-controls.ag-dock-pinned .ag-toggle-btn {
    background: rgba(245, 158, 11, 0.22) !important;
    border-color: rgba(245, 158, 11, 0.6) !important;
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.35) !important;
}

.ag-toggle-btn .ag-bolt {
    color: #f59e0b;
    font-size: 14px;
    line-height: 1;
    display: inline-block;
    filter: drop-shadow(0 0 6px rgba(245, 158, 11, 0.6));
    animation: agBoltPulse 2.5s infinite ease-in-out;
}

@keyframes agBoltPulse {
    0%, 100% { transform: scale(1); opacity: 0.95; }
    50% { transform: scale(1.15); opacity: 1; filter: drop-shadow(0 0 10px rgba(245, 158, 11, 0.9)); }
}

.ag-toggle-btn .ag-brand-text {
    font-weight: 700;
    color: #FFFFFF;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

.ag-toggle-btn .ag-chevron {
    font-size: 11px;
    opacity: 0.75;
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    display: inline-block;
}

#antigravity-top-controls:hover .ag-chevron,
#antigravity-top-controls.ag-dock-expanded .ag-chevron,
#antigravity-top-controls.ag-dock-pinned .ag-chevron {
    transform: rotate(180deg);
    opacity: 1;
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
   StreamFlow Studio — BitChord Edition
   Apple Music-inspired dark player · DM Sans · #FA243C coral-red accent
   ========================================================================== */

@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap');

/* ── DESIGN TOKENS ───────────────────────────────────────────────────────── */
:root, #antigravity-studio-music {
    /* Backgrounds */
    --bc-bg:           #000000;
    --bc-surface:      #161618;
    --bc-elevated:     #242426;
    --bc-glass:        rgba(28, 28, 30, 0.82);
    --bc-glass-hover:  rgba(40, 40, 44, 0.90);
    /* Accent */
    --bc-accent:       #FA243C;
    --bc-accent-glow:  rgba(250, 36, 60, 0.35);
    --bc-accent-bg:    rgba(250, 36, 60, 0.12);
    /* Text */
    --bc-text:         #FFFFFF;
    --bc-text-sub:     rgba(255, 255, 255, 0.65);
    --bc-text-muted:   rgba(255, 255, 255, 0.40);
    /* Borders */
    --bc-border:       rgba(255, 255, 255, 0.10);
    --bc-border-hover: rgba(255, 255, 255, 0.20);
    /* Legacy names (keep existing JS working) */
    --ambient-bg:      #000000;
    --ambient-color-1: rgba(250, 36, 60, 0.18);
    --ambient-color-2: rgba(40, 70, 130, 0.22);
    --yuma-accent:     #FA243C;
    --yuma-accent-glow: rgba(250, 36, 60, 0.35);
    --text-main:       #FFFFFF;
    --text-sub:        rgba(255, 255, 255, 0.65);
    --text-muted:      rgba(255, 255, 255, 0.40);
    --glass-surface:   rgba(255, 255, 255, 0.04);
    --glass-surface-hover: rgba(255, 255, 255, 0.08);
    --glass-border:    rgba(255, 255, 255, 0.10);
    --glass-border-hover: rgba(255, 255, 255, 0.20);
}

/* ── ROOT CONTAINER ──────────────────────────────────────────────────────── */
#antigravity-studio-music {
    position: fixed !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    z-index: 2147483640 !important;
    background: #000000 !important;
    color: var(--bc-text) !important;
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
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

/* ── AMBIENT AURORA MESH ─────────────────────────────────────────────────── */
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
    width: 55vw;
    height: 60vh;
    top: -15%;
    left: -8%;
    background: radial-gradient(circle, var(--ambient-color-1) 0%, transparent 65%);
    filter: blur(100px);
    opacity: 0.70;
    animation: agAuroraFloat1 24s ease-in-out infinite alternate;
    transition: background 1.8s ease;
}
.ag-sm-ambient-mesh::after {
    content: '';
    position: absolute;
    width: 50vw;
    height: 55vh;
    bottom: -8%;
    right: -4%;
    background: radial-gradient(circle, var(--ambient-color-2) 0%, transparent 65%);
    filter: blur(110px);
    opacity: 0.60;
    animation: agAuroraFloat2 28s ease-in-out infinite alternate;
    transition: background 1.8s ease;
}

@keyframes agAuroraFloat1 {
    0%   { transform: translate(0, 0) scale(1); }
    50%  { transform: translate(5vw, 3vh) scale(1.06); }
    100% { transform: translate(-3vw, 7vh) scale(0.97); }
}
@keyframes agAuroraFloat2 {
    0%   { transform: translate(0, 0) scale(1); }
    50%  { transform: translate(-6vw, -4vh) scale(1.09); }
    100% { transform: translate(2vw, -7vh) scale(0.96); }
}

/* ── SCOPED SCROLLBARS ───────────────────────────────────────────────────── */
#antigravity-studio-music ::-webkit-scrollbar { width: 4px; height: 4px; }
#antigravity-studio-music ::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.14);
    border-radius: 9999px;
}
#antigravity-studio-music ::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.28);
}
#antigravity-studio-music ::-webkit-scrollbar-track { background: transparent; }

/* ── TOP HEADER ──────────────────────────────────────────────────────────── */
.ag-sm-header {
    height: 56px;
    background: rgba(0, 0, 0, 0.72);
    backdrop-filter: blur(28px) saturate(200%);
    -webkit-backdrop-filter: blur(28px) saturate(200%);
    border-bottom: 1px solid var(--bc-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    z-index: 50;
    position: relative;
    flex-shrink: 0;
}
.ag-sm-header-left,
.ag-sm-header-right {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}

.ag-sm-back-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    color: var(--bc-text-sub);
    background: transparent;
    border: 1px solid transparent;
    transition: all 0.18s ease;
}
.ag-sm-back-arrow:hover {
    background: var(--bc-glass);
    border-color: var(--bc-border);
    color: var(--bc-text);
}

.ag-sm-brand { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.ag-sm-brand-icon {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 16px;
}
.ag-sm-brand-icon span {
    width: 3px;
    border-radius: 2px;
    background: var(--bc-accent);
    animation: agEqDance 1.1s ease-in-out infinite alternate;
}
.ag-sm-brand-icon span:nth-child(1) { height: 8px;  animation-delay: 0s; }
.ag-sm-brand-icon span:nth-child(2) { height: 14px; animation-delay: 0.15s; }
.ag-sm-brand-icon span:nth-child(3) { height: 10px; animation-delay: 0.30s; }
.ag-sm-brand-icon span:nth-child(4) { height: 16px; animation-delay: 0.45s; }
.ag-sm-brand-icon span:nth-child(5) { height: 7px;  animation-delay: 0.60s; }

@keyframes agEqDance {
    0%   { transform: scaleY(0.5); opacity: 0.6; }
    100% { transform: scaleY(1);   opacity: 1.0; }
}

.ag-sm-brand-text {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: var(--bc-text);
}
.ag-sm-brand-badge { display: none; }

.ag-sm-header-center {
    flex: 1;
    display: flex;
    justify-content: center;
    padding: 0 20px;
    min-width: 0;
}
.ag-sm-search-capsule {
    display: flex;
    align-items: center;
    gap: 10px;
    width: min(460px, 44vw);
    height: 36px;
    background: rgba(118, 118, 128, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 999px;
    padding: 0 14px;
    transition: all 0.22s ease;
    color: var(--bc-text-muted);
}
.ag-sm-search-capsule:focus-within {
    width: min(520px, 50vw);
    background: rgba(118, 118, 128, 0.22);
    border-color: rgba(255, 255, 255, 0.24);
    color: var(--bc-text-sub);
}
.ag-sm-search-capsule input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    color: var(--bc-text);
    font-size: 13px;
    font-family: inherit;
    caret-color: var(--bc-accent);
}
.ag-sm-search-capsule input::placeholder { color: rgba(255, 255, 255, 0.35); }

.ag-sm-hdr-icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    color: var(--bc-text-sub);
    background: transparent;
    border: 1px solid transparent;
    transition: all 0.18s ease;
}
.ag-sm-hdr-icon-btn:hover {
    background: var(--bc-glass);
    border-color: var(--bc-border);
    color: var(--bc-text);
}
.ag-sm-hdr-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    color: var(--bc-text-sub);
    background: transparent;
    border: 1px solid transparent;
    transition: all 0.18s ease;
}
.ag-sm-hdr-btn:hover {
    background: var(--bc-glass);
    border-color: var(--bc-border);
    color: var(--bc-text);
}
.ag-sm-hdr-btn span { font-size: 12px; }

/* ── CONTENT STAGE ───────────────────────────────────────────────────────── */
.ag-sm-content-stage {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(380px, 36vw);
    flex: 1;
    min-height: 0;
    position: relative;
    z-index: 2;
}

/* ── RIGHT PANEL ─────────────────────────────────────────────────────────── */
.ag-sm-right-stage {
    grid-column: 1;
    grid-row: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    padding: 20px 22px 24px;
    gap: 12px;
    background: rgba(10, 10, 12, 0.18);
    overflow: hidden;
}

/* ── LEFT PLAYER ─────────────────────────────────────────────────────────── */
.ag-sm-left-player {
    grid-column: 2;
    grid-row: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 0;
    padding: clamp(20px, 3.5vh, 44px) clamp(22px, 2.5vw, 50px) 20px;
    gap: 18px;
    background: rgba(0, 0, 0, 0.42);
    border-left: 1px solid var(--bc-border);
    overflow: hidden;
}

/* Artwork */
.ag-sm-art-wrap {
    width: 100%;
    display: flex;
    justify-content: center;
    padding: 0;
    min-height: 0;
}
.ag-sm-art-container {
    position: relative;
    width: min(28vw, 320px);
    height: min(28vw, 320px);
    max-width: 100%;
    max-height: 40vh;
    display: flex;
    align-items: center;
    justify-content: center;
}
.ag-sm-vinyl-disc {
    position: absolute;
    right: -14%;
    top: 50%;
    transform: translateY(-50%);
    width: 90%;
    height: 90%;
    border-radius: 50%;
    background: radial-gradient(circle at 50% 50%,
        #1a1a1a 0%, #111 20%, #0a0a0a 25%,
        #1c1c1c 30%, #0d0d0d 40%, #1a1a1a 50%,
        #0d0d0d 60%, #1c1c1c 70%, #0d0d0d 80%, #000 100%);
    box-shadow: 0 8px 40px rgba(0,0,0,0.6);
    opacity: 0.72;
    z-index: 0;
}
.ag-sm-vinyl-grooves {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: repeating-radial-gradient(circle,
        transparent, transparent 3px, rgba(255,255,255,0.025) 3px, rgba(255,255,255,0.025) 4px);
}
.ag-sm-vinyl-label {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 32%; height: 32%;
    border-radius: 50%;
    background: var(--bc-accent);
    display: flex;
    align-items: center;
    justify-content: center;
}
.ag-sm-vinyl-hole {
    width: 20%; height: 20%;
    border-radius: 50%;
    background: #000;
}
.ag-sm-art-sleeve {
    position: relative;
    z-index: 1;
    width: 100%; height: 100%;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 24px 64px rgba(0,0,0,0.72), 0 0 0 1px rgba(255,255,255,0.14), 0 0 48px -16px var(--bc-accent-glow);
    transition: box-shadow 1.4s ease;
}
.ag-sm-art-gloss {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, transparent 60%);
    pointer-events: none;
}
.ag-sm-art-img {
    width: 100%; height: 100%;
    object-fit: cover;
    display: block;
    border-radius: 16px;
    transition: opacity 0.4s ease;
    opacity: 0.3;
}
.ag-sm-art-img.loaded { opacity: 1; }
.ag-sm-art-wrap.is-playing .ag-sm-art-sleeve {
    box-shadow: 0 24px 64px rgba(0,0,0,0.72), 0 0 0 1px rgba(255,255,255,0.18), 0 0 72px -4px var(--bc-accent-glow);
    animation: agArtPulse 3s ease-in-out infinite;
}
@keyframes agArtPulse {
    0%, 100% { box-shadow: 0 24px 64px rgba(0,0,0,0.72), 0 0 0 1px rgba(255,255,255,0.18), 0 0 56px -8px var(--bc-accent-glow); }
    50%       { box-shadow: 0 24px 64px rgba(0,0,0,0.72), 0 0 0 1px rgba(255,255,255,0.22), 0 0 72px -4px var(--bc-accent-glow); }
}
.ag-sm-art-wrap.is-playing .ag-sm-vinyl-disc {
    animation: agVinylSpin 2.4s linear infinite;
}
@keyframes agVinylSpin {
    from { transform: translateY(-50%) rotate(0deg); }
    to   { transform: translateY(-50%) rotate(360deg); }
}

/* Track info */
.ag-sm-info-row {
    width: 100%;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 0 2px;
}
.ag-sm-info-text { flex: 1; min-width: 0; }
.ag-sm-hero-title {
    font-size: clamp(17px, 1.8vw, 23px);
    font-weight: 700;
    letter-spacing: -0.5px;
    color: var(--bc-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.2;
}
.ag-sm-hero-artist-wrap { margin-top: 4px; }
.ag-sm-hero-artist {
    font-size: 13px;
    font-weight: 500;
    color: var(--bc-text-sub);
}

/* Heart button */
.ag-sm-heart-btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    color: var(--bc-text-muted);
    transition: all 0.18s ease;
}
.ag-sm-heart-btn:hover { color: var(--bc-accent); transform: scale(1.1); }
.ag-sm-heart-btn.active { color: var(--bc-accent); background: var(--bc-accent-bg); }

/* Hi-Fi badge */
.ag-sm-hifi-row { width: 100%; }
.ag-sm-badge-capsule {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: rgba(250, 36, 60, 0.08);
    border: 1px solid rgba(250, 36, 60, 0.22);
    border-radius: 999px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: var(--bc-accent);
    text-transform: uppercase;
}
.ag-sm-dac-led {
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--bc-accent);
    box-shadow: 0 0 6px var(--bc-accent);
    animation: agLedPulse 1.8s ease-in-out infinite;
}
.ag-sm-dac-text { font-size: 9px; letter-spacing: 0.5px; }
@keyframes agLedPulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
}

/* Seek bar */
.ag-sm-seek-section { width: 100%; }
.ag-sm-seek-wrap { width: 100%; }
.ag-sm-slider {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 3px;
    border-radius: 999px;
    outline: none;
    cursor: pointer;
    background: linear-gradient(to right, var(--bc-accent) 0%, var(--bc-accent) 0%, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.14) 100%);
    transition: height 0.15s ease;
}
.ag-sm-slider:hover { height: 5px; }
.ag-sm-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px; height: 14px;
    border-radius: 50%;
    background: var(--bc-text);
    box-shadow: 0 0 0 2px var(--bc-accent);
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s ease;
}
.ag-sm-slider:hover::-webkit-slider-thumb { opacity: 1; }
.ag-sm-timestamps {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    font-size: 11px;
    font-weight: 500;
    color: var(--bc-text-muted);
}

/* Transport controls */
.ag-sm-transport-row {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
}
.ag-sm-transport-capsule {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 6px 18px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--bc-border);
    border-radius: 999px;
    backdrop-filter: blur(16px);
}
.ag-sm-trans-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px; height: 36px;
    color: var(--bc-text);
    opacity: 0.80;
    transition: opacity 0.15s ease, transform 0.15s ease;
}
.ag-sm-trans-btn:hover { opacity: 1; transform: scale(1.08); }
.ag-sm-play-circle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 50px; height: 50px;
    border-radius: 50%;
    background: var(--bc-accent);
    box-shadow: 0 4px 20px var(--bc-accent-glow);
    color: #fff;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.ag-sm-play-circle:hover {
    transform: scale(1.06);
    box-shadow: 0 6px 28px var(--bc-accent-glow);
}
.ag-sm-play-circle svg { fill: #ffffff; }

/* Shuffle / Repeat */
.ag-sm-flank-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px; height: 36px;
    border-radius: 50%;
    color: var(--bc-text-muted);
    background: transparent;
    border: 1px solid transparent;
    transition: all 0.18s ease;
}
.ag-sm-flank-btn:hover {
    color: var(--bc-text-sub);
    background: rgba(255,255,255,0.06);
    border-color: var(--bc-border);
}
.ag-sm-flank-btn.active {
    color: var(--bc-accent);
    background: var(--bc-accent-bg);
    border-color: rgba(250, 36, 60, 0.28);
}

/* Deck utilities */
.ag-sm-deck-utilities {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--bc-border);
}
.ag-sm-vol-cluster {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
}
.ag-sm-vol-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--bc-text-muted);
    transition: color 0.15s ease;
}
.ag-sm-vol-btn:hover { color: var(--bc-text); }
.ag-sm-vol-slider {
    -webkit-appearance: none;
    appearance: none;
    flex: 1;
    max-width: 90px;
    height: 3px;
    border-radius: 999px;
    outline: none;
    cursor: pointer;
    background: linear-gradient(to right, var(--bc-accent) 100%, rgba(255,255,255,0.14) 100%);
}
.ag-sm-vol-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px; height: 12px;
    border-radius: 50%;
    background: var(--bc-text);
    cursor: pointer;
}
.ag-sm-deck-actions {
    display: flex;
    align-items: center;
    gap: 6px;
}
.ag-sm-hero-dl-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 30px;
    padding: 0 12px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    color: var(--bc-text-sub);
    background: rgba(255,255,255,0.06);
    border: 1px solid var(--bc-border);
    transition: all 0.18s ease;
}
.ag-sm-hero-dl-btn:hover {
    background: rgba(255,255,255,0.12);
    color: var(--bc-text);
    border-color: var(--bc-border-hover);
}
.ag-sm-sheet-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px; height: 32px;
    border-radius: 50%;
    color: var(--bc-text-muted);
    background: transparent;
    border: 1px solid transparent;
    transition: all 0.18s ease;
}
.ag-sm-sheet-btn:hover {
    background: rgba(255,255,255,0.08);
    border-color: var(--bc-border);
    color: var(--bc-text-sub);
}
.ag-sm-sheet-btn.active {
    color: #000;
    background: var(--bc-text);
    border-color: var(--bc-text);
}

/* AutoMix / Crossfade toggles */
.ag-sm-toggle-row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--bc-border);
}
.ag-sm-toggle-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    height: 30px;
    border-radius: 999px;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.2px;
    color: var(--bc-text-muted);
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--bc-border);
    transition: all 0.18s ease;
    font-family: inherit;
}
.ag-sm-toggle-btn:hover {
    color: var(--bc-text-sub);
    background: rgba(255,255,255,0.09);
    border-color: var(--bc-border-hover);
}
.ag-sm-toggle-btn.active {
    color: var(--bc-accent);
    background: var(--bc-accent-bg);
    border-color: rgba(250, 36, 60, 0.30);
}
.ag-sm-toggle-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.6;
    transition: opacity 0.18s;
}
.ag-sm-toggle-btn.active .ag-sm-toggle-dot { opacity: 1; }

/* Panel tabs */
.ag-sm-panel-tabs {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px;
    background: rgba(118, 118, 128, 0.12);
    border: 1px solid var(--bc-border);
    border-radius: 10px;
    align-self: flex-start;
}
.ag-sm-panel-tab {
    min-width: 90px;
    border: 0;
    border-radius: 7px;
    padding: 7px 14px;
    background: transparent;
    color: var(--bc-text-muted);
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.18s ease, color 0.18s ease;
}
.ag-sm-panel-tab:hover { color: var(--bc-text-sub); background: rgba(255,255,255,0.06); }
.ag-sm-panel-tab[aria-selected="true"] {
    background: rgba(255, 255, 255, 0.92);
    color: #0a0a0a;
}
.ag-sm-next-panel,
.ag-sm-lyrics-panel {
    min-height: 0;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow: hidden;
}
.ag-sm-lyrics-panel[hidden] { display: none !important; }

/* Section headers */
.ag-sm-sec-header { margin-top: 2px; }
.ag-sm-sec-title {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.6px;
    color: var(--bc-text);
}
.ag-sm-sec-sub {
    font-size: 12px;
    color: var(--bc-text-muted);
    margin-top: 2px;
}

/* Mood chips */
.ag-sm-chips-row {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
}
.ag-sm-chip {
    display: inline-flex;
    align-items: center;
    padding: 7px 16px;
    border-radius: 999px;
    background: rgba(118, 118, 128, 0.12);
    border: 1px solid var(--bc-border);
    color: var(--bc-text-sub);
    font-size: 12px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.18s ease;
}
.ag-sm-chip:hover { background: rgba(118,118,128,0.22); border-color: var(--bc-border-hover); }
.ag-sm-chip.active {
    background: rgba(255,255,255,0.90);
    color: #0a0a0a;
    border-color: rgba(255,255,255,0.90);
}

/* Queue list */
.ag-sm-queue-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    overflow-y: auto;
    min-height: 0;
    flex: 1;
    padding-right: 2px;
}
.ag-sm-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 12px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    cursor: pointer;
    transition: all 0.18s ease;
    min-height: 58px;
}
.ag-sm-card:hover {
    background: rgba(255,255,255,0.07);
    border-color: var(--bc-border);
    transform: translateX(2px);
}
.ag-sm-card.active-playing {
    background: linear-gradient(90deg, rgba(250,36,60,0.14), rgba(255,255,255,0.03));
    border-color: rgba(250, 36, 60, 0.42);
    box-shadow: 0 0 0 1px rgba(250,36,60,0.10);
}
.ag-sm-card-index {
    width: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    position: relative;
}
.ag-sm-card-num {
    font-size: 12px;
    font-weight: 600;
    color: var(--bc-text-muted);
}
.ag-sm-card-hover-play { display: none; position: absolute; color: var(--bc-text); }
.ag-sm-card:hover .ag-sm-card-num { display: none; }
.ag-sm-card:hover .ag-sm-card-hover-play { display: flex; }
.ag-sm-live-eq {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 14px;
}
.ag-sm-live-eq span {
    width: 2.5px;
    border-radius: 2px;
    background: var(--bc-accent);
    animation: agEqDance 0.9s ease-in-out infinite alternate;
}
.ag-sm-live-eq span:nth-child(1) { height: 6px;  animation-delay: 0s; }
.ag-sm-live-eq span:nth-child(2) { height: 12px; animation-delay: 0.12s; }
.ag-sm-live-eq span:nth-child(3) { height: 8px;  animation-delay: 0.24s; }
.ag-sm-live-eq span:nth-child(4) { height: 14px; animation-delay: 0.36s; }
.ag-sm-card-thumb {
    width: 44px; height: 44px;
    border-radius: 8px;
    overflow: hidden;
    flex-shrink: 0;
    background: var(--bc-surface);
}
.ag-sm-card-thumb img { width: 100%; height: 100%; object-fit: cover; }
.ag-sm-card-info { flex: 1; min-width: 0; }
.ag-sm-card-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--bc-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.ag-sm-card-artist {
    font-size: 11px;
    font-weight: 500;
    color: var(--bc-text-muted);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.ag-sm-card-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}
.ag-sm-card-dur {
    font-size: 11px;
    font-weight: 500;
    color: var(--bc-text-muted);
}
.ag-sm-card-dl-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 26px;
    padding: 0 8px;
    border-radius: 8px;
    font-size: 10px;
    font-weight: 600;
    font-family: inherit;
    color: var(--bc-text-sub);
    background: transparent;
    border: 1px solid transparent;
    transition: all 0.15s ease;
}
.ag-sm-card-dl-btn:hover {
    background: rgba(255,255,255,0.10);
    border-color: var(--bc-border);
    color: var(--bc-text);
}

/* Skeleton loading */
.ag-sm-skeleton-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 12px;
    background: rgba(255,255,255,0.03);
    min-height: 58px;
}
.ag-sm-skel-thumb {
    width: 44px; height: 44px;
    border-radius: 8px;
    background: rgba(255,255,255,0.08);
    animation: agSkelPulse 1.6s ease-in-out infinite;
}
.ag-sm-skel-lines { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.ag-sm-skel-line {
    height: 10px;
    border-radius: 999px;
    background: rgba(255,255,255,0.08);
    animation: agSkelPulse 1.6s ease-in-out infinite;
}
.ag-sm-skel-line:last-child { width: 60%; animation-delay: 0.3s; }
@keyframes agSkelPulse {
    0%, 100% { opacity: 0.6; }
    50%       { opacity: 1; }
}

/* Lyrics panel */
.ag-sm-lyrics-heading {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
}
.ag-sm-lyrics-status {
    font-size: 11px;
    font-weight: 500;
    color: rgba(255,255,255,0.35);
    text-align: right;
    flex-shrink: 0;
}
.ag-sm-lyrics-scroll {
    min-height: 0;
    flex: 1;
    overflow-y: auto;
    padding: 8px 2px 36px;
    scrollbar-width: thin;
}
.ag-sm-lyrics-line {
    margin: 0;
    padding: 7px 10px;
    color: rgba(255, 255, 255, 0.28);
    font-size: clamp(18px, 1.9vw, 26px);
    font-weight: 700;
    line-height: 1.25;
    letter-spacing: -0.5px;
    filter: blur(0.6px);
    transition: color 0.25s ease, filter 0.25s ease, transform 0.25s ease;
    cursor: default;
}
.ag-sm-lyrics-line.is-active {
    color: #FFFFFF;
    filter: none;
    transform: translateX(5px);
    text-shadow: 0 0 24px rgba(255, 255, 255, 0.40);
}
.ag-sm-lyrics-empty {
    margin: 0;
    padding: 20px 10px;
    color: var(--bc-text-muted);
    font-size: 14px;
    line-height: 1.6;
}

/* EQ Drawer */
.ag-sm-eq-drawer {
    display: none;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    background: var(--bc-glass);
    backdrop-filter: blur(16px);
    border: 1px solid var(--bc-border);
    border-radius: 14px;
    margin-bottom: 2px;
}
.ag-sm-eq-drawer.open { display: flex; }
.ag-sm-eq-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ag-sm-eq-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ag-sm-eq-label {
    font-size: 9px; font-weight: 700;
    letter-spacing: 0.8px;
    color: var(--bc-text-muted);
    text-transform: uppercase;
}
.ag-sm-eq-chip {
    padding: 5px 11px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    font-family: inherit;
    color: var(--bc-text-sub);
    background: rgba(255,255,255,0.06);
    border: 1px solid var(--bc-border);
    cursor: pointer;
    transition: all 0.15s ease;
}
.ag-sm-eq-chip:hover { background: rgba(255,255,255,0.11); }
.ag-sm-eq-chip.active {
    background: var(--bc-accent);
    border-color: var(--bc-accent);
    color: #fff;
}
.ag-sm-eq-sliders {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}
.ag-sm-band {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}
.ag-sm-band-name, .ag-sm-band-val {
    font-size: 9px;
    color: var(--bc-text-muted);
    font-weight: 600;
}
.ag-sm-band-slider {
    -webkit-appearance: none;
    width: 56px; height: 3px;
    border-radius: 999px;
    background: rgba(255,255,255,0.14);
    outline: none;
    cursor: pointer;
}
.ag-sm-band-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 11px; height: 11px;
    border-radius: 50%;
    background: var(--bc-accent);
    cursor: pointer;
}

/* Stats for Nerds overlay */
#agSmStatsOverlay {
    display: none;
    position: absolute;
    bottom: 24px;
    right: 24px;
    z-index: 60;
    min-width: 240px;
    padding: 14px 16px;
    background: rgba(0, 0, 0, 0.84);
    backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid var(--bc-border);
    border-radius: 14px;
    font-size: 11px;
    font-weight: 500;
    color: var(--bc-text-sub);
    pointer-events: none;
}
#agSmStatsOverlay.open { display: block; pointer-events: auto; }
#agSmStatsOverlay table { border-collapse: collapse; width: 100%; }
#agSmStatsOverlay td {
    padding: 3px 6px;
    vertical-align: top;
}
#agSmStatsOverlay td:first-child {
    color: var(--bc-text-muted);
    white-space: nowrap;
    padding-right: 12px;
}
#agSmStatsOverlay td:last-child {
    color: var(--bc-text);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}
#agSmStatsTitle {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--bc-accent);
    margin-bottom: 8px;
}
.ag-sm-stats-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px; height: 32px;
    border-radius: 50%;
    color: var(--bc-text-muted);
    background: transparent;
    border: 1px solid transparent;
    transition: all 0.18s ease;
}
.ag-sm-stats-btn:hover {
    background: rgba(255,255,255,0.08);
    border-color: var(--bc-border);
    color: var(--bc-text-sub);
}
.ag-sm-stats-btn.active {
    color: var(--bc-accent);
    background: var(--bc-accent-bg);
    border-color: rgba(250,36,60,0.28);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
    .ag-sm-vinyl-disc, .ag-sm-brand-icon span, .ag-sm-live-eq span,
    .ag-sm-dac-led, .ag-sm-art-wrap, .ag-sm-ambient-mesh::before,
    .ag-sm-ambient-mesh::after { animation: none !important; }
}

/* Responsive */
@media (max-width: 900px) {
    .ag-sm-header { padding: 0 14px; }
    .ag-sm-header-center { display: none; }
    .ag-sm-content-stage {
        grid-template-columns: minmax(290px, 40vw) minmax(0, 1fr);
    }
    .ag-sm-left-player { grid-column: 2; }
    .ag-sm-right-stage { grid-column: 1; padding-inline: 14px; }
    .ag-sm-card-dl-btn span { display: none; }
}
@media (max-width: 680px) {
    .ag-sm-header-right .ag-sm-hdr-btn span { display: none; }
    .ag-sm-content-stage {
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
    .ag-sm-left-player {
        order: 1;
        min-height: min(600px, 70vh);
        flex: none;
        border-left: 0;
        border-bottom: 1px solid var(--bc-border);
        padding-block: 20px;
    }
    .ag-sm-art-container {
        width: min(62vw, 290px);
        height: min(62vw, 290px);
    }
    .ag-sm-right-stage {
        order: 2;
        flex: none;
        min-height: 400px;
    }
}
"""

CINEMA_JS = r"""
(function() {
    try {
        // Untouched native network layer: preserving authentic YouTube SABR streaming and InnerTube attestation
        // to prevent player errors, playback freezes, and automatic song skipping.

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

        // Navigation History & Smart Back Navigation Engine
        function trackBrowseUrl() {
            try {
                const href = window.location.href;
                const path = window.location.pathname;
                // If on search results, browse feed, or home page (not playing a specific video)
                if (!window.location.search.includes('v=') && !path.includes('/watch')) {
                    safeSetStorage('ag_last_browse_url', href);
                }
            } catch(e) {}
        }
        trackBrowseUrl();

        function handleNavigationBack() {
            // 1. If currently in Music Studio, exit cleanly to normal YouTube or Video view
            if (typeof isStudioActive !== 'undefined' && isStudioActive) {
                if (typeof window.setStudioMode === 'function') {
                    window.setStudioMode(false);
                    return;
                }
            }
            // 2. If in Cinema Mode, disable cinema mode so normal YouTube page is shown
            if (document.body && document.body.classList.contains('ag-cinema-active')) {
                document.body.classList.remove('ag-cinema-active');
                if (typeof isCinema !== 'undefined') isCinema = false;
            }

            const initialHref = window.location.href;
            try {
                window.history.back();
            } catch(e) {}

            // Robust safety fallback: if URL has not changed after 350ms (history depleted or opened directly)
            setTimeout(() => {
                if (window.location.href === initialHref) {
                    const fallbackUrl = safeGetStorage('ag_last_browse_url') || 'https://www.youtube.com';
                    window.location.href = fallbackUrl;
                }
            }, 350);
        }

        // Top-Left Circular Back Button pinned beside YouTube Masthead / Player
        function injectPageBackButton() {
            let backBtn = document.getElementById('antigravity-page-back-btn');
            if (!backBtn) {
                backBtn = document.createElement('button');
                backBtn.id = 'antigravity-page-back-btn';
                backBtn.title = 'Back to search / previous page (Alt + Left)';
                backBtn.setAttribute('aria-label', 'Go back');

                const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                svg.setAttribute('viewBox', '0 0 24 24');
                svg.setAttribute('fill', 'none');
                svg.setAttribute('stroke', 'currentColor');
                svg.setAttribute('stroke-width', '2.5');
                svg.setAttribute('stroke-linecap', 'round');
                svg.setAttribute('stroke-linejoin', 'round');
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', 'M19 12H5M12 19l-7-7 7-7');
                svg.appendChild(path);
                backBtn.appendChild(svg);

                const triggerBack = (e) => {
                    if (e) {
                        e.preventDefault();
                        e.stopPropagation();
                        if (e.stopImmediatePropagation) e.stopImmediatePropagation();
                    }
                    handleNavigationBack();
                };
                backBtn.onclick = triggerBack;
                backBtn.addEventListener('click', triggerBack, true);
                backBtn.addEventListener('pointerdown', (e) => { if (e) e.stopPropagation(); }, true);

                const root = document.body || document.documentElement;
                if (root) root.appendChild(backBtn);
            }
            updatePageBackButtonVisibility();
            return backBtn;
        }

        function updatePageBackButtonVisibility() {
            const btn = document.getElementById('antigravity-page-back-btn');
            if (!btn) return;
            const isStudio = typeof isStudioActive !== 'undefined' && isStudioActive;
            if (isStudio) {
                btn.style.display = 'none';
                return;
            }
            btn.style.display = 'inline-flex';
        }

        // 5. Inject Top Controls Container
        function injectTopControls() {
            let controls = document.getElementById('antigravity-top-controls');
            if (controls) {
                if (!document.getElementById('agDockActions')) {
                    controls.remove();
                } else {
                    if (document.body && controls.parentElement !== document.body) {
                        document.body.appendChild(controls);
                    }
                    return controls;
                }
            }

            const targetParent = document.body || document.documentElement;
            if (!targetParent) return null;

            controls = document.createElement('div');
            controls.id = 'antigravity-top-controls';
            
            // 0. Back Navigation Button
            const backBtn = document.createElement('button');
            backBtn.className = 'ag-control-btn ag-back-btn';
            backBtn.id = 'agBackBtn';
            backBtn.textContent = '⬅ Back';
            backBtn.title = 'Go back to previous page or search results (Alt + Left)';
            backBtn.onclick = (e) => {
                if (e) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                handleNavigationBack();
            };

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

            // Brand Trigger Button (⚡ StreamFlow) - Opens on hover, click toggles collapse
            const minBtn = document.createElement('button');
            minBtn.className = 'ag-control-btn ag-toggle-btn';
            minBtn.id = 'agMinBtn';
            const boltSpan = document.createElement('span');
            boltSpan.className = 'ag-bolt';
            boltSpan.textContent = '⚡';
            const textSpan = document.createElement('span');
            textSpan.className = 'ag-brand-text';
            textSpan.textContent = 'StreamFlow';
            minBtn.appendChild(boltSpan);
            minBtn.appendChild(textSpan);
            minBtn.title = 'Click to pin/unpin dock. Hover to open.';
            minBtn.onclick = (e) => {
                e.stopPropagation();
                controls.classList.toggle('ag-dock-expanded');
            };

            // Actions wrapper for smooth sliding reveal on hover
            const actionsWrap = document.createElement('div');
            actionsWrap.className = 'ag-dock-actions';
            actionsWrap.id = 'agDockActions';

            actionsWrap.appendChild(backBtn);
            actionsWrap.appendChild(fsBtn);
            actionsWrap.appendChild(studioBtn);
            actionsWrap.appendChild(musicBtn);
            actionsWrap.appendChild(modeBtn);
            actionsWrap.appendChild(dlBtn);

            controls.appendChild(minBtn);
            controls.appendChild(actionsWrap);
            targetParent.appendChild(controls);
            return controls;
        }

        let controls = injectTopControls();
        injectPageBackButton();

        function ensureTopControls() {
            let controls = document.getElementById('antigravity-top-controls');
            if (!controls || !document.getElementById('agDockActions')) {
                controls = injectTopControls();
                if (typeof bindControlEvents === 'function') bindControlEvents();
                if (typeof updatePageMode === 'function') updatePageMode();
            } else if (document.body && controls.parentElement !== document.body) {
                document.body.appendChild(controls);
            }
            injectPageBackButton();
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

        function updatePageMode() {
            if (!document.body) return;
            const isMusic = window.location.hostname.includes('music.youtube.com');
            const hasVideo = window.location.search.includes('v=');

            if (isMusic) {
                document.body.classList.add('ag-music-site');
                document.body.classList.remove('ag-cinema-active');
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
                document.body.classList.remove('ag-music-site');
                if (!hasVideo) {
                    // On YouTube Home or Search: NEVER enable cinema mode, keep YouTube header & search bar 100% visible
                    isCinema = false;
                    document.body.classList.remove('ag-cinema-active');
                    if (modeBtn) modeBtn.style.display = 'none';
                } else {
                    // On video watch page: respect current cinema mode state
                    document.body.classList.toggle('ag-cinema-active', isCinema);
                    if (modeBtn) {
                        modeBtn.style.display = '';
                        modeBtn.textContent = isCinema ? '🌐 YouTube View' : '🎬 Cinema View';
                        modeBtn.style.background = isCinema ? 'rgba(15, 23, 42, 0.92)' : 'rgba(37, 99, 235, 0.92)';
                    }
                }
            }
            if (typeof trackBrowseUrl === 'function') trackBrowseUrl();
            if (typeof updatePageBackButtonVisibility === 'function') updatePageBackButtonVisibility();
        }
        updatePageMode();

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
                updatePageMode();
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

        // Controls Dock Hover & Inactivity Controller
        let leaveDebounceTimer;

        function bindControlEvents() {
            const ctrl = document.getElementById('antigravity-top-controls');
            if (!ctrl || ctrl._eventsBound) return;
            ctrl._eventsBound = true;

            ctrl.addEventListener('mouseenter', () => {
                isHovered = true;
                ctrl.classList.add('ag-dock-hovered');
                ctrl.classList.remove('hidden');
                clearTimeout(hideTimer);
                clearTimeout(leaveDebounceTimer);
            });

            ctrl.addEventListener('mousemove', () => {
                if (!ctrl.classList.contains('ag-dock-hovered')) {
                    ctrl.classList.add('ag-dock-hovered');
                }
            });

            ctrl.addEventListener('mouseleave', () => {
                isHovered = false;
                clearTimeout(leaveDebounceTimer);
                leaveDebounceTimer = setTimeout(() => {
                    ctrl.classList.remove('ag-dock-hovered');
                }, 200);
                resetTimer();
            });
        }
        bindControlEvents();

        function resetTimer() {
            const ctrl = document.getElementById('antigravity-top-controls');
            const pageBack = document.getElementById('antigravity-page-back-btn');
            if (ctrl) ctrl.classList.remove('hidden');
            if (pageBack && document.body && document.body.classList.contains('ag-cinema-active')) {
                pageBack.classList.remove('hidden');
            }
            clearTimeout(hideTimer);
            if (!isHovered && document.body && document.body.classList.contains('ag-cinema-active')) {
                hideTimer = setTimeout(() => {
                    const c = document.getElementById('antigravity-top-controls');
                    if (c) c.classList.add('hidden');
                    const pb = document.getElementById('antigravity-page-back-btn');
                    if (pb) pb.classList.add('hidden');
                }, 3500);
            }
        }

        window.addEventListener('mousemove', resetTimer);
        window.addEventListener('mousedown', resetTimer);
        resetTimer();

        // Clicking outside collapses hover expansion
        document.addEventListener('click', (e) => {
            const ctrl = document.getElementById('antigravity-top-controls');
            if (ctrl && !ctrl.contains(e.target)) {
                ctrl.classList.remove('ag-dock-hovered');
            }
        });


        // Lightweight Draggable Support for Floating Controls Dock
        let isDragging = false;
        let startX = 0, startY = 0;
        let initialLeft = 0, initialTop = 0;

        controls.addEventListener('pointerdown', (e) => {
            if (e.target.closest('button')) return;
            isDragging = true;
            const rect = controls.getBoundingClientRect();
            startX = e.clientX;
            startY = e.clientY;
            initialLeft = rect.left;
            initialTop = rect.top;
            try { controls.setPointerCapture(e.pointerId); } catch(err) {}
            e.preventDefault();
        });

        controls.addEventListener('pointermove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            const newLeft = Math.max(10, Math.min(window.innerWidth - controls.offsetWidth - 10, initialLeft + dx));
            const newTop = Math.max(10, Math.min(window.innerHeight - controls.offsetHeight - 10, initialTop + dy));
            controls.style.left = newLeft + 'px';
            controls.style.top = newTop + 'px';
            controls.style.bottom = 'auto';
            controls.style.right = 'auto';
            controls.style.transform = 'none';
        });

        const stopDrag = (e) => {
            if (isDragging) {
                isDragging = false;
                try { controls.releasePointerCapture(e.pointerId); } catch(err) {}
            }
        };
        controls.addEventListener('pointerup', stopDrag);
        controls.addEventListener('pointercancel', stopDrag);

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
                <!-- LIVING AURORA MESH BACKDROP -->
                <div id="agSmAmbientMesh" class="ag-sm-ambient-mesh"></div>

                <!-- TOP HEADER -->
                <header class="ag-sm-header">
                    <div class="ag-sm-header-left">
                        <button class="ag-sm-hdr-icon-btn ag-sm-back-arrow" id="agSmBackArrow" title="Back to previous page or YouTube view (Alt + Left)">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                        </button>
                        <div class="ag-sm-brand" id="agSmBrandLogo">
                            <div class="ag-sm-brand-icon">
                                <span></span><span></span><span></span><span></span><span></span>
                            </div>
                            <span class="ag-sm-brand-text">StreamFlow Studio</span>
                            <span class="ag-sm-brand-badge">HI-RES AUDIO</span>
                        </div>
                    </div>

                    <div class="ag-sm-header-center">
                        <div class="ag-sm-search-capsule">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                            <input type="text" id="agSmSearchInput" placeholder="Search songs, artists, albums, or paste YouTube link..." autocomplete="off">
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

                <!-- TWO-COLUMN CONTENT STAGE -->
                <div class="ag-sm-content-stage">
                    <!-- LEFT: MASTER OBSIDIAN HI-FI CONSOLE DECK -->
                    <div class="ag-sm-left-player">
                        <!-- Cover Artwork & Vinyl Showcase -->
                        <div class="ag-sm-art-wrap" id="agSmHeroStage">
                            <div class="ag-sm-art-container">
                                <div class="ag-sm-vinyl-disc" id="agSmVinylDisc">
                                    <div class="ag-sm-vinyl-grooves"></div>
                                    <div class="ag-sm-vinyl-label">
                                        <div class="ag-sm-vinyl-hole"></div>
                                    </div>
                                </div>
                                <div class="ag-sm-art-sleeve">
                                    <img class="ag-sm-art-img" id="agSmHeroArtImg" src="${STUDIO_ASSETS.hero_art}" alt="Cover">
                                    <div class="ag-sm-art-gloss"></div>
                                </div>
                            </div>
                        </div>

                        <!-- Title, Artist, Heart -->
                        <div class="ag-sm-info-row">
                            <div class="ag-sm-info-text">
                                <div class="ag-sm-hero-title" id="agSmHeroTitle" style="color:rgba(255,255,255,0.45);font-size:16px;font-weight:600">Select a song to start listening</div>
                                <div class="ag-sm-hero-artist-wrap">
                                    <span class="ag-sm-hero-artist" id="agSmHeroArtist" style="color:rgba(255,255,255,0.3)">StreamFlow Studio Hi-Fi</span>
                                </div>
                            </div>
                            <button class="ag-sm-heart-btn" id="agSmHeroHeartBtn" title="Like Track">
                                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                            </button>
                        </div>

                        <!-- Hi-Fi Lossless DAC Badge -->
                        <div class="ag-sm-hifi-row">
                            <div class="ag-sm-badge-capsule" id="agSmHiFiPill">
                                <span class="ag-sm-dac-led"></span>
                                <span class="ag-sm-dac-text">MASTER HI-RES &bull; 24-BIT / 96.0 kHz &bull; LOSSLESS FLAC</span>
                            </div>
                        </div>

                        <!-- Continuous Seekbar & Timestamps -->
                        <div class="ag-sm-seek-section">
                            <div class="ag-sm-seek-wrap">
                                <input type="range" class="ag-sm-slider" id="agSmSlider" min="0" max="100" value="0">
                            </div>
                            <div class="ag-sm-timestamps">
                                <span id="agSmCurrentTime">0:00</span>
                                <span id="agSmDuration">0:00</span>
                            </div>
                        </div>

                        <!-- Floating Transport Capsule -->
                        <div class="ag-sm-transport-row">
                            <button class="ag-sm-flank-btn" id="agSmShuffleBtn" title="Shuffle">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>
                            </button>

                            <div class="ag-sm-transport-capsule">
                                <button class="ag-sm-trans-btn" id="agSmPrevBtn" title="Previous">
                                    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
                                </button>
                                <button class="ag-sm-play-circle" id="agSmPlayPauseBtn" title="Play / Pause">
                                    <svg width="22" height="22" viewBox="0 0 24 24" fill="#080a12"><polygon points="6 4 20 12 6 20 6 4"/></svg>
                                </button>
                                <button class="ag-sm-trans-btn" id="agSmNextBtn" title="Next">
                                    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
                                </button>
                            </div>

                            <button class="ag-sm-flank-btn" id="agSmRepeatBtn" title="Repeat">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                            </button>
                        </div>

                        <!-- Deck Bottom Utility Row (Volume + Lossless MP3 Download + Lyrics) -->
                        <div class="ag-sm-deck-utilities">
                            <div class="ag-sm-vol-cluster">
                                <button class="ag-sm-vol-btn" id="agSmMuteBtn" title="Mute / Unmute">
                                    <span id="agSmVolIconWrap">
                                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
                                    </span>
                                </button>
                                <input type="range" class="ag-sm-vol-slider" id="agSmVolSlider" min="0" max="100" value="100" title="Volume">
                            </div>

                            <div class="ag-sm-deck-actions">
                                <button class="ag-sm-hero-dl-btn" id="agSmHeroDlBtn" title="Download High-Quality MP3">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                    <span>Download MP3</span>
                                </button>
                                <button class="ag-sm-sheet-btn" id="agSmLyricsBtn" title="Show lyrics" aria-label="Show lyrics" aria-pressed="false">
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                                </button>
                                <button class="ag-sm-sheet-btn ag-sm-stats-btn" id="agSmStatsBtn" title="Stats for Nerds" aria-label="Stats for Nerds" aria-pressed="false">
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                                </button>
                                <button class="ag-sm-sheet-btn ag-sm-automix-btn" id="agSmAutoMixBtn" title="AutoMix: smooth track transitions" aria-label="AutoMix" aria-pressed="false">
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3h5v5"/><path d="M4 20L21 3"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/></svg>
                                </button>
                                <button class="ag-sm-sheet-btn ag-sm-crossfade-btn" id="agSmCrossfadeBtn" title="Crossfade: blend between tracks" aria-label="Crossfade" aria-pressed="false">
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h4l3-9 4 18 3-9h4"/></svg>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- RIGHT: SMART RECOMMENDATIONS & UP NEXT QUEUE -->
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

                        <div class="ag-sm-panel-tabs" role="tablist" aria-label="Player side panel">
                            <button class="ag-sm-panel-tab" id="agSmUpNextTab" role="tab" aria-selected="true" aria-controls="agSmUpNextPanel">Up Next</button>
                            <button class="ag-sm-panel-tab" id="agSmLyricsTab" role="tab" aria-selected="false" aria-controls="agSmLyricsPanel">Lyrics</button>
                        </div>

                        <div class="ag-sm-next-panel" id="agSmUpNextPanel" role="tabpanel" aria-labelledby="agSmUpNextTab">
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
                                <div class="ag-sm-sec-sub" id="agSmRecSubtitle">Tailored to YouTube Music</div>
                            </div>

                            <!-- Up Next Cards List -->
                            <div class="ag-sm-queue-list" id="agSmRelatedList">
                            <div class="ag-sm-card active-playing">
                                <div class="ag-sm-card-index">
                                    <div class="ag-sm-live-eq"><span></span><span></span><span></span><span></span></div>
                                    <div class="ag-sm-card-hover-play"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"/></svg></div>
                                </div>
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">Peter x Gwen Edit</div>
                                    <div class="ag-sm-card-artist">Saarang & Sarvaang</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">2:49</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>MP3</span></button>
                                </div>
                            </div>
                            <div class="ag-sm-card" data-title="Recollect - Konomi Suzuki">
                                <div class="ag-sm-card-index">
                                    <span class="ag-sm-card-num">02</span>
                                    <div class="ag-sm-card-hover-play"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"/></svg></div>
                                </div>
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">Recollect</div>
                                    <div class="ag-sm-card-artist">Konomi Suzuki, Ashnikko</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">3:18</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>MP3</span></button>
                                </div>
                            </div>
                            <div class="ag-sm-card" data-title="FLASH BACK - natori">
                                <div class="ag-sm-card-index">
                                    <span class="ag-sm-card-num">03</span>
                                    <div class="ag-sm-card-hover-play"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"/></svg></div>
                                </div>
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">FLASH BACK</div>
                                    <div class="ag-sm-card-artist">natori</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">3:05</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>MP3</span></button>
                                </div>
                            </div>
                            <div class="ag-sm-card" data-title="Deep down - Aimer">
                                <div class="ag-sm-card-index">
                                    <span class="ag-sm-card-num">04</span>
                                    <div class="ag-sm-card-hover-play"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"/></svg></div>
                                </div>
                                <div class="ag-sm-card-thumb">
                                    <img src="${STUDIO_ASSETS.hero_art}" alt="Art">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">Deep down</div>
                                    <div class="ag-sm-card-artist">Aimer</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">3:47</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>MP3</span></button>
                                </div>
                            </div>
                            </div>
                        </div>

                        <div class="ag-sm-lyrics-panel" id="agSmLyricsPanel" role="tabpanel" aria-labelledby="agSmLyricsTab" hidden>
                            <div class="ag-sm-lyrics-heading">
                                <div>
                                    <div class="ag-sm-sec-title">Lyrics</div>
                                    <div class="ag-sm-sec-sub">Synced to the current track when available</div>
                                </div>
                                <div class="ag-sm-lyrics-status" id="agSmLyricsStatus">Select Lyrics to load</div>
                            </div>
                            <div class="ag-sm-lyrics-scroll" id="agSmLyricsContent" aria-live="polite">
                                <p class="ag-sm-lyrics-empty">Lyrics are off. Select this panel to search for lyrics.</p>
                            </div>
                        </div>
                    </div>
                </div>
                <!-- Stats for Nerds Overlay -->
                <div id="agSmStatsOverlay" class="ag-sm-stats-overlay">
                    <div class="ag-sm-stats-title" id="agSmStatsTitle">Stats for Nerds</div>
                    <table class="ag-sm-stats-table" id="agSmStatsTable">
                        <tr><td>Format</td><td id="agSmStatFmt">—</td></tr>
                        <tr><td>Codec</td><td id="agSmStatCodec">AAC</td></tr>
                        <tr><td>Resolution</td><td id="agSmStatRes">—</td></tr>
                        <tr><td>Sample Rate</td><td id="agSmStatSR">44.1 kHz</td></tr>
                        <tr><td>Buffered</td><td id="agSmStatBuf">—</td></tr>
                        <tr><td>Duration</td><td id="agSmStatDur">—</td></tr>
                        <tr><td>Bitrate</td><td id="agSmStatBR">~320 kbps</td></tr>
                    </table>
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
        var studioQueue = [];
        var studioQueueIndex = -1;
        var studioShuffle = false;
        var studioRepeat = 'off';
        var visRunning = false;
        var audioCtx = null;
        var eqFilters = [];
        var sleepTimerId = null;
        var lyricsPanelMode = 'up-next';
        var lyricsTrackKey = '';
        var lyricsLines = [];
        var lyricsActiveIndex = -2;
        var lyricsRequestPending = false;
        var lyricsRequestFinished = false;

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

        function escapeLyricsText(value) {
            return String(value || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function parseLyrics(raw, synced) {
            const text = String(raw || '').replace(/\r/g, '').trim();
            if (!text) return [];
            if (!synced) {
                return text.split('\n').map((line) => ({ time: -1, text: line.trim() })).filter((line) => line.text);
            }

            const parsed = [];
            text.split('\n').forEach((line) => {
                const timestamps = [];
                const matcher = /\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]/g;
                let match;
                while ((match = matcher.exec(line)) !== null) {
                    const fraction = String(match[3] || '0');
                    const milliseconds = fraction.length === 1 ? Number(fraction) * 100 : fraction.length === 2 ? Number(fraction) * 10 : Number(fraction);
                    timestamps.push(Number(match[1]) * 60 + Number(match[2]) + milliseconds / 1000);
                }
                const lyricText = line.replace(/\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]/g, '').trim();
                if (lyricText) timestamps.forEach((time) => parsed.push({ time, text: lyricText }));
            });
            return parsed.sort((a, b) => a.time - b.time);
        }

        function renderLyricsLines(currentTime) {
            const content = document.getElementById('agSmLyricsContent');
            if (!content || !lyricsLines.length) return;

            let activeIndex = -1;
            if (lyricsLines.some((line) => line.time >= 0)) {
                lyricsLines.forEach((line, index) => {
                    if (line.time >= 0 && line.time <= currentTime) activeIndex = index;
                });
            }
            if (activeIndex === lyricsActiveIndex && content.dataset.rendered === '1') return;
            lyricsActiveIndex = activeIndex;
            content.dataset.rendered = '1';
            setSafeHTML(content, lyricsLines.map((line, index) =>
                `<p class="ag-sm-lyrics-line${index === activeIndex ? ' is-active' : ''}">${escapeLyricsText(line.text)}</p>`
            ).join(''));
            const activeLine = content.querySelector('.ag-sm-lyrics-line.is-active');
            if (activeLine && activeIndex >= 0) {
                activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        function setLyricsMessage(message) {
            const content = document.getElementById('agSmLyricsContent');
            if (!content) return;
            content.dataset.rendered = '0';
            setSafeHTML(content, `<p class="ag-sm-lyrics-empty">${escapeLyricsText(message)}</p>`);
        }

        function receiveLyricsResult(result, trackKey) {
            if (trackKey !== lyricsTrackKey) return;
            lyricsRequestPending = false;
            lyricsRequestFinished = true;
            let data = result;
            if (typeof data === 'string') {
                try { data = JSON.parse(data); } catch(e) { data = null; }
            }
            const status = document.getElementById('agSmLyricsStatus');
            if (!data || data.status !== 'success') {
                lyricsLines = [];
                lyricsActiveIndex = -2;
                if (status) status.textContent = 'Not available';
                setLyricsMessage(data && data.message ? data.message : 'Lyrics are unavailable for this track.');
                return;
            }

            const synced = String(data.synced_lyrics || '').trim();
            const plain = String(data.plain_lyrics || '').trim();
            lyricsLines = parseLyrics(synced || plain, Boolean(synced));
            lyricsActiveIndex = -2;
            const provider = String(data.provider || data.source || 'Lyrics');
            if (status) status.textContent = synced ? `${provider} · synced` : `${provider} · plain text`;
            if (!lyricsLines.length) {
                setLyricsMessage('No lyrics found for this track.');
                return;
            }
            setLyricsMessage('');
            renderLyricsLines(document.querySelector('video')?.currentTime || 0);
        }

        function loadLyricsForCurrentTrack(title, artist, duration) {
            if (lyricsPanelMode !== 'lyrics' || !title || title === 'Unknown Title') return;
            const trackKey = `${title}|${artist}`;
            if (trackKey === lyricsTrackKey && (lyricsRequestPending || lyricsRequestFinished)) return;
            lyricsTrackKey = trackKey;
            lyricsLines = [];
            lyricsActiveIndex = -2;
            lyricsRequestPending = true;
            lyricsRequestFinished = false;
            const status = document.getElementById('agSmLyricsStatus');
            if (status) status.textContent = 'Searching…';
            setLyricsMessage('Searching lyrics for this track…');

            const bridge = window.pywebview && window.pywebview.api;
            if (bridge && typeof bridge.get_lyrics === 'function') {
                Promise.resolve(bridge.get_lyrics(title, artist, Number.isFinite(duration) ? duration : null))
                    .then((result) => receiveLyricsResult(result, trackKey))
                    .catch(() => receiveLyricsResult({ status: 'not_found', message: 'Lyrics are unavailable for this track.' }, trackKey));
                return;
            }

            const params = new URLSearchParams({ track_name: title });
            if (artist && artist !== 'Original Artist') params.set('artist_name', artist);
            fetch(`https://lrclib.net/api/get?${params.toString()}`)
                .then((response) => response.ok ? response.json() : Promise.reject(new Error('lyrics unavailable')))
                .then((result) => receiveLyricsResult({
                    status: 'success',
                    source: 'LRCLIB',
                    plain_lyrics: result.plainLyrics,
                    synced_lyrics: result.syncedLyrics,
                }, trackKey))
                .catch(() => receiveLyricsResult({ status: 'not_found', message: 'Lyrics are unavailable for this track.' }, trackKey));
        }

        function showStudioPanel(panel) {
            lyricsPanelMode = panel === 'lyrics' ? 'lyrics' : 'up-next';
            const nextPanel = document.getElementById('agSmUpNextPanel');
            const lyricsPanel = document.getElementById('agSmLyricsPanel');
            const nextTab = document.getElementById('agSmUpNextTab');
            const lyricsTab = document.getElementById('agSmLyricsTab');
            const lyricsButton = document.getElementById('agSmLyricsBtn');
            if (nextPanel) nextPanel.hidden = lyricsPanelMode !== 'up-next';
            if (lyricsPanel) lyricsPanel.hidden = lyricsPanelMode !== 'lyrics';
            if (nextTab) nextTab.setAttribute('aria-selected', String(lyricsPanelMode === 'up-next'));
            if (lyricsTab) lyricsTab.setAttribute('aria-selected', String(lyricsPanelMode === 'lyrics'));
            if (lyricsButton) {
                lyricsButton.classList.toggle('active', lyricsPanelMode === 'lyrics');
                lyricsButton.setAttribute('aria-pressed', String(lyricsPanelMode === 'lyrics'));
                lyricsButton.title = lyricsPanelMode === 'lyrics' ? 'Hide lyrics' : 'Show lyrics';
            }
            if (lyricsPanelMode === 'lyrics') {
                const video = document.querySelector('video');
                const player = document.getElementById('movie_player');
                const data = player && typeof player.getVideoData === 'function' ? player.getVideoData() : {};
                const title = cleanTrackTitle(data.title || document.title.replace(/ - YouTube(?: Music)?$/, ''));
                const artist = cleanArtistName(data.author || '');
                loadLyricsForCurrentTrack(title, artist, video ? video.duration : null);
                renderLyricsLines(video?.currentTime || 0);
            }
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
                if (typeof updatePageBackButtonVisibility === 'function') updatePageBackButtonVisibility();
                try { syncStudioPlayer(); } catch(err) {}
                try { fetchContextualRecommendations(); } catch(err) {}
                try { startVisualizer(); } catch(err) {}
            } else {
                if (studioUI) {
                    studioUI.classList.remove('active');
                    studioUI.style.display = 'none';
                }
                if (topControls) topControls.style.display = '';
                if (typeof updatePageBackButtonVisibility === 'function') updatePageBackButtonVisibility();
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
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) e.stopImmediatePropagation();
                handleNavigationBack();
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
                grad.addColorStop(0.30, '#FA243C');
                grad.addColorStop(0.55, '#818cf8');
                grad.addColorStop(0.80, '#c084fc');
                grad.addColorStop(1.0, '#FA243C');

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

        function syncStudioQueueButtons() {
            const shuffleButtons = [document.getElementById('agSmHeroShuffleBtn'), document.getElementById('agSmShuffleBtn')];
            shuffleButtons.forEach((button) => {
                if (!button) return;
                button.classList.toggle('active', studioShuffle);
                button.setAttribute('aria-pressed', String(studioShuffle));
                button.title = studioShuffle ? 'Shuffle is on' : 'Shuffle';
            });

            const repeatButtons = [document.getElementById('agSmHeroRepeatBtn'), document.getElementById('agSmRepeatBtn')];
            repeatButtons.forEach((button) => {
                if (!button) return;
                button.classList.toggle('active', studioRepeat !== 'off');
                button.setAttribute('aria-pressed', String(studioRepeat !== 'off'));
                button.title = studioRepeat === 'one' ? 'Repeat one' : studioRepeat === 'all' ? 'Repeat all' : 'Repeat';
            });
        }

        function advanceStudioQueue(direction) {
            if (studioQueue.length === 0) {
                const nextButton = document.querySelector('.ytp-next-button');
                if (nextButton && direction > 0) nextButton.click();
                return;
            }

            let nextIndex = studioQueueIndex;
            if (studioShuffle) {
                const choices = studioQueue.map((_, index) => index).filter((index) => index !== studioQueueIndex);
                nextIndex = choices.length ? choices[Math.floor(Math.random() * choices.length)] : studioQueueIndex;
            } else {
                nextIndex += direction;
                if (nextIndex >= studioQueue.length) {
                    if (studioRepeat === 'all') nextIndex = 0;
                    else return;
                }
                if (nextIndex < 0) nextIndex = studioQueue.length - 1;
            }

            const track = studioQueue[nextIndex];
            if (track && track.id) {
                studioQueueIndex = nextIndex;
                playSongInstantly(track.id, track.url);
            }
        }

        function syncStudioPlayer() {
            try {
                if (!isStudioActive) return;
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
                    if (!video._studioQueueBound) {
                        video._studioQueueBound = true;
                        video.addEventListener('ended', () => {
                            if (studioRepeat === 'one') {
                                video.currentTime = 0;
                                video.play().catch(() => {});
                                return;
                            }
                            advanceStudioQueue(1);
                        });
                    }
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

                if (lyricsPanelMode === 'lyrics') {
                    loadLyricsForCurrentTrack(displayTitle, displayAuthor, video ? video.duration : null);
                    renderLyricsLines(video?.currentTime || 0);
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
                    studioQueue = tracks.slice();
                    studioQueueIndex = studioQueue.findIndex((track) => track.id === lastVId);
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
                                <div class="ag-sm-card-index">
                                    ${idxDisplay}
                                    <div class="ag-sm-card-hover-play"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"/></svg></div>
                                </div>
                                <div class="ag-sm-card-thumb">
                                    <img src="${t.thumb}" alt="Art" loading="lazy">
                                </div>
                                <div class="ag-sm-card-info">
                                    <div class="ag-sm-card-title">${cleanT}</div>
                                    <div class="ag-sm-card-artist">${cleanA}</div>
                                </div>
                                <div class="ag-sm-card-meta">
                                    <span class="ag-sm-card-dur">${durText}</span>
                                    <button class="ag-sm-card-dl-btn" data-action="dl" title="Download MP3"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>MP3</span></button>
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
                                                    setSafeHTML(btn, `${dlSvg}<span>MP3</span>`);
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
                const queuedIndex = studioQueue.findIndex((track) => track.id === songId);
                if (queuedIndex >= 0) studioQueueIndex = queuedIndex;
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
                    h.style.color = isLiked ? '#FA243C' : '#94a3b8';
                    if (isLiked) h.style.background = 'rgba(250, 36, 60, 0.25)';
                    else h.style.background = 'transparent';
                }
            });
        }
        const heroHeartBtn = document.getElementById('agSmHeroHeartBtn');
        if (heroHeartBtn) heroHeartBtn.onclick = () => toggleHeart(heroHeartBtn);
        const dockHeartBtn = document.getElementById('agSmDockHeartBtn');
        if (dockHeartBtn) dockHeartBtn.onclick = () => toggleHeart(dockHeartBtn);

        // ---- Stats for Nerds ----
        var agStatsOpen = false;
        function agUpdateStats() {
            if (!agStatsOpen) return;
            const video = document.querySelector('video');
            const overlay = document.getElementById('agSmStatsOverlay');
            if (!overlay || !video) return;
            const res = document.getElementById('agSmStatRes');
            const buf = document.getElementById('agSmStatBuf');
            const dur = document.getElementById('agSmStatDur');
            const fmt = document.getElementById('agSmStatFmt');
            if (res) res.textContent = video.videoWidth && video.videoHeight ? video.videoWidth + 'x' + video.videoHeight : 'Audio';
            if (dur) dur.textContent = video.duration && isFinite(video.duration) ? formatTime(video.duration) : '—';
            if (fmt) {
                try { fmt.textContent = video.currentSrc ? (video.currentSrc.includes('.webm') ? 'WebM' : video.currentSrc.includes('.mp4') ? 'MP4' : 'Stream') : '—'; } catch(e){}
            }
            try {
                if (video.buffered && video.buffered.length > 0 && buf) {
                    buf.textContent = formatTime(video.buffered.end(video.buffered.length - 1));
                }
            } catch(e) {}
        }
        setInterval(agUpdateStats, 1000);
        const agStatsBtn = document.getElementById('agSmStatsBtn');
        if (agStatsBtn) {
            agStatsBtn.addEventListener('click', function() {
                agStatsOpen = !agStatsOpen;
                agStatsBtn.classList.toggle('active', agStatsOpen);
                agStatsBtn.setAttribute('aria-pressed', String(agStatsOpen));
                const overlay = document.getElementById('agSmStatsOverlay');
                if (overlay) overlay.classList.toggle('open', agStatsOpen);
            });
        }

        // ---- AutoMix ----
        var agAutoMixEnabled = false;
        var agAutoMixFading = false;
        const agAutoMixBtn = document.getElementById('agSmAutoMixBtn');
        if (agAutoMixBtn) {
            agAutoMixBtn.addEventListener('click', function() {
                agAutoMixEnabled = !agAutoMixEnabled;
                agAutoMixBtn.classList.toggle('active', agAutoMixEnabled);
                agAutoMixBtn.setAttribute('aria-pressed', String(agAutoMixEnabled));
            });
        }

        // ---- Crossfade ----
        var agCrossfadeEnabled = false;
        const agCrossfadeBtn = document.getElementById('agSmCrossfadeBtn');
        if (agCrossfadeBtn) {
            agCrossfadeBtn.addEventListener('click', function() {
                agCrossfadeEnabled = !agCrossfadeEnabled;
                agCrossfadeBtn.classList.toggle('active', agCrossfadeEnabled);
                agCrossfadeBtn.setAttribute('aria-pressed', String(agCrossfadeEnabled));
            });
        }

        // AutoMix: 5s before track ends → fade out if crossfade, then advance
        function agCheckAutoMix() {
            if (!agAutoMixEnabled || agAutoMixFading) return;
            const video = document.querySelector('video');
            if (!video || video.paused || !isFinite(video.duration) || video.duration <= 0) return;
            const remaining = video.duration - video.currentTime;
            if (remaining > 0 && remaining <= 5) {
                agAutoMixFading = true;
                if (agCrossfadeEnabled) {
                    const startVol = video.volume;
                    let stepCount = 0;
                    const totalSteps = 50;
                    const fadeTimer = setInterval(function() {
                        stepCount++;
                        video.volume = Math.max(0, startVol * (1 - stepCount / totalSteps));
                        if (stepCount >= totalSteps) {
                            clearInterval(fadeTimer);
                            video.volume = startVol;
                            agAutoMixFading = false;
                            const nxt = document.getElementById('agSmNextBtn');
                            if (nxt) nxt.click();
                        }
                    }, 100);
                } else {
                    setTimeout(function() {
                        agAutoMixFading = false;
                        const nxt = document.getElementById('agSmNextBtn');
                        if (nxt) nxt.click();
                    }, 5000);
                }
            }
        }
        setInterval(agCheckAutoMix, 500);

        // Shuffle & Repeat Toggles
        const shuffleBtns = [document.getElementById('agSmHeroShuffleBtn'), document.getElementById('agSmShuffleBtn')];
        shuffleBtns.forEach(btn => {
            if (btn) {
                btn.onclick = () => {
                    studioShuffle = !studioShuffle;
                    syncStudioQueueButtons();
                };
            }
        });

        const repeatBtns = [document.getElementById('agSmHeroRepeatBtn'), document.getElementById('agSmRepeatBtn')];
        repeatBtns.forEach(btn => {
            if (btn) {
                btn.onclick = () => {
                    studioRepeat = studioRepeat === 'off' ? 'all' : studioRepeat === 'all' ? 'one' : 'off';
                    syncStudioQueueButtons();
                };
            }
        });

        syncStudioQueueButtons();

        const upNextTab = document.getElementById('agSmUpNextTab');
        const lyricsTab = document.getElementById('agSmLyricsTab');
        if (upNextTab) upNextTab.onclick = () => showStudioPanel('up-next');
        if (lyricsTab) lyricsTab.onclick = () => showStudioPanel('lyrics');
        const lyricsToggle = document.getElementById('agSmLyricsBtn');
        if (lyricsToggle) {
            lyricsToggle.onclick = () => showStudioPanel(lyricsPanelMode === 'lyrics' ? 'up-next' : 'lyrics');
        }
        showStudioPanel('up-next');

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
                else if (studioQueue.length > 0) advanceStudioQueue(-1);
                else window.history.back();
            };
        }

        const smNext = document.getElementById('agSmNextBtn');
        if (smNext) {
            smNext.onclick = () => {
                advanceStudioQueue(1);
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
            studioShuffle = !studioShuffle;
            syncStudioQueueButtons();
        };
        const heroRepeat = document.getElementById('agSmHeroRepeatBtn');
        if (heroRepeat) heroRepeat.onclick = () => {
            studioRepeat = studioRepeat === 'off' ? 'all' : studioRepeat === 'all' ? 'one' : 'off';
            syncStudioQueueButtons();
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
                // Ensure top controls are always present in the DOM
                if (typeof ensureTopControls === 'function') {
                    ensureTopControls();
                }

                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                const video = document.querySelector('video');

                // 1. Strict, high-precision in-stream ad detection (ONLY when ad is actually playing)
                const hasAdClass = !!(
                    (player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'))) ||
                    document.querySelector('.ad-showing, .ad-interrupting, ytd-player.ad-showing, ytmusic-player-bar[is-ad_]')
                );
                const isAdState = !!(player && typeof player.getAdState === 'function' && player.getAdState() > 0);
                const isAdShowing = hasAdClass || isAdState;

                if (isAdShowing && video) {
                    if (!isAdActive) {
                        isAdActive = true;
                        if (video.playbackRate >= 0.25 && video.playbackRate <= 2.0) {
                            originalPlaybackRate = video.playbackRate;
                        }
                        originalMuted = video.muted;
                    }

                    // A. Instant mute (silences ad audio immediately)
                    video.muted = true;

                    // B. Accelerate ad to 16x speed (silently finishes unskippable ads in a fraction of a second)
                    if (video.playbackRate !== 16.0) {
                        video.playbackRate = 16.0;
                    }

                    // C. Click native skip button if present
                    const skipSelectors = [
                        '.ytp-ad-skip-button',
                        '.ytp-ad-skip-button-modern',
                        '.ytp-skip-ad-button',
                        '.ytp-ad-skip-button-slot button',
                        '.ytp-ad-skip-button-container button',
                        '.ytmusic-skip-ad-button',
                        'button[class*="skip-ad"]',
                        'button[class*="ytp-ad-skip"]'
                    ];
                    for (let i = 0; i < skipSelectors.length; i++) {
                        const btns = document.querySelectorAll(skipSelectors[i]);
                        for (let j = 0; j < btns.length; j++) {
                            const btn = btns[j];
                            if (btn && typeof btn.click === 'function') {
                                try { btn.click(); } catch(e) {}
                            }
                        }
                    }

                    // D. Remove visual ad overlays
                    const adOverlays = document.querySelectorAll(
                        '.ytp-ad-player-overlay, .ytp-ad-player-overlay-layout, .ytp-ad-image-overlay, .ytp-ad-text-overlay'
                    );
                    adOverlays.forEach(ov => {
                        try { ov.remove(); } catch(e) {}
                    });
                } else {
                    // Normal video / song playing - cleanly restore genuine playback rate and volume
                    if (isAdActive) {
                        isAdActive = false;
                        if (video) {
                            video.playbackRate = originalPlaybackRate || 1.0;
                            video.muted = originalMuted;
                        }
                    } else if (video && video.playbackRate === 16.0) {
                        video.playbackRate = 1.0;
                    }
                }

                // 2. Auto-dismiss & remove YouTube Anti-Adblock Warning Modals
                const enforcement = document.querySelector('ytd-enforcement-message-view-model, yt-upsell-dialog-renderer');
                if (enforcement) {
                    const modal = enforcement.closest('tp-yt-paper-dialog') || enforcement;
                    const dismissBtn = modal.querySelector('#dismiss-button button, yt-button-renderer button');
                    if (dismissBtn && typeof dismissBtn.click === 'function') {
                        try { dismissBtn.click(); } catch(e) {}
                    }
                    try { modal.remove(); } catch(e) {}

                    // Remove backdrops
                    const backdrops = document.querySelectorAll('tp-yt-iron-overlay-backdrop');
                    backdrops.forEach(bd => {
                        try {
                            bd.removeAttribute('opened');
                            bd.remove();
                        } catch(e) {}
                    });

                    // Restore page overflow
                    if (document.body) {
                        document.body.style.setProperty('overflow', 'auto', 'important');
                    }

                    // Resume video if paused
                    if (video && video.paused) {
                        try { video.play(); } catch(e) {}
                    }
                }

                // 3. Remove non-video promotional overlays
                const promo = document.querySelector('.ytp-ad-overlay-container, ytd-banner-promo-renderer');
                if (promo) promo.remove();

            } catch(e) {}
        }

        // Throttled observer to prevent main-thread freezing and loading delays
        let _adCheckScheduled = false;
        function scheduleAdBlockCheck() {
            if (_adCheckScheduled) return;
            _adCheckScheduled = true;
            requestAnimationFrame(() => {
                _adCheckScheduled = false;
                processAdBlocker();
            });
        }

        const targetNode = document.body || document.documentElement;
        if (targetNode) {
            const observer = new MutationObserver((mutations) => {
                for (let i = 0; i < mutations.length; i++) {
                    const m = mutations[i];
                    if (m.type === 'attributes' || (m.target && m.target.id === 'movie_player')) {
                        scheduleAdBlockCheck();
                        break;
                    }
                }
            });
            observer.observe(targetNode, {
                attributes: true,
                attributeFilter: ['class'],
                childList: true,
                subtree: true
            });
        }

        // Backup periodic interval (500ms is responsive without lagging the player)
        setInterval(processAdBlocker, 500);

        // Keep active across Single Page Application (SPA) YouTube video navigations
        window.addEventListener('yt-navigate-finish', () => {
            isAdActive = false;
            if (typeof trackBrowseUrl === 'function') trackBrowseUrl();
            if (typeof updatePageBackButtonVisibility === 'function') updatePageBackButtonVisibility();
            if (typeof updatePageMode === 'function') updatePageMode();
            processAdBlocker();
        });
        window.addEventListener('popstate', () => {
            if (typeof trackBrowseUrl === 'function') trackBrowseUrl();
            if (typeof updatePageBackButtonVisibility === 'function') updatePageBackButtonVisibility();
            if (typeof updatePageMode === 'function') updatePageMode();
        });

        // Global Keyboard & Mouse Navigation Shortcuts
        window.addEventListener('keydown', (e) => {
            const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
            const isEditing = tag === 'input' || tag === 'textarea' || (e.target && e.target.isContentEditable);
            if (isEditing) return;

            // Alt + LeftArrow -> Back
            if (e.altKey && (e.key === 'ArrowLeft' || e.keyCode === 37)) {
                e.preventDefault();
                handleNavigationBack();
            } else if (e.key === 'Backspace' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
                // Backspace as back navigation when not editing text
                e.preventDefault();
                handleNavigationBack();
            }
        });

        // Mouse Button 3 (Back)
        window.addEventListener('mouseup', (e) => {
            if (e.button === 3) {
                e.preventDefault();
                handleNavigationBack();
            }
        });

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                ensureTopControls();
                injectPageBackButton();
                updatePageMode();
                processAdBlocker();
            });
            window.addEventListener('load', () => {
                ensureTopControls();
                injectPageBackButton();
                updatePageMode();
                processAdBlocker();
            });
        }

    } catch(err) {
        console.error('Antigravity Cinema Init Error:', err);
    }
})();
"""

def get_cinema_payload():
    return CINEMA_JS.replace("{adblock_css_json}", json.dumps(ADBLOCK_CSS))\
                    .replace("{cinema_css_json}", json.dumps(CINEMA_CSS))\
                    .replace("{controls_css_json}", json.dumps(CONTROLS_CSS))\
                    .replace("{studio_music_css_json}", json.dumps(STUDIO_MUSIC_CSS))\
                    .replace("{studio_assets_json}", json.dumps(STUDIO_ASSETS))

def on_loaded(window):
    """Inject permanent adblock CSS shield, cinema styling, controls styling, studio music styling, view switcher, and stealth ad-blocker engine"""
    try:
        payload = get_cinema_payload()
        if hasattr(window, 'run_js'):
            window.run_js(payload)
        else:
            window.evaluate_js(payload)
    except Exception as e:
        logging.debug(f"on_loaded injection note: {e}")

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

    # Install safe document-start CSS adblock shield
    setup_strict_adblock()
    
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

    # Secondary injection timer to guarantee injection even on fast/cached loads or missed loaded events
    def delayed_injection():
        time.sleep(1.0)
        on_loaded(window)
        time.sleep(2.0)
        on_loaded(window)

    t = threading.Thread(target=delayed_injection, daemon=True)
    t.start()
    
    try:
        webview.start(private_mode=False)
    finally:
        pass

if __name__ == '__main__':
    main()

