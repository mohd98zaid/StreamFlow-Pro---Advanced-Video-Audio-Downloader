import React, { useState, useEffect } from "react";
import { Titlebar } from "./components/layout/Titlebar";
import { Sidebar, NavTab } from "./components/layout/Sidebar";
import { StatusFooter } from "./components/layout/StatusFooter";
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
    loadConfig();
    loadPresets();
    fetchQueue();

    return () => {
      wsClient.disconnect();
    };
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-background text-foreground overflow-hidden font-sans select-none">
      {/* 1. Window Titlebar with controls */}
      <Titlebar />

      {/* 2. Middle: Sidebar + Main Content View */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 overflow-hidden relative bg-background/50">
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
        </main>
      </div>

      {/* 3. Bottom Status Footer */}
      <StatusFooter />
    </div>
  );
}

export default App;
