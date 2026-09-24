"""
StreamFlow Pro - Local Backend Server
FastAPI + WebSocket bridge strictly bound to 127.0.0.1.
Enables modern desktop frontend (Tauri/React) to communicate with core Python engine.
"""
import sys
import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.api_adapter import BackendApiAdapter
from core.events import Event, EventBus
from core.models import DownloadItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("StreamFlow.Bridge")

app = FastAPI(title="StreamFlow Pro Desktop Bridge", version="1.0.0")

# Enable CORS for local desktop UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

adapter = BackendApiAdapter()

# Active WebSocket connections
connected_websockets: Set[WebSocket] = set()
main_loop: Optional[asyncio.AbstractEventLoop] = None


class ConnectionManager:
    """Manages WebSocket clients and real-time broadcasting."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send to client, removing: {e}")
                self.disconnect(connection)


ws_manager = ConnectionManager()


def dispatch_event_to_ws(event: Event, data: Any):
    """Bridge EventBus emissions to WebSocket clients asynchronously."""
    global main_loop
    if not main_loop or not ws_manager.active_connections:
        return

    payload: Dict[str, Any] = {
        "event": event.value,
        "timestamp": datetime.now().isoformat(),
        "data": None,
    }

    if isinstance(data, DownloadItem):
        payload["data"] = adapter._item_to_dict(data)
    elif isinstance(data, dict):
        payload["data"] = data
    elif isinstance(data, (str, int, float, bool)):
        payload["data"] = data
    elif data is None and event == Event.QUEUE_UPDATED:
        payload["data"] = adapter.get_queue()

    asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), main_loop)


# Wire EventBus to WebSocket broadcast
for ev in Event:
    adapter.event_bus.subscribe(ev, lambda d, e=ev: dispatch_event_to_ws(e, d))


# ------------------------------------------------------------------------------
# WEBSOCKET ENDPOINT
# ------------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global main_loop
    main_loop = asyncio.get_running_loop()
    await ws_manager.connect(websocket)

    # Send initial state snapshot on connection
    try:
        await websocket.send_json({
            "event": "connected",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "queue": adapter.get_queue(),
                "config": adapter.get_config(),
                "presets": adapter.get_presets(),
            }
        })
        while True:
            # Keep socket alive and accept ping / incoming commands
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket loop error: {e}")
        ws_manager.disconnect(websocket)


# ------------------------------------------------------------------------------
# REST API SCHEMAS & ROUTES
# ------------------------------------------------------------------------------
class ValidateRequest(BaseModel):
    text: str


class MetadataRequest(BaseModel):
    url: str


class AddDownloadRequest(BaseModel):
    urls: List[str]
    download_type: str = "video"
    quality: str = "1080p (Full HD)"
    format_type: str = "mp4"
    options: Optional[Dict[str, Any]] = None
    save_path: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    limit: int = 15


class OpenFileRequest(BaseModel):
    file_path: str


class OpenFolderRequest(BaseModel):
    path: Optional[str] = None


class OpenPlayerRequest(BaseModel):
    video_id: str
    title: str = "Video Preview"


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "StreamFlow Pro Bridge", "engine_ready": True}


@app.get("/api/config")
def get_config():
    return adapter.get_config()


@app.post("/api/config")
def update_config(payload: Dict[str, Any] = Body(...)):
    return adapter.update_config(payload)


@app.get("/api/presets")
def get_presets():
    return adapter.get_presets()


@app.post("/api/validate")
def validate_url_input(req: ValidateRequest):
    return adapter.validate_input(req.text)


@app.post("/api/metadata")
def get_url_metadata(req: MetadataRequest):
    res = adapter.fetch_metadata(req.url)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Metadata extraction failed"))
    return res


@app.get("/api/queue")
def get_queue():
    return adapter.get_queue()


@app.post("/api/downloads/add")
def add_downloads(req: AddDownloadRequest):
    res = adapter.add_downloads(
        urls=req.urls,
        download_type=req.download_type,
        quality=req.quality,
        format_type=req.format_type,
        options=req.options,
        save_path=req.save_path
    )
    return res


@app.post("/api/queue/{item_id}/pause")
def pause_item(item_id: str):
    success = adapter.pause_item(item_id)
    return {"success": success}


@app.post("/api/queue/{item_id}/resume")
def resume_item(item_id: str):
    success = adapter.resume_item(item_id)
    return {"success": success}


@app.post("/api/queue/{item_id}/cancel")
def cancel_item(item_id: str):
    success = adapter.cancel_item(item_id)
    return {"success": success}


@app.post("/api/queue/{item_id}/retry")
def retry_item(item_id: str):
    success = adapter.retry_item(item_id)
    return {"success": success}


@app.post("/api/queue/{item_id}/remove")
def remove_item(item_id: str):
    success = adapter.remove_item(item_id)
    return {"success": success}


@app.post("/api/queue/pause_all")
def pause_all():
    count = adapter.pause_all()
    return {"success": True, "count": count}


@app.post("/api/queue/resume_all")
def resume_all():
    count = adapter.resume_all()
    return {"success": True, "count": count}


@app.post("/api/queue/clear_completed")
def clear_completed():
    count = adapter.clear_completed()
    return {"success": True, "count": count}


@app.get("/api/history")
def get_history(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    return adapter.get_history(search_query=search, status_filter=status, limit=limit, offset=offset)


@app.delete("/api/history/{item_id}")
def delete_history_item(item_id: str):
    success = adapter.delete_history_item(item_id)
    return {"success": success}


@app.post("/api/history/clear")
def clear_history():
    success = adapter.clear_history()
    return {"success": success}


@app.get("/api/stats")
def get_statistics():
    return adapter.get_statistics()


@app.post("/api/search")
def search_youtube(req: SearchRequest):
    results = adapter.search_youtube(req.query, limit=req.limit)
    return {"results": results, "count": len(results)}


@app.post("/api/actions/open_file")
def open_file(req: OpenFileRequest):
    res = adapter.open_file(req.file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/actions/open_folder")
def open_folder(req: OpenFolderRequest):
    res = adapter.open_folder(req.path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/actions/open_player")
def open_player(req: OpenPlayerRequest):
    res = adapter.launch_player(req.video_id, req.title)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res


@app.post("/api/actions/browse_directory")
def browse_directory():
    """Trigger native folder picker dialog and return selected path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        curr = adapter.config_manager.get("download_path")
        folder = filedialog.askdirectory(initialdir=curr, title="Select Download Directory")
        root.destroy()
        if folder:
            return {"success": True, "selected_path": folder}
        return {"success": False, "cancelled": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/system/shutdown")
def shutdown():
    adapter.downloader.shutdown()
    return {"success": True, "message": "Downloader engine shutdown cleanly"}


def start_server(host: str = "127.0.0.1", port: int = 47891):
    """Run server programmatically."""
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start_server()
