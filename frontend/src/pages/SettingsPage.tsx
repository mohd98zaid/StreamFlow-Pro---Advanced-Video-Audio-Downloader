import React, { useState } from "react";
import {
  Folder,
  Sliders,
  Palette,
  Bell,
  Info,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { useSettingsStore } from "../stores/useSettingsStore";
import { Button } from "../components/ui/Button";

export const SettingsPage: React.FC = () => {
  const { config, updateConfig, theme, setTheme, browseFolder } = useSettingsStore();
  const [saveToast, setSaveToast] = useState(false);

  const handleUpdate = async (partial: any) => {
    await updateConfig(partial);
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2500);
  };

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Settings & Preferences
          </h1>
          <p className="text-xs text-foreground-muted">
            Configure download directories, concurrent worker limits, appearance, and metadata embedding.
          </p>
        </div>

        {saveToast && (
          <span className="text-xs font-semibold text-success flex items-center gap-1.5 animate-fade-in">
            <CheckCircle2 className="w-4 h-4" />
            <span>Preferences saved!</span>
          </span>
        )}
      </div>

      <div className="space-y-4">
        {/* Section 1: General & Storage */}
        <div className="bg-surface border border-border rounded-2xl p-4 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-border/60">
            <Folder className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-bold text-foreground">Storage & Directories</h2>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-foreground-muted mb-1.5">
                Default Download Directory
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={config.download_path || ""}
                  readOnly
                  className="flex-1 h-9 px-3 bg-surface-elevated border border-border rounded-lg text-xs text-foreground"
                />
                <Button size="sm" variant="secondary" onClick={browseFolder}>
                  Browse Folder…
                </Button>
              </div>
              <span className="text-[11px] text-foreground-subtle mt-1 block">
                Target location on disk where all video and audio files will be merged and written.
              </span>
            </div>
          </div>
        </div>

        {/* Section 2: Download Engine & Concurrency */}
        <div className="bg-surface border border-border rounded-2xl p-4 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-border/60">
            <Sliders className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-bold text-foreground">Engine & Concurrency</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-foreground-muted mb-1.5">
                Maximum Concurrent Downloads
              </label>
              <select
                value={config.concurrent_downloads || 3}
                onChange={(e) => handleUpdate({ concurrent_downloads: parseInt(e.target.value) })}
                className="w-full h-9 bg-surface-elevated border border-border rounded-lg px-3 text-xs text-foreground focus:outline-none focus:border-primary"
              >
                {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                  <option key={n} value={n}>
                    {n} Parallel Threads
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-foreground-subtle mt-1 block">
                ThreadPool worker allocation limit for simultaneous yt-dlp tasks.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground-muted mb-1.5">
                Filename Template Pattern
              </label>
              <input
                type="text"
                value={config.filename_pattern || "%(title)s.%(ext)s"}
                onChange={(e) => handleUpdate({ filename_pattern: e.target.value })}
                className="w-full h-9 bg-surface-elevated border border-border rounded-lg px-3 text-xs text-foreground focus:outline-none focus:border-primary font-mono"
              />
              <span className="text-[11px] text-foreground-subtle mt-1 block">
                Standard yt-dlp format string (e.g. <code>%(title)s.%(ext)s</code>).
              </span>
            </div>
          </div>
        </div>

        {/* Section 3: Appearance & Theme */}
        <div className="bg-surface border border-border rounded-2xl p-4 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-border/60">
            <Palette className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-bold text-foreground">Visual Appearance</h2>
          </div>

          <div className="flex items-center gap-3">
            {[
              { id: "dark", label: "Dark (Recommended)" },
              { id: "light", label: "Light Mode" },
              { id: "system", label: "System Sync" },
            ].map((th) => (
              <button
                key={th.id}
                onClick={() => {
                  setTheme(th.id as any);
                  handleUpdate({ theme: th.id });
                }}
                className={`flex-1 py-2.5 px-3 rounded-xl border text-xs font-semibold transition-all ${
                  theme === th.id
                    ? "bg-primary text-white border-primary shadow-sm"
                    : "bg-surface-elevated text-foreground-muted border-border hover:text-foreground"
                }`}
              >
                {th.label}
              </button>
            ))}
          </div>
        </div>

        {/* Section 4: Notifications & Metadata */}
        <div className="bg-surface border border-border rounded-2xl p-4 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-border/60">
            <Bell className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-bold text-foreground">Notifications & Metadata</h2>
          </div>

          <div className="space-y-3">
            <label className="flex items-center justify-between p-2 rounded-xl hover:bg-surface-elevated cursor-pointer select-none">
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  Windows Desktop Toast Notifications
                </span>
                <span className="block text-[11px] text-foreground-subtle">
                  Receive Windows notification when downloads complete or fail in the background.
                </span>
              </div>
              <input
                type="checkbox"
                checked={config.notifications_enabled ?? true}
                onChange={(e) => handleUpdate({ notifications_enabled: e.target.checked })}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-border cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between p-2 rounded-xl hover:bg-surface-elevated cursor-pointer select-none">
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  Always Embed Thumbnail Artwork
                </span>
                <span className="block text-[11px] text-foreground-subtle">
                  Embeds album cover or video preview thumbnail into audio and video files.
                </span>
              </div>
              <input
                type="checkbox"
                checked={config.embed_thumbnail ?? true}
                onChange={(e) => handleUpdate({ embed_thumbnail: e.target.checked })}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-border cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between p-2 rounded-xl hover:bg-surface-elevated cursor-pointer select-none">
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  Always Embed Metadata Tags
                </span>
                <span className="block text-[11px] text-foreground-subtle">
                  Embeds artist, track title, album, and release date into ID3 / MP4 tags.
                </span>
              </div>
              <input
                type="checkbox"
                checked={config.embed_metadata ?? true}
                onChange={(e) => handleUpdate({ embed_metadata: e.target.checked })}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-border cursor-pointer"
              />
            </label>
          </div>
        </div>

        {/* Section 5: About & Engine Status */}
        <div className="bg-surface border border-border rounded-2xl p-4 space-y-3 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-border/60">
            <Info className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-bold text-foreground">About StreamFlow Pro</h2>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-foreground-muted">
            <div className="space-y-0.5">
              <span className="text-foreground font-bold">StreamFlow Pro Desktop Workstation</span>
              <span className="block text-[11px] text-foreground-subtle">
                Version 3.0.0 (Tauri + React + Python Architecture)
              </span>
            </div>

            <div className="flex items-center gap-2">
              <a
                href="https://github.com/mohd98zaid/StreamFlow-Pro---Advanced-Video-Audio-Downloader"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-foreground hover:text-primary transition-colors text-xs font-semibold"
              >
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                <span>GitHub Repository</span>
                <ExternalLink className="w-3 h-3 text-foreground-subtle ml-0.5" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
