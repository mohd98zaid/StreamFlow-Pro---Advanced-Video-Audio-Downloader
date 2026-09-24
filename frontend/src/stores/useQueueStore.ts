import { create } from "zustand";
import { DownloadItem, QueueSummary } from "../types/download";
import { api } from "../services/api";
import { wsClient } from "../services/websocket";
import { WebSocketEnvelope } from "../types/events";

interface QueueStore {
  items: DownloadItem[];
  summary: QueueSummary;
  isLoading: boolean;
  statusMessage: string;

  fetchQueue: () => Promise<void>;
  pauseItem: (id: string) => Promise<void>;
  resumeItem: (id: string) => Promise<void>;
  cancelItem: (id: string) => Promise<void>;
  retryItem: (id: string) => Promise<void>;
  removeItem: (id: string) => Promise<void>;
  pauseAll: () => Promise<void>;
  resumeAll: () => Promise<void>;
  clearCompleted: () => Promise<void>;
  handleWebSocketEvent: (envelope: WebSocketEnvelope) => void;
}

export const useQueueStore = create<QueueStore>((set, get) => ({
  items: [],
  summary: {
    total: 0,
    active: 0,
    queued: 0,
    paused: 0,
    completed: 0,
    failed: 0,
  },
  isLoading: false,
  statusMessage: "Engine Ready",

  fetchQueue: async () => {
    try {
      const data = await api.getQueue();
      set({ items: data.items, summary: data.summary });
    } catch (err) {
      console.error("Failed to fetch queue:", err);
    }
  },

  pauseItem: async (id: string) => {
    // Optimistic update
    set((state) => ({
      items: state.items.map((i) => (i.id === id ? { ...i, status: "Paused", speed: "Paused" } : i)),
    }));
    await api.pauseItem(id);
  },

  resumeItem: async (id: string) => {
    set((state) => ({
      items: state.items.map((i) => (i.id === id ? { ...i, status: "Queued", speed: "Waiting" } : i)),
    }));
    await api.resumeItem(id);
  },

  cancelItem: async (id: string) => {
    set((state) => ({
      items: state.items.map((i) => (i.id === id ? { ...i, status: "Cancelled", speed: "Cancelled" } : i)),
    }));
    await api.cancelItem(id);
  },

  retryItem: async (id: string) => {
    await api.retryItem(id);
    get().fetchQueue();
  },

  removeItem: async (id: string) => {
    set((state) => ({
      items: state.items.filter((i) => i.id !== id),
    }));
    await api.removeItem(id);
  },

  pauseAll: async () => {
    await api.pauseAll();
    get().fetchQueue();
  },

  resumeAll: async () => {
    await api.resumeAll();
    get().fetchQueue();
  },

  clearCompleted: async () => {
    await api.clearCompleted();
    get().fetchQueue();
  },

  handleWebSocketEvent: (envelope: WebSocketEnvelope) => {
    const { event, data } = envelope;

    if (event === "connected") {
      if (data?.queue) {
        set({ items: data.queue.items, summary: data.queue.summary });
      }
    } else if (event === "download_progress" && data?.id) {
      set((state) => {
        const index = state.items.findIndex((it) => it.id === data.id);
        if (index !== -1) {
          const updated = [...state.items];
          updated[index] = { ...updated[index], ...data };
          return { items: updated };
        } else {
          return { items: [data, ...state.items] };
        }
      });
    } else if (event === "queue_updated") {
      get().fetchQueue();
    } else if (event === "download_completed" || event === "download_failed") {
      get().fetchQueue();
    } else if (event === "status_message" && typeof data === "string") {
      set({ statusMessage: data });
    }
  },
}));

// Auto-wire WebSocket listener
wsClient.subscribe((envelope) => {
  useQueueStore.getState().handleWebSocketEvent(envelope);
});
