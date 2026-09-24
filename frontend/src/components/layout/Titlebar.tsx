import React, { useState, useEffect } from "react";
import { Minus, Square, X, Sun, Moon, Radio } from "lucide-react";
import { useSettingsStore } from "../../stores/useSettingsStore";
import { useQueueStore } from "../../stores/useQueueStore";

export const Titlebar: React.FC = () => {
  const { theme, setTheme } = useSettingsStore();
  const { summary } = useQueueStore();
  const [isTauri, setIsTauri] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && (window as any).__TAURI__) {
      setIsTauri(true);
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
  };

  const handleMinimize = async () => {
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window" as any);
      const win = getCurrentWindow();
      await win.minimize();
    } catch {}
  };

  const handleMaximize = async () => {
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window" as any);
      const win = getCurrentWindow();
      await win.toggleMaximize();
    } catch {}
  };

  const handleClose = async () => {
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window" as any);
      const win = getCurrentWindow();
      await win.close();
    } catch {}
  };

  return (
    <header className="h-10 w-full bg-surface border-b border-border flex items-center justify-between px-3 select-none flex-shrink-0 titlebar-drag-region z-50">
      {/* Brand & Status */}
      <div className="flex items-center gap-2.5 titlebar-no-drag">
        {/* Animated Brand Bars */}
        <div className="flex items-end gap-[2px] h-3.5 px-0.5">
          <span className="w-[2.5px] h-2 bg-gradient-to-t from-primary to-accent-cyan rounded-full animate-pulse" />
          <span className="w-[2.5px] h-3.5 bg-gradient-to-t from-primary to-accent-cyan rounded-full" />
          <span className="w-[2.5px] h-2.5 bg-gradient-to-t from-primary to-accent-cyan rounded-full animate-pulse" />
          <span className="w-[2.5px] h-1.5 bg-gradient-to-t from-primary to-accent-cyan rounded-full" />
        </div>

        <span className="text-xs font-bold tracking-tight text-foreground flex items-center gap-1.5">
          StreamFlow <span className="text-primary font-black">PRO</span>
        </span>

        {summary.active > 0 && (
          <span className="flex items-center gap-1 text-[11px] font-semibold text-accent-cyan bg-accent-cyan/10 px-2 py-0.5 rounded-full border border-accent-cyan/20">
            <Radio className="w-2.5 h-2.5 animate-pulse" />
            {summary.active} active
          </span>
        )}
      </div>

      {/* Center Drag Area */}
      <div className="flex-1 h-full titlebar-drag-region" />

      {/* Right Controls */}
      <div className="flex items-center gap-1 titlebar-no-drag">
        {/* Theme Switcher Button */}
        <button
          onClick={toggleTheme}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          className="w-7 h-7 flex items-center justify-center rounded-md text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
        >
          {theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
        </button>

        {isTauri && (
          <div className="flex items-center ml-1 border-l border-border/70 pl-1">
            <button
              onClick={handleMinimize}
              className="w-7 h-7 flex items-center justify-center rounded-md text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleMaximize}
              className="w-7 h-7 flex items-center justify-center rounded-md text-foreground-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
            >
              <Square className="w-3 h-3" />
            </button>
            <button
              onClick={handleClose}
              className="w-7 h-7 flex items-center justify-center rounded-md text-foreground-muted hover:text-danger hover:bg-danger/10 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
