import { create } from "zustand";
import { DownloadItem, DownloadStats } from "../types/download";
import { api } from "../services/api";
import { useToastStore } from "./useToastStore";

interface HistoryStore {
  items: DownloadItem[];
  stats: DownloadStats | null;
  searchQuery: string;
  statusFilter: string;
  isLoading: boolean;

  fetchHistory: () => Promise<void>;
  fetchStats: () => Promise<void>;
  setSearchQuery: (query: string) => void;
  setStatusFilter: (filter: string) => void;
  deleteItem: (id: string) => Promise<void>;
  clearAll: () => Promise<void>;
  openFile: (path: string) => Promise<void>;
  openFolder: (path?: string) => Promise<void>;
}

export const useHistoryStore = create<HistoryStore>((set, get) => ({
  items: [],
  stats: null,
  searchQuery: "",
  statusFilter: "All",
  isLoading: false,

  fetchHistory: async () => {
    set({ isLoading: true });
    try {
      const data = await api.getHistory({
        search: get().searchQuery || undefined,
        status: get().statusFilter !== "All" ? get().statusFilter : undefined,
      });
      set({ items: data.items, isLoading: false });
    } catch (err) {
      console.error("Failed to load history:", err);
      set({ isLoading: false });
    }
  },

  fetchStats: async () => {
    try {
      const stats = await api.getStatistics();
      set({ stats });
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  },

  setSearchQuery: (searchQuery: string) => {
    set({ searchQuery });
    get().fetchHistory();
  },

  setStatusFilter: (statusFilter: string) => {
    set({ statusFilter });
    get().fetchHistory();
  },

  deleteItem: async (id: string) => {
    try {
      await api.deleteHistoryItem(id);
      await get().fetchHistory();
      await get().fetchStats();
    } catch (err: any) {
      useToastStore.getState().error(err?.message || "We couldn't remove that history item", "History Error");
    }
  },

  clearAll: async () => {
    try {
      await api.clearHistory();
      set({ items: [] });
      await get().fetchStats();
    } catch (err: any) {
      useToastStore.getState().error(err?.message || "We couldn't clear history", "History Error");
    }
  },

  openFile: async (filePath: string) => {
    try {
      await api.openFile(filePath);
    } catch (err: any) {
      useToastStore.getState().error(err.message || "Failed to open file", "File Error");
    }
  },

  openFolder: async (path?: string) => {
    try {
      await api.openFolder(path);
    } catch (err: any) {
      useToastStore.getState().error(err.message || "Failed to open folder", "Folder Error");
    }
  },
}));
