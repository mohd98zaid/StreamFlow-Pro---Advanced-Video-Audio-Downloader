import { create } from "zustand";
import { DownloadItem, QueueSummary } from "../types/download";
import { api } from "../services/api";
import { wsClient } from "../services/websocket";
import { WebSocketEnvelope } from "../types/events";
import { useToastStore } from "./useToastStore";

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
    cancelled: 0,
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
    try {
      const result = await api.pauseItem(id);
      if (!result.success) throw new Error("The download could not be paused");
      await get().fetchQueue();
    } catch (err: any) {
      await get().fetchQueue();
      useToastStore.getState().error(err?.message || "The download could not be paused", "Queue Error");
    }
  },

  resumeItem: async (id: string) => {
    set((state) => ({
      items: state.items.map((i) => (i.id === id ? { ...i, status: "Queued", speed: "Waiting" } : i)),
    }));
    try {
      const result = await api.resumeItem(id);
      if (!result.success) throw new Error("The download could not be resumed");
      await get().fetchQueue();
    } catch (err: any) {
      await get().fetchQueue();
      useToastStore.getState().error(err?.message || "The download could not be resumed", "Queue Error");
    }
  },

  cancelItem: async (id: string) => {
    set((state) => ({
      items: state.items.map((i) => (i.id === id ? { ...i, status: "Cancelled", speed: "Cancelled" } : i)),
    }));
    try {
      const result = await api.cancelItem(id);
      if (!result.success) throw new Error("The download could not be cancelled");
      await get().fetchQueue();
    } catch (err: any) {
      await get().fetchQueue();
      useToastStore.getState().error(err?.message || "The download could not be cancelled", "Queue Error");
    }
  },

  retryItem: async (id: string) => {
    try {
      const result = await api.retryItem(id);
      if (!result.success) throw new Error("The download could not be retried");
      await get().fetchQueue();
    } catch (err: any) {
      useToastStore.getState().error(err?.message || "The download could not be retried", "Queue Error");
    }
  },

  removeItem: async (id: string) => {
    set((state) => ({
      items: state.items.filter((i) => i.id !== id),
    }));
    try {
      const result = await api.removeItem(id);
      if (!result.success) throw new Error("The queue item could not be removed");
      await get().fetchQueue();
    } catch (err: any) {
      await get().fetchQueue();
      useToastStore.getState().error(err?.message || "The queue item could not be removed", "Queue Error");
    }
  },

  pauseAll: async () => {
    try {
      await api.pauseAll();
      await get().fetchQueue();
    } catch (err: any) {
      useToastStore.getState().error(err?.message || "The queue could not be paused", "Queue Error");
    }
  },

  resumeAll: async () => {
    try {
      await api.resumeAll();
      await get().fetchQueue();
    } catch (err: any) {
      useToastStore.getState().error(err?.message || "The queue could not be resumed", "Queue Error");
    }
  },

  clearCompleted: async () => {
    try {
      await api.clearCompleted();
      await get().fetchQueue();
    } catch (err: any) {
      useToastStore.getState().error(err?.message || "Finished queue items could not be cleared", "Queue Error");
    }
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
