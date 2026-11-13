import { WebSocketEnvelope } from "../types/events";

type EventHandler = (envelope: WebSocketEnvelope) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url = "ws://127.0.0.1:47891/ws";
  private listeners: Set<EventHandler> = new Set();
  private reconnectInterval = 2000;
  private isConnecting = false;
  private pingTimer: number | null = null;
  private reconnectTimer: number | null = null;
  private shouldReconnect = true;

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.shouldReconnect = true;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.isConnecting = true;
    try {
      const socket = new WebSocket(this.url);
      this.ws = socket;

      socket.onopen = () => {
        this.isConnecting = false;
        // Start ping interval
        if (this.pingTimer) window.clearInterval(this.pingTimer);
        this.pingTimer = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 15000);
      };

      socket.onmessage = (event) => {
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
        } catch {
          // not JSON or ignored
        }
      };

      socket.onclose = () => {
        this.isConnecting = false;
        if (this.pingTimer) window.clearInterval(this.pingTimer);
        this.pingTimer = null;
        if (this.ws === socket) this.ws = null;
        if (this.shouldReconnect && this.ws === null && this.reconnectTimer === null) {
          this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
          }, this.reconnectInterval);
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    } catch {
      this.isConnecting = false;
      if (this.shouldReconnect && this.reconnectTimer === null) {
        this.reconnectTimer = window.setTimeout(() => {
          this.reconnectTimer = null;
          this.connect();
        }, this.reconnectInterval);
      }
    }
  }

  subscribe(handler: EventHandler) {
    this.listeners.add(handler);
    return () => {
      this.listeners.delete(handler);
    };
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.pingTimer) window.clearInterval(this.pingTimer);
    this.pingTimer = null;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new WebSocketClient();
