import React, { useState, useEffect } from "react";
import { Titlebar } from "./components/layout/Titlebar";
import { Sidebar, NavTab } from "./components/layout/Sidebar";
import { MiniPlayer } from "./components/media/MiniPlayer";
import { ToastContainer } from "./components/ui/ToastContainer";
import { DownloadPage } from "./pages/DownloadPage";
import { DownloadsPage } from "./pages/DownloadsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { SearchPage } from "./pages/SearchPage";
import { SettingsPage } from "./pages/SettingsPage";
import { wsClient } from "./services/websocket";
import { useSettingsStore } from "./stores/useSettingsStore";
import { useDownloadStore } from "./stores/useDownloadStore";
import { useQueueStore } from "./stores/useQueueStore";

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("download");
  const { loadConfig } = useSettingsStore();
  const { loadPresets } = useDownloadStore();
  const { fetchQueue } = useQueueStore();

  useEffect(() => {
    // 1. Establish persistent WebSocket stream to local Python engine
    wsClient.connect();

    // 2. Load configurations and initial state
    void loadConfig();
    void loadPresets();
    void fetchQueue();

    return () => {
      wsClient.disconnect();
    };
  }, [fetchQueue, loadConfig, loadPresets]);

  return (
    <div className="flex flex-col min-h-dvh h-screen w-screen bg-background text-foreground overflow-hidden font-sans select-none relative app-canvas">
      {/* 1. In-App Floating Toast System */}
      <ToastContainer />

      {/* 2. Window Titlebar with native controls */}
      <Titlebar />

      {/* 3. Middle Workstation: Sidebar + Main Content View */}
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main id="main-content" className="flex-1 min-w-0 overflow-hidden relative bg-transparent">
          {/* Ambient Studio Lighting Orbs */}
          <div className="ambient-glow-top" />
          <div className="ambient-glow-bottom" />

          <div className="w-full h-full relative z-10">
            {activeTab === "download" && (
              <DownloadPage onGoToQueue={() => setActiveTab("queue")} />
            )}
            {activeTab === "queue" && (
              <DownloadsPage onNewDownload={() => setActiveTab("download")} />
            )}
            {activeTab === "history" && <HistoryPage />}
            {activeTab === "search" && (
              <SearchPage onGoToQueue={() => setActiveTab("queue")} />
            )}
            {activeTab === "settings" && <SettingsPage />}
          </div>
        </main>
      </div>

      {/* 4. Bottom YDS MiniPlayer & Media Telemetry Bar */}
      <MiniPlayer />
    </div>
  );
}

export default App;
