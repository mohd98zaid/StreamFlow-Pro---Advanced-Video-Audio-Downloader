import { WebSocketEnvelope } from "../types/events";

type EventHandler = (envelope: WebSocketEnvelope) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url = "ws://127.0.0.1:47891/ws";
  private listeners: Set<EventHandler> = new Set();
  private reconnectInterval = 2000;
  private isConnecting = false;
  private pingTimer: number | null = null;

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isConnecting = true;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        // Start ping interval
        if (this.pingTimer) window.clearInterval(this.pingTimer);
        this.pingTimer = window.setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send("ping");
          }
        }, 15000);
      };

      this.ws.onmessage = (event) => {
        try {
          if (event.data === "pong") return;
          const envelope: WebSocketEnvelope = JSON.parse(event.data);
          this.listeners.forEach((fn) => {
            try {
              fn(envelope);
            } catch (err) {
              console.error("Error in WS handler:", err);
            }
          });
        } catch (e) {
          // not JSON or ignored
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        if (this.pingTimer) window.clearInterval(this.pingTimer);
        setTimeout(() => this.connect(), this.reconnectInterval);
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch (err) {
      this.isConnecting = false;
      setTimeout(() => this.connect(), this.reconnectInterval);
    }
  }

  subscribe(handler: EventHandler) {
    this.listeners.add(handler);
    return () => {
      this.listeners.delete(handler);
    };
  }

  disconnect() {
    if (this.pingTimer) window.clearInterval(this.pingTimer);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new WebSocketClient();
