import { create } from "zustand";
import { AppConfig } from "../types/config";
import { api } from "../services/api";

interface SettingsStore {
  config: AppConfig;
  isLoading: boolean;
  theme: "dark" | "light" | "system";

  loadConfig: () => Promise<void>;
  updateConfig: (partial: Partial<AppConfig>) => Promise<void>;
  setTheme: (theme: "dark" | "light" | "system") => void;
  browseFolder: () => Promise<string | null>;
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  config: {
    download_path: "",
    theme: "dark",
    concurrent_downloads: 3,
    notifications_enabled: true,
    embed_thumbnail: true,
    embed_metadata: true,
    embed_subtitles: false,
  },
  isLoading: false,
  theme: "dark",

  loadConfig: async () => {
    set({ isLoading: true });
    try {
      const cfg = await api.getConfig();
      set({ config: cfg, theme: cfg.theme || "dark", isLoading: false });
      get().setTheme(cfg.theme || "dark");
    } catch (err) {
      console.error("Failed to load settings:", err);
      set({ isLoading: false });
    }
  },

  updateConfig: async (partial: Partial<AppConfig>) => {
    try {
      const updated = await api.updateConfig(partial);
      set({ config: updated });
      if (partial.theme) {
        get().setTheme(partial.theme);
      }
    } catch (err) {
      console.error("Failed to update settings:", err);
    }
  },

  setTheme: (theme: "dark" | "light" | "system") => {
    set({ theme });
    const root = document.documentElement;
    root.classList.remove("dark", "light");

    if (theme === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.classList.add(prefersDark ? "dark" : "light");
    } else {
      root.classList.add(theme);
    }
  },

  browseFolder: async () => {
    try {
      const res = await api.browseDirectory();
      if (res.success && res.selected_path) {
        await get().updateConfig({ download_path: res.selected_path });
        return res.selected_path;
      }
    } catch (err) {
      console.error("Failed to browse folder:", err);
    }
    return null;
  },
}));
