import React from "react";
import {
  DownloadCloud,
  ListVideo,
  History,
  Search,
  Settings,
  FolderOpen,
  Tv,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useQueueStore } from "../../stores/useQueueStore";
import { useSettingsStore } from "../../stores/useSettingsStore";
import { api } from "../../services/api";

export type NavTab = "download" | "queue" | "history" | "search" | "settings";

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const { summary } = useQueueStore();
  const { config } = useSettingsStore();

  const handleOpenFolder = () => {
    api.openFolder(config.download_path);
  };

  const navItems = [
    {
      id: "download" as NavTab,
      label: "New Download",
      icon: DownloadCloud,
    },
    {
      id: "queue" as NavTab,
      label: "Downloads",
      icon: ListVideo,
      badge: summary.active > 0 ? summary.active : summary.queued > 0 ? summary.queued : undefined,
      badgeColor: summary.active > 0 ? "bg-accent-cyan text-black" : "bg-surface-elevated text-foreground-muted",
    },
    {
      id: "history" as NavTab,
      label: "History",
      icon: History,
    },
    {
      id: "search" as NavTab,
      label: "Search YouTube",
      icon: Search,
    },
  ];

  return (
    <aside className="w-56 glass-panel border-r border-border-glass flex flex-col justify-between p-3 select-none flex-shrink-0 z-30">
      {/* Navigation Group */}
      <div className="space-y-4">
        {/* Quick Launch CTA */}
        <div>
          <button
            onClick={() => onTabChange("download")}
            className="w-full flex items-center justify-center gap-2 h-10 px-4 rounded-2xl bg-gradient-to-r from-primary to-primary-hover text-white font-semibold text-xs tracking-wide shadow-glass-sm hover:shadow-glass hover:brightness-105 transition-all duration-150 active:scale-[0.98]"
          >
            <DownloadCloud className="w-4 h-4" />
            <span>+ New Download</span>
          </button>
        </div>

        {/* Primary Navigation Links */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all duration-150 group relative",
                  isActive
                    ? "bg-surface-elevated/90 text-primary border border-border-glass shadow-sm font-bold"
                    : "text-foreground-muted hover:text-foreground hover:bg-surface-elevated/50"
                )}
              >
                <div className="flex items-center gap-2.5">
                  <Icon
                    className={cn(
                      "w-4 h-4 transition-colors",
                      isActive ? "text-primary" : "text-foreground-subtle group-hover:text-foreground-muted"
                    )}
                  />
                  <span>{item.label}</span>
                </div>

                {item.badge !== undefined && (
                  <span
                    className={cn(
                      "px-1.5 py-0.2 rounded-full text-[10px] font-bold min-w-[18px] text-center shadow-sm",
                      item.badgeColor
                    )}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Actions */}
      <div className="space-y-1.5 pt-3 border-t border-border-glass">
        {/* Ad-Free Studio Launcher Quick Action */}
        <button
          onClick={() => api.openPlayer("https://www.youtube.com", "YouTube Browser")}
          title="Launch YouTube in dedicated ad-free player browser"
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-foreground-muted hover:text-accent-cyan hover:bg-accent-cyan/10 transition-colors"
        >
          <Tv className="w-4 h-4 text-accent-cyan" />
          <span>Ad-Free Player</span>
        </button>

        {/* Open Download Directory */}
        <button
          onClick={handleOpenFolder}
          title="Open downloads directory in Windows Explorer"
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-foreground-muted hover:text-foreground hover:bg-surface-elevated/60 transition-colors"
        >
          <FolderOpen className="w-4 h-4 text-foreground-subtle" />
          <span>Open Folder</span>
        </button>

        {/* Settings Tab */}
        <button
          onClick={() => onTabChange("settings")}
          className={cn(
            "w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-colors",
            activeTab === "settings"
              ? "bg-surface-elevated/90 text-primary border border-border-glass font-bold"
              : "text-foreground-muted hover:text-foreground hover:bg-surface-elevated/60"
          )}
        >
          <Settings className="w-4 h-4 text-foreground-subtle" />
          <span>Settings</span>
        </button>

        {/* Engine Ready Badge */}
        <div className="pt-2 px-1 flex items-center justify-between text-[10px] text-foreground-subtle">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            <span className="font-medium text-foreground-muted">Engine v3.0</span>
          </div>
          <span>yt-dlp</span>
        </div>
      </div>
    </aside>
  );
};
