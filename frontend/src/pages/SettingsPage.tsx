import React from "react";
import {
  Folder,
  Sliders,
  Palette,
  Bell,
  Info,
  CheckCircle2,
  ExternalLink,
  HardDrive,
  Cpu,
} from "lucide-react";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useToastStore } from "../stores/useToastStore";
import { GlassSurface } from "../components/ui/GlassSurface";

export const SettingsPage: React.FC = () => {
  const { config, updateConfig, theme, setTheme, browseFolder } = useSettingsStore();
  const toast = useToastStore();

  const handleUpdate = async (partial: any) => {
    await updateConfig(partial);
    toast.success("Preferences saved successfully", "Settings Updated");
  };

  return (
    <div className="w-full h-full overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto animate-fade-in select-none">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>Settings & Preferences</span>
          </h1>
          <p className="text-xs text-foreground-muted">
            Configure download directories, concurrent worker threads, appearance themes, and metadata tags.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Section 1: Storage & Directories */}
        <GlassSurface variant="panel" className="p-5 space-y-4">
          <div className="flex items-center gap-2.5 pb-2.5 border-b border-border-hairline">
            <div className="w-7 h-7 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <Folder className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Storage & Directories</h2>
              <span className="text-[11px] text-foreground-subtle">Manage target media destination on disk</span>
            </div>
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
                  className="flex-1 h-10 px-3.5 bg-surface-elevated/70 border border-border-glass rounded-xl text-xs text-foreground font-mono"
                />
                <button
                  onClick={browseFolder}
                  className="h-10 px-4 rounded-xl glass-card hover:bg-surface-elevated border border-border-glass text-xs font-semibold text-foreground transition-colors"
                >
                  Browse Folder…
                </button>
              </div>
              <span className="text-[11px] text-foreground-subtle mt-1.5 block">
                Target location where merged video, audio, and cover art are saved.
              </span>
            </div>
          </div>
        </GlassSurface>

        {/* Section 2: Download Engine & Concurrency */}
        <GlassSurface variant="panel" className="p-5 space-y-4">
          <div className="flex items-center gap-2.5 pb-2.5 border-b border-border-hairline">
            <div className="w-7 h-7 rounded-xl bg-accent-cyan/10 flex items-center justify-center text-accent-cyan">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Engine & Thread Allocation</h2>
              <span className="text-[11px] text-foreground-subtle">Adjust worker parallelism and file templates</span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-foreground-muted mb-1.5">
                Concurrent Download Workers
              </label>
              <select
                value={config.concurrent_downloads || 3}
                onChange={(e) => handleUpdate({ concurrent_downloads: parseInt(e.target.value) })}
                className="w-full h-10 bg-surface-elevated/80 border border-border-glass rounded-xl px-3.5 text-xs text-foreground focus:outline-none focus:border-primary font-medium"
              >
                {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                  <option key={n} value={n}>
                    {n} Parallel Threads
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-foreground-subtle mt-1.5 block">
                Thread pool allocation for simultaneous yt-dlp tasks.
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
                className="w-full h-10 bg-surface-elevated/80 border border-border-glass rounded-xl px-3.5 text-xs text-foreground focus:outline-none focus:border-primary font-mono"
              />
              <span className="text-[11px] text-foreground-subtle mt-1.5 block">
                Standard yt-dlp format string (e.g. <code>%(title)s.%(ext)s</code>).
              </span>
            </div>
          </div>
        </GlassSurface>

        {/* Section 3: Visual Appearance */}
        <GlassSurface variant="panel" className="p-5 space-y-4">
          <div className="flex items-center gap-2.5 pb-2.5 border-b border-border-hairline">
            <div className="w-7 h-7 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <Palette className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Theme & Visual Experience</h2>
              <span className="text-[11px] text-foreground-subtle">Yuma Design System (YDS) color palette</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {[
              { id: "dark", label: "Dark Workstation (Recommended)" },
              { id: "light", label: "Neutral Light Glass" },
              { id: "system", label: "System Windows Sync" },
            ].map((th) => (
              <button
                key={th.id}
                onClick={() => {
                  setTheme(th.id as any);
                  handleUpdate({ theme: th.id });
                }}
                className={`flex-1 py-3 px-3 rounded-2xl border text-xs font-semibold transition-all ${
                  theme === th.id
                    ? "bg-primary text-white border-primary shadow-sm font-bold"
                    : "glass-card text-foreground-muted hover:text-foreground"
                }`}
              >
                {th.label}
              </button>
            ))}
          </div>
        </GlassSurface>

        {/* Section 4: Notifications & Metadata */}
        <GlassSurface variant="panel" className="p-5 space-y-4">
          <div className="flex items-center gap-2.5 pb-2.5 border-b border-border-hairline">
            <div className="w-7 h-7 rounded-xl bg-accent-cyan/10 flex items-center justify-center text-accent-cyan">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Notifications & Tag Embedding</h2>
              <span className="text-[11px] text-foreground-subtle">Configure automatic post-processing</span>
            </div>
          </div>

          <div className="space-y-3">
            <label className="flex items-center justify-between p-3 rounded-2xl hover:bg-surface-elevated/60 cursor-pointer select-none border border-border-hairline transition-colors">
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
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-border-glass cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded-2xl hover:bg-surface-elevated/60 cursor-pointer select-none border border-border-hairline transition-colors">
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  Always Embed Thumbnail Artwork
                </span>
                <span className="block text-[11px] text-foreground-subtle">
                  Embeds cover art directly into audio and video files using FFmpeg.
                </span>
              </div>
              <input
                type="checkbox"
                checked={config.embed_thumbnail ?? true}
                onChange={(e) => handleUpdate({ embed_thumbnail: e.target.checked })}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-border-glass cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded-2xl hover:bg-surface-elevated/60 cursor-pointer select-none border border-border-hairline transition-colors">
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  Always Embed Metadata Tags
                </span>
                <span className="block text-[11px] text-foreground-subtle">
                  Embeds artist name, release year, album, and track title into ID3/MP4 tags.
                </span>
              </div>
              <input
                type="checkbox"
                checked={config.embed_metadata ?? true}
                onChange={(e) => handleUpdate({ embed_metadata: e.target.checked })}
                className="w-4 h-4 rounded text-primary focus:ring-0 bg-surface border-border-glass cursor-pointer"
              />
            </label>
          </div>
        </GlassSurface>

        {/* Section 5: About StreamFlow Pro */}
        <GlassSurface variant="panel" className="p-5 space-y-3">
          <div className="flex items-center gap-2.5 pb-2.5 border-b border-border-hairline">
            <div className="w-7 h-7 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <Info className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">About StreamFlow Pro</h2>
              <span className="text-[11px] text-foreground-subtle">System information & upstream credits</span>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-foreground-muted pt-1">
            <div className="space-y-0.5">
              <span className="text-foreground font-bold">StreamFlow Pro Media Workstation</span>
              <span className="block text-[11px] text-foreground-subtle">
                Version 3.0.0 (Tauri v2 + React 19 + Python Engine)
              </span>
            </div>

            <div className="flex items-center gap-2">
              <a
                href="https://github.com/mohd98zaid/StreamFlow-Pro---Advanced-Video-Audio-Downloader"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-card text-foreground hover:text-primary transition-colors text-xs font-semibold"
              >
                <span>GitHub Repository</span>
                <ExternalLink className="w-3 h-3 text-foreground-subtle ml-0.5" />
              </a>
            </div>
          </div>
        </GlassSurface>
      </div>
    </div>
  );
};
