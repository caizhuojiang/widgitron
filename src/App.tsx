import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Settings,
  Cpu,
  Calendar,
  X,
  Minus,
  Square,
  ChevronRight,
  Activity,
  Server,
  Lock,
  Unlock,
  Pin,
  PinOff,
  Trophy,
  Plus,
  Copy,
  Check,
  Sun,
  Moon,
  ExternalLink,
  Trash2
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { APP_VERSION } from "./constants";
import { invoke } from "@tauri-apps/api/core";
import { listen, emit } from "@tauri-apps/api/event";
import { enable, disable, isEnabled } from "@tauri-apps/plugin-autostart";
import { WebviewWindow, getAllWebviewWindows } from "@tauri-apps/api/webviewWindow";
 
interface ColorConfig {
  name: string;
  value: string;
  opacity?: number;
}
 
interface WidgetTheme {
  id: string;
  name: string;
  is_default: boolean;
  bg_color: string;
  bg_opacity: number;
  text_colors: ColorConfig[];
  primary_colors: ColorConfig[];
}
 
interface WidgetThemeConfig {
  themes: WidgetTheme[];
  assignments: Record<string, string>;
}
 
const hexToRgba = (hex: string, opacity: number) => {
  let r = 0, g = 0, b = 0;
  const h = hex.replace("#", "");
  if (h.length === 3) {
    r = parseInt(h[0] + h[0], 16);
    g = parseInt(h[1] + h[1], 16);
    b = parseInt(h[2] + h[2], 16);
  } else if (h.length === 6) {
    r = parseInt(h.substring(0, 2), 16);
    g = parseInt(h.substring(2, 4), 16);
    b = parseInt(h.substring(4, 6), 16);
  }
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
};

// App Component
const appWindow = getCurrentWindow();

function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [isMaximized, setIsMaximized] = useState(false);
  const [windowLabel, setWindowLabel] = useState("");
  const [isLocked, setIsLocked] = useState(true);
  const [isPinned, setIsPinned] = useState(false);
  const [gpuData, setGpuData] = useState<any[]>([]);
  const [deadlines, setDeadlines] = useState<any[]>([]);
  const [gpuConfig, setGpuConfig] = useState<any>({ servers: [] });
  const [paperConfig, setPaperConfig] = useState<any>({});
  const [arxivConfig, setArxivConfig] = useState<any>({});
  const [arxivPapers, setArxivPapers] = useState<any[]>([]);
  const [arxivSavedPapers, setArxivSavedPapers] = useState<any[]>([]);
  const [arxivDiscardedPapers, setArxivDiscardedPapers] = useState<any[]>([]);
  const [arxivView, setArxivView] = useState<"new" | "saved" | "discarded">("new");
  const [appConfig, setAppConfig] = useState<any>(() => {
    try {
      const saved = localStorage.getItem("widgitron-theme") || "dark";
      return { theme: saved };
    } catch (e) {
      return { theme: "dark" };
    }
  });
  const [isAutostart, setIsAutostart] = useState(false);
  const [activeWidgets, setActiveWidgets] = useState<string[]>([]);
  const [themeConfig, setThemeConfig] = useState<WidgetThemeConfig>({ themes: [], assignments: {} });
  const [currentTheme, setCurrentTheme] = useState<WidgetTheme | null>(null);

  useEffect(() => {
    const win = appWindow;
    setWindowLabel(win.label);

    let interval: any;
    let unlisteners: (() => void)[] = [];

    const init = async () => {
      try {
        console.log("Initializing window:", win.label);
        const gc = await invoke("get_gpu_config");
        const pc = await invoke("get_paper_config");
        const arc = await invoke("get_arxiv_config");
        const ac = await invoke("get_app_config") as any;
        const initialDeadlines: any = await invoke("get_deadlines");
        const initialGpuData: any = await invoke("get_gpu_data");
        const initialArxiv: any = await invoke("get_arxiv_papers");
        const tc: WidgetThemeConfig = await invoke("get_theme_config");

        setGpuConfig(gc);
        setPaperConfig(pc);
        setArxivConfig(arc);
        setAppConfig(ac);
        if (ac.theme) localStorage.setItem("widgitron-theme", ac.theme);
        setDeadlines(initialDeadlines);
        setGpuData(initialGpuData);
        setArxivPapers(initialArxiv);
        setIsAutostart(await isEnabled());
        setThemeConfig(tc);

        const label = win.label;
        if (label.startsWith("widget-")) {
          const tid = tc.assignments?.[label];
          let defaultId = "theme-gpu-default";
          if (label.includes("deadlines")) defaultId = "theme-deadline-default";
          if (label.includes("arxiv")) defaultId = "theme-arxiv-default";
          
          const theme = tc.themes.find(t => t.id === tid) || tc.themes.find(t => t.id === defaultId);
          setCurrentTheme(theme || null);

          let pinned = false;
          if (ac.always_on_top?.[label] !== undefined) {
            pinned = ac.always_on_top[label];
          }
          
          setIsPinned(pinned);
          
          // Wait a bit for the window to be ready before Win32 manipulations
          setTimeout(async () => {
            if (pinned) {
              await win.setAlwaysOnTop(true);
              await invoke("set_desktop_mode", { label, enabled: false });
            } else {
              await win.setAlwaysOnTop(false);
              await invoke("set_desktop_mode", { label, enabled: true });
            }
          }, 500);
        }

        const windows = await getAllWebviewWindows();
        const initialActive = [];
        for (const w of windows) {
          if (w.label.startsWith("widget-") && await w.isVisible()) {
            initialActive.push(w.label);
          }
        }
        setActiveWidgets(initialActive);

        interval = setInterval(async () => {
          const wins = await getAllWebviewWindows();
          const active = [];
          for (const w of wins) {
            if (w.label.startsWith("widget-") && await w.isVisible()) {
              active.push(w.label);
            }
          }
          setActiveWidgets(active);
        }, 1000);

        const u1 = await win.onResized(async () => {
          const maximized = await win.isMaximized();
          setIsMaximized(maximized);
        });
        unlisteners.push(() => u1());

        const u2 = await listen<any>("gpu_update", (event) => {
          const item = event.payload;
          setGpuData(prev => {
            const index = prev.findIndex(s => s.host === item.host);
            if (index === -1) return [...prev, item];
            const next = [...prev];
            next[index] = item;
            return next;
          });
        });
        unlisteners.push(() => u2());

        const u3 = await listen<any[]>("paper_update", (event) => {
          setDeadlines(event.payload);
        });
        unlisteners.push(() => u3());

        const u4 = await listen("gpu_clear", () => {
          setGpuData([]);
        });
        unlisteners.push(() => u4());

        const u5 = await listen("theme_update", (event: any) => {
          const config = event.payload as WidgetThemeConfig;
          setThemeConfig(config);
          if (label.startsWith("widget-")) {
            const tid = config.assignments?.[label];
            const defaultId = label.includes("gpu") ? "theme-gpu-default" : "theme-deadline-default";
            const theme = config.themes.find(t => t.id === tid) || config.themes.find(t => t.id === defaultId);
            setCurrentTheme(theme || null);
          }
        });
        unlisteners.push(() => u5());
        const u6 = await listen<any[]>("arxiv_update", (event) => setArxivPapers(event.payload));
        unlisteners.push(() => u6());

        const u8 = await listen("arxiv_saved_update", async () => {
          setArxivSavedPapers(await invoke<any[]>("get_arxiv_saved_papers"));
        });
        unlisteners.push(() => u8());

        const u9 = await listen("arxiv_discarded_update", async () => {
          setArxivDiscardedPapers(await invoke<any[]>("get_arxiv_discarded_papers"));
        });
        unlisteners.push(() => u9());

        // Initial fetch
        invoke<any>("get_arxiv_config").then(setArxivConfig).catch(console.error);
        invoke<any[]>("get_arxiv_saved_papers").then(setArxivSavedPapers).catch(console.error);
        invoke<any[]>("get_arxiv_discarded_papers").then(setArxivDiscardedPapers).catch(console.error);
        invoke<any[]>("get_arxiv_papers").then(setArxivPapers).catch(console.error);

      } catch (e) { console.error("Init failed", e); }
    };

    if (win.label === "tray-menu") {
      win.onFocusChanged((event) => {
        if (!event.payload) win.hide();
      }).then(u => unlisteners.push(() => u()));
      init();
    } else {
      init();
    }

    return () => {
      if (interval) clearInterval(interval);
      unlisteners.forEach(f => f());
    };
  }, []);

  const saveGpuConfig = async (newConfig: any) => {
    try {
      await invoke("save_gpu_config", { config: newConfig });
      setGpuConfig(newConfig);
    } catch (e) { console.error("Save failed", e); }
  };

  const savePaperConfig = async (newConfig: any) => {
    try {
      await invoke("save_paper_config", { config: newConfig });
      setPaperConfig(newConfig);
      await emit("paper_config_update", newConfig);
    } catch (e) { console.error("Save failed", e); }
  };

  const togglePinConference = async (title: string) => {
    const nextPinned = (paperConfig.pinned_titles || []).includes(title)
      ? paperConfig.pinned_titles.filter((t: string) => t !== title)
      : [...(paperConfig.pinned_titles || []), title];
    const nextConfig = { ...paperConfig, pinned_titles: nextPinned };
    await savePaperConfig(nextConfig);
  };

  const onSaveApp = async (config: any) => {
    setAppConfig(config);
    if (config.theme) localStorage.setItem("widgitron-theme", config.theme);
    await invoke("save_app_config", { config });
  };

  const saveArxivConfig = async (newConfig: any) => {
    try {
      await invoke("save_arxiv_config", { config: newConfig });
      setArxivConfig(newConfig);
      await emit("arxiv_config_update", newConfig);
    } catch (e) { console.error("Save Arxiv config failed", e); }
  };
 
  const onSaveThemes = async (config: WidgetThemeConfig) => {
    setThemeConfig(config);
    await invoke("save_theme_config", { config });
    // Emit event to widgets to sync themes
    await emit("theme_update", config);
  };

  const toggleMaximize = async () => {
    try {
      await appWindow.toggleMaximize();
    } catch (e) { console.error(e); }
  };

  const handleToggleWidget = async (id: string, title: string) => {
    try {
      // Optimistic UI update for instant feedback
      setActiveWidgets(prev => 
        prev.includes(id) ? prev.filter(w => w !== id) : [...prev, id]
      );
      await invoke("toggle_widget", { id, title });
    } catch (e) { 
      console.error("Toggle failed", e); 
    }
  };

  const toggleLock = async () => {
    const nextLocked = !isLocked;
    setIsLocked(nextLocked);
    
    // When unlocking, we MUST exit desktop mode to allow movement
    // When locking, if we are NOT pinned, we re-enter desktop mode
    if (windowLabel.startsWith("widget-")) {
      if (!nextLocked) {
        // Unlocking: Exit desktop mode
        await invoke("set_desktop_mode", { label: windowLabel, enabled: false });
      } else {
        // Locking: If not pinned, re-embed
        if (!isPinned) {
          await invoke("set_desktop_mode", { label: windowLabel, enabled: true });
        }
      }
    }
  };

  const togglePin = async (labelToToggle?: string) => {
    try {
      const targetLabel = labelToToggle || windowLabel;
      const currentVal = targetLabel === windowLabel ? isPinned : (appConfig.always_on_top?.[targetLabel] || false);
      const next = !currentVal;
      
      const targetWin = targetLabel === windowLabel ? appWindow : await WebviewWindow.getByLabel(targetLabel);
      
      if (next) {
        // Turning ON Always on Top: Disable Desktop Mode FIRST, then set top
        await invoke("set_desktop_mode", { label: targetLabel, enabled: false });
        await targetWin?.setAlwaysOnTop(true);
      } else {
        // Turning OFF Always on Top: Enable Desktop Mode (Embedded)
        await targetWin?.setAlwaysOnTop(false);
        await invoke("set_desktop_mode", { label: targetLabel, enabled: true });
      }

      if (targetLabel === windowLabel) {
        setIsPinned(next);
      }
      
      const nextStates = { ...(appConfig.always_on_top || {}), [targetLabel]: next };
      await onSaveApp({ ...appConfig, always_on_top: nextStates });
    } catch (e) { console.error(e); }
  };

  const handleClose = async () => {
    console.log("Close clicked, label:", windowLabel);
    try {
      const win = getCurrentWindow();
      if (windowLabel === "main" || windowLabel.startsWith("widget-")) {
        await win.hide();
        // Notify main window if this was a widget (though events are better)
      } else {
        await win.close();
      }
    } catch (e) { console.error("Close failed", e); }
  };

  const startDrag = async (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (e.button === 0 && !target.closest('[data-no-drag="true"]')) {
      try {
        console.log("Start dragging");
        await getCurrentWindow().startDragging();
      } catch (e) { console.error("Drag failed", e); }
    }
  };

  // --- CUSTOM TRAY MENU VIEW ---
  if (windowLabel === "tray-menu") {
    return (
      <div className="h-screen w-screen flex flex-col bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xl p-1 select-none">
        <button 
          onClick={() => invoke("show_main")} 
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md hover:bg-slate-100 text-slate-700 transition-colors group"
        >
          <LayoutDashboard size={14} className="text-slate-500 group-hover:text-blue-600 transition-colors" />
          <span className="text-[11px] font-bold">Dashboard</span>
        </button>
        <button 
          onClick={() => invoke("exit_app")} 
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md hover:bg-red-50 text-slate-700 hover:text-red-600 transition-colors group"
        >
          <X size={14} className="text-slate-500 group-hover:text-red-500 transition-colors" />
          <span className="text-[11px] font-bold">Exit</span>
        </button>
      </div>
    );
  }

  // --- DESKTOP WIDGET VIEW ---
  if (windowLabel.startsWith("widget-")) {
    const isGpu = windowLabel.includes("gpu");
    const isDeadline = windowLabel.includes("deadlines");

    return (
      <div className="absolute inset-0 flex flex-col group select-none overflow-hidden bg-transparent p-0">
        {/* Floating Controls (Now inside the window, but top-right) */}
        <div className="absolute top-1 right-1 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-50">
          <button data-no-drag="true" onClick={toggleLock} className="w-7 h-7 flex items-center justify-center rounded-md bg-black/60 border border-white/10 text-white/70 hover:text-white transition-all shadow-lg backdrop-blur-md">
            {isLocked ? <Lock size={12} /> : <Unlock size={12} />}
          </button>
          <button data-no-drag="true" onClick={() => togglePin()} className={`w-7 h-7 flex items-center justify-center rounded-md bg-black/60 border border-white/10 ${isPinned ? "text-blue-400" : "text-white/70"} hover:text-white transition-all shadow-lg backdrop-blur-md`} title={isPinned ? "Unpin (Embed in Desktop)" : "Pin to top"}>
            {isPinned ? <Pin size={12} /> : <PinOff size={12} />}
          </button>
          <button data-no-drag="true" onClick={handleClose} className="w-7 h-7 flex items-center justify-center rounded-md bg-red-500/30 border border-red-500/20 text-red-400 hover:bg-red-500 hover:text-white transition-all shadow-lg backdrop-blur-md">
            <X size={12} />
          </button>
        </div>

        {/* The Glass Card (Fills the window, buttons overlap content) */}
        <div
          className={`flex-1 p-5 flex flex-col gap-4 relative overflow-hidden rounded-xl z-10 ${isLocked ? "" : "shadow-2xl shadow-black/80"}`}
          style={windowLabel.startsWith("widget-") && currentTheme ? {
            backgroundColor: hexToRgba(currentTheme.bg_color, currentTheme.bg_opacity),
            color: currentTheme.text_colors?.find(c => c.name === "Main Text") ? hexToRgba(currentTheme.text_colors.find(c => c.name === "Main Text")!.value, currentTheme.text_colors.find(c => c.name === "Main Text")!.opacity ?? 1.0) : "#ffffff",
            border: `1px solid ${hexToRgba(currentTheme.text_colors?.find(c => c.name === "Main Text")?.value || "#ffffff", 0.1)}`
          } : {}}
          onMouseDown={!isLocked ? startDrag : undefined}
          data-tauri-drag-region={!isLocked ? "true" : "false"}
        >
          {isGpu && <GPUWidgetContent />}
          {isDeadline && <DeadlineWidgetContent />}
          {windowLabel.includes("arxiv") && <ArxivWidgetContent />}
        </div>
      </div>
    );
  }

  // --- MAIN CONTROL PANEL VIEW ---
  return (
    <div className={`absolute inset-0 flex overflow-hidden ${appConfig.theme === "light" ? "light-theme" : ""} glass ${isMaximized ? "rounded-none" : "rounded-xl dashboard-accent-border"}`}>
      {/* Sidebar */}
      <aside className={`w-64 border-r border-white/5 flex flex-col bg-[var(--sidebar-bg)] z-20 select-none`} onMouseDown={startDrag}>
        <div className="p-6 flex items-center gap-2.5 cursor-default">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/40 overflow-hidden pointer-events-none">
            <img src="/logo.png" alt="Widgitron" className="w-full h-full object-cover" />
          </div>
          <div className="pointer-events-none flex flex-col justify-center space-y-1.5">
            <h1 className="font-bold text-base tracking-tight leading-none">Widgitron</h1>
            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold leading-none">{APP_VERSION}</span>
          </div>
        </div>

        <nav className="flex-1 px-4 pt-2 pb-6 space-y-1.5 overflow-y-auto" data-no-drag="true">
          <SidebarLink icon={<LayoutDashboard size={20} />} label="Overview" active={activeTab === "dashboard"} onClick={() => setActiveTab("dashboard")} theme={appConfig.theme} />
          <SidebarLink icon={<Cpu size={20} />} label="GPU Cluster" active={activeTab === "gpu"} onClick={() => setActiveTab("gpu")} theme={appConfig.theme} />
          <SidebarLink icon={<Calendar size={20} />} label="Deadlines" active={activeTab === "deadlines"} onClick={() => setActiveTab("deadlines")} theme={appConfig.theme} />
          <SidebarLink icon={<Activity size={20} />} label="Arxiv Radar" active={activeTab === "arxiv"} onClick={() => setActiveTab("arxiv")} theme={appConfig.theme} />
          <div className={`my-4 border-t ${appConfig.theme === "light" ? "border-slate-200" : "border-white/10"}`} />
          <SidebarLink icon={<Settings size={20} />} label="Settings" active={activeTab === "settings"} onClick={() => setActiveTab("settings")} theme={appConfig.theme} />
        </nav>

      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 z-20">
        <header className={`h-14 flex items-center justify-between px-6 border-b border-[var(--dashboard-border)] relative bg-[var(--header-bg)] z-50 select-none pointer-events-auto`} data-tauri-drag-region="true">
          <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 pointer-events-none">{activeTab}</div>
          <div className="flex items-center gap-0.5 z-[60] pointer-events-auto">
            <WindowButton icon={<Minus size={16} />} onClick={() => appWindow.minimize()} theme={appConfig.theme} />
            <WindowButton icon={isMaximized ? <Copy size={12} /> : <Square size={14} />} onClick={toggleMaximize} theme={appConfig.theme} />
            <WindowButton icon={<X size={18} />} onClick={handleClose} hoverColor="hover:bg-red-500" theme={appConfig.theme} />
          </div>
        </header>

        <div className={`flex-1 overflow-y-auto p-8 custom-scrollbar relative z-0 ${appConfig.theme === "light" ? "bg-transparent" : "bg-black/5"}`} data-no-drag="true">
          <AnimatePresence mode="wait">
            {activeTab === "dashboard" && (
              <motion.div key="dashboard" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <StatCard label="Active Monitors" value={gpuData.filter(s => s.is_online).length.toString()} icon={<Server className="text-blue-400" />} theme={appConfig.theme} />
                <StatCard label="Total GPUs" value={gpuData.reduce((acc, s) => acc + s.gpu_list.length, 0).toString()} icon={<Cpu className="text-purple-400" />} theme={appConfig.theme} />
                <StatCard label="Active Deadlines" value={deadlines.length.toString()} icon={<Calendar className="text-emerald-400" />} theme={appConfig.theme} />
                <StatCard label="Arxiv Radar" value={arxivPapers.length.toString()} icon={<Activity className="text-pink-400" />} theme={appConfig.theme} />

                <div className="col-span-full mt-4">
                  <h2 className={`text-xl font-bold tracking-tight mb-6 ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Quick Launch Widgets</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {appConfig.gpu_enabled !== false && (
                      <WidgetPreviewCard
                        title="GPU Monitor Widget"
                        status={activeWidgets.includes("widget-gpu-default") ? "Active" : "Ready"}
                        detail="Floating desktop monitoring for GPU clusters"
                        trend={activeWidgets.includes("widget-gpu-default") ? "Hide Widget" : "Show Widget"}
                        color="blue"
                        theme={appConfig.theme}
                        onLaunch={() => handleToggleWidget("widget-gpu-default", "GPU Monitor")}
                      />
                    )}
                    {appConfig.deadline_enabled !== false && (
                      <WidgetPreviewCard
                        title="Paper Deadline Widget"
                        status={activeWidgets.includes("widget-deadlines-default") ? "Active" : "Ready"}
                        detail="Track conference deadlines on your desktop"
                        trend={activeWidgets.includes("widget-deadlines-default") ? "Hide Widget" : "Show Widget"}
                        color="purple"
                        theme={appConfig.theme}
                        onLaunch={() => handleToggleWidget("widget-deadlines-default", "Deadlines")}
                      />
                    )}
                    {appConfig.arxiv_enabled !== false && (
                      <WidgetPreviewCard
                        title="Arxiv Radar Widget"
                        status={activeWidgets.includes("widget-arxiv-default") ? "Active" : "Ready"}
                        detail="Swipe to discover latest research papers"
                        trend={activeWidgets.includes("widget-arxiv-default") ? "Hide Widget" : "Show Widget"}
                        color="pink"
                        theme={appConfig.theme}
                        onLaunch={() => handleToggleWidget("widget-arxiv-default", "Arxiv Radar")}
                      />
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "gpu" && (
              <motion.div key="gpu" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="flex items-center justify-between mb-8">
                  <h2 className={`text-2xl font-bold tracking-tight ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>GPU Cluster Status</h2>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{appConfig.gpu_enabled !== false ? "Service Enabled" : "Service Disabled"}</span>
                    <MasterSwitch 
                      enabled={appConfig.gpu_enabled !== false} 
                      onToggle={async (val) => {
                        try {
                          const next = { ...appConfig, gpu_enabled: val };
                          setAppConfig(next);
                          await invoke("save_app_config", { config: next });
                          if (!val) {
                            setGpuData([]);
                            await invoke("close_widget", { id: "widget-gpu-default" });
                          } else {
                            await invoke("create_widget", { id: "widget-gpu-default", title: "GPU Monitor" });
                          }
                        } catch (e) {
                          console.error("GPU Master Switch failed", e);
                        }
                      }} 
                    />
                  </div>
                </div>
                <div className="space-y-6">
                  {gpuData.length === 0 ? (
                    <div className="p-12 text-center bg-black/5 rounded-3xl border border-dashed border-white/10 text-slate-500 font-bold uppercase tracking-widest text-xs">No active data. Configure servers in Settings.</div>
                  ) : gpuData.map((server, idx) => (
                    <div key={idx} className="glass-card p-6">
                      <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${server.is_online ? "bg-emerald-500 shadow-[0_0_10px_#10b981]" : "bg-red-500"}`} />
                          <span className={`text-lg font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{server.host}</span>
                        </div>
                        <span className="text-xs font-black text-slate-500 uppercase tracking-widest">{server.gpu_list.length} GPUs Detected</span>
                      </div>
                      <div className="space-y-8">
                        {(() => {
                          const groups: Record<string, any[]> = {};
                          server.gpu_list.forEach((gpu: any) => {
                            const gid = gpu.job_id || "SYSTEM";
                            if (!groups[gid]) groups[gid] = [];
                            groups[gid].push(gpu);
                          });

                          return Object.entries(groups).map(([jobId, gpus]) => (
                            <div key={jobId} className="space-y-4">
                              {jobId !== "SYSTEM" && (
                                <div className="flex items-center gap-2 text-xs font-black text-blue-400 uppercase tracking-[0.2em] mb-2 px-1">
                                  <Activity size={14} /> Job: {jobId}
                                  <CopyButton text={jobId} />
                                </div>
                              )}
                              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                {gpus.map((gpu, gidx) => (
                                  <div key={gidx} className={`p-5 rounded-xl border ${appConfig.theme === "light" ? "bg-slate-50 border-slate-100" : "bg-black/20 border-white/5"} relative group transition-all hover:bg-black/5`}>
                                    <div className="flex items-center justify-between mb-4">
                                      <span className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{gpu.name}</span>
                                      <span className={`text-[10px] font-black ${gpu.util > 80 ? "text-red-500" : "text-blue-400"} uppercase tracking-widest`}>{gpu.util}%</span>
                                    </div>

                                    <div className="space-y-4">
                                      <div>
                                        <div className="flex justify-between text-[10px] text-slate-500 font-bold uppercase tracking-tighter mb-1">
                                          <span>Load</span>
                                          <span>{gpu.util}%</span>
                                        </div>
                                        <div className={`w-full ${appConfig.theme === "light" ? "bg-slate-200" : "bg-white/5"} h-1.5 rounded-full overflow-hidden mt-1`}>
                                          <motion.div initial={{ width: 0 }} animate={{ width: `${gpu.util}%` }} className={`h-full rounded-full ${gpu.util > 80 ? "bg-red-500" : "bg-blue-500"}`} />
                                        </div>
                                      </div>

                                      <div className="grid grid-cols-2 gap-4">
                                        <div className={`p-2 rounded-lg ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
                                          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Temp</div>
                                          <div className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{gpu.temp}°C</div>
                                        </div>
                                        <div className={`p-2 rounded-lg ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
                                          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Memory</div>
                                          <div className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{gpu.mem_used}/{gpu.mem_total}MB</div>
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ));
                        })()}
                      </div>
                      {server.error && <p className="mt-4 text-[10px] text-red-400/60 italic font-medium break-all">{server.error}</p>}
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {activeTab === "deadlines" && (
              <motion.div key="deadlines" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="flex items-center justify-between mb-8">
                  <h2 className={`text-2xl font-bold tracking-tight ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Upcoming Conferences</h2>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{appConfig.deadline_enabled !== false ? "Service Enabled" : "Service Disabled"}</span>
                    <MasterSwitch 
                      enabled={appConfig.deadline_enabled !== false} 
                      onToggle={async (val) => {
                        try {
                          const next = { ...appConfig, deadline_enabled: val };
                          setAppConfig(next);
                          await invoke("save_app_config", { config: next });
                          if (!val) {
                            setDeadlines([]);
                            await invoke("close_widget", { id: "widget-deadlines-default" });
                          } else {
                            await invoke("create_widget", { id: "widget-deadlines-default", title: "Deadlines" });
                          }
                        } catch (e) {
                          console.error("Deadline Master Switch failed", e);
                        }
                      }} 
                    />
                  </div>
                </div>
                <div className="space-y-4">
                  {deadlines.length === 0 ? (
                    <div className="p-12 text-center bg-black/5 rounded-3xl border border-dashed border-white/10 text-slate-500 font-bold uppercase tracking-widest text-xs">No deadlines match your current filters.</div>
                  ) : deadlines.map((dl, idx) => {
                    const isPinned = (paperConfig.pinned_titles || []).includes(dl.title);
                    return (
                      <div key={idx} className={`border border-[var(--dashboard-border)] rounded-2xl p-6 flex items-center justify-between hover:bg-black/5 transition-all group ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
                        <div className="flex items-center gap-6">
                          <div className={`w-16 h-16 rounded-2xl flex flex-col items-center justify-center relative ${appConfig.theme === "light" ? "bg-purple-100 text-purple-600" : "bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/20 text-purple-400"}`}>
                            <span className="text-[10px] font-black uppercase tracking-tighter opacity-60">{dl.sub}</span>
                            <Trophy size={20} className={appConfig.theme === "light" ? "text-purple-600" : "text-purple-400"} />
                            <button
                              onClick={() => togglePinConference(dl.title)}
                              className={`absolute -top-2 -right-2 p-1.5 rounded-full shadow-lg transition-all ${isPinned ? "bg-amber-500 text-white scale-110" : "bg-slate-800 text-slate-500 opacity-0 group-hover:opacity-100"}`}
                            >
                              <Pin size={10} className={isPinned ? "fill-current" : ""} />
                            </button>
                          </div>
                          <div>
                            <h3 className={`text-lg font-bold group-hover:text-purple-400 transition-colors ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{dl.title} {dl.year}</h3>
                            <div className="flex items-center gap-3 mt-1">
                              <p className="text-xs text-slate-500 font-medium">{dl.place}</p>
                              <div className="w-1 h-1 rounded-full bg-slate-700" />
                              <div className="text-[10px] font-mono font-bold text-purple-500/80">
                                <DeadlineCountdown date={dl.deadline_utc} />
                              </div>
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-xl font-black ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{new Date(dl.deadline_utc).toLocaleDateString()}</div>
                          <div className="text-xs font-bold text-slate-500 uppercase tracking-widest">Deadline (UTC)</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {activeTab === "arxiv" && (
              <motion.div key="arxiv" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-6">
                    <h2 className={`text-2xl font-bold tracking-tight ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Arxiv Radar</h2>
                    <div className={`flex items-center p-1 rounded-xl ${appConfig.theme === "light" ? "bg-slate-100" : "bg-white/5"}`}>
                      <button 
                        onClick={() => setArxivView("new")}
                        className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${arxivView === "new" ? (appConfig.theme === "light" ? "bg-white text-slate-900 shadow-sm" : "bg-white/10 text-white shadow-lg") : "text-slate-500 hover:text-slate-400"}`}
                      >Latest ({arxivPapers.length})</button>
                      <button 
                        onClick={() => setArxivView("saved")}
                        className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${arxivView === "saved" ? (appConfig.theme === "light" ? "bg-white text-slate-900 shadow-sm" : "bg-white/10 text-white shadow-lg") : "text-slate-500 hover:text-slate-400"}`}
                      >Saved ({arxivSavedPapers.length})</button>
                      <button 
                        onClick={() => setArxivView("discarded")}
                        className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${arxivView === "discarded" ? (appConfig.theme === "light" ? "bg-white text-slate-900 shadow-sm" : "bg-white/10 text-white shadow-lg") : "text-slate-500 hover:text-slate-400"}`}
                      >Discarded ({arxivDiscardedPapers.length})</button>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{appConfig.arxiv_enabled !== false ? "Service Enabled" : "Service Disabled"}</span>
                    <MasterSwitch 
                      enabled={appConfig.arxiv_enabled !== false} 
                      onToggle={async (val) => {
                        try {
                          const next = { ...appConfig, arxiv_enabled: val };
                          setAppConfig(next);
                          await invoke("save_app_config", { config: next });
                          if (!val) {
                            setArxivPapers([]);
                            await invoke("close_widget", { id: "widget-arxiv-default" });
                          } else {
                            await invoke("create_widget", { id: "widget-arxiv-default", title: "Arxiv Radar" });
                          }
                        } catch (e) {
                          console.error("Arxiv Master Switch failed", e);
                        }
                      }} 
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {(arxivView === "new" ? arxivPapers : (arxivView === "saved" ? arxivSavedPapers : arxivDiscardedPapers)).length === 0 ? (
                    <div className="col-span-full p-12 text-center bg-black/5 rounded-3xl border border-dashed border-white/10 text-slate-500 font-bold uppercase tracking-widest text-xs">
                      {arxivView === "new" ? "No new papers. Adjust keywords in Settings or wait for update." : 
                       (arxivView === "saved" ? "No saved papers yet. Swipe right on the widget to save!" : "No discarded papers. Swipe left on the widget to discard.")}
                    </div>
                  ) : (arxivView === "new" ? arxivPapers : (arxivView === "saved" ? arxivSavedPapers : arxivDiscardedPapers)).map((paper, idx) => (
                    <div key={idx} className={`border border-[var(--dashboard-border)] rounded-2xl p-6 flex flex-col gap-4 hover:bg-black/5 transition-all group ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
                      <div className="flex-1">
                        <h3 className={`text-sm font-bold line-clamp-2 mb-2 ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{paper.title}</h3>
                        <p className="text-[10px] text-slate-500 line-clamp-6 leading-relaxed">{paper.summary}</p>
                      </div>
                      <div className="flex items-center justify-between mt-2 pt-4 border-t border-white/5">
                        <div className="flex flex-wrap gap-1">
                          <span className="text-[9px] font-medium text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-full">
                            {paper.authors.length > 0 ? (
                              <>{paper.authors[0]}{paper.authors.length > 1 ? " et al." : ""}</>
                            ) : "Unknown Author"}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">

                          {arxivView === "saved" && (
                            <button 
                              onClick={() => invoke("remove_arxiv_saved_paper", { id: paper.id })}
                              className="p-2 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white transition-all"
                              title="Remove from saved"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                          {arxivView === "discarded" && (
                            <button 
                              onClick={() => invoke("remove_arxiv_discarded_paper", { id: paper.id })}
                              className="p-2 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white transition-all"
                              title="Delete permanently"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                          <button 
                            onClick={() => invoke("open_link", { url: paper.link })}
                            className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white transition-colors"
                          >
                            <ExternalLink size={14} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {activeTab === "settings" && (
              <SettingsPanel
                gpuConfig={gpuConfig}
                paperConfig={paperConfig}
                arxivConfig={arxivConfig}
                appConfig={appConfig}
                themeConfig={themeConfig}
                onSaveGpu={saveGpuConfig}
                onSavePaper={savePaperConfig}
                onSaveArxiv={saveArxivConfig}
                onSaveApp={onSaveApp}
                onSaveThemes={onSaveThemes}
                isAutostart={isAutostart}
                onToggleAutostart={async () => {
                  if (isAutostart) await disable();
                  else await enable();
                  setIsAutostart(await isEnabled());
                }}
                activeWidgets={activeWidgets}
              />
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

// --- SUB-COMPONENTS ---

function DeadlineCountdown({ date }: { date: string }) {
  const [timeLeft, setTimeLeft] = useState<string>("");

  useEffect(() => {
    const calculate = () => {
      const target = new Date(date).getTime();
      const now = new Date().getTime();
      const diff = target - now;

      if (diff <= 0) {
        setTimeLeft("EXPIRED");
        return;
      }

      const d = Math.floor(diff / (1000 * 60 * 60 * 24));
      const h = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const s = Math.floor((diff % (1000 * 60)) / 1000);

      setTimeLeft(`${d}d ${h}h ${m}m ${s}s`);
    };

    calculate();
    const interval = setInterval(calculate, 1000);
    return () => clearInterval(interval);
  }, [date]);

  return <span>{timeLeft}</span>;
}

function GPUWidgetContent() {
  const [serverData, setServerData] = useState<any[]>([]);
  const [currentTheme, setCurrentTheme] = useState<WidgetTheme | null>(null);
  const win = getCurrentWindow();

  useEffect(() => {
    let unlisteners: (() => void)[] = [];

    const load = async () => {
      try {
        setServerData(await invoke("get_gpu_data"));
        const config: WidgetThemeConfig = await invoke("get_theme_config");
        const themeId = config.assignments?.[win.label];
        const theme = config.themes.find(t => t.id === themeId) || config.themes.find(t => t.id === "theme-gpu-default");
        setCurrentTheme(theme || null);

        const u1 = await listen<any>("gpu_update", (event) => {
          const item = event.payload;
          setServerData(prev => {
            const index = prev.findIndex(s => s.host === item.host);
            if (index === -1) return [...prev, item];
            const next = [...prev];
            next[index] = item;
            return next;
          });
        });
        unlisteners.push(() => u1());

        const u2 = await listen("theme_update", (event: any) => {
          const config = event.payload as WidgetThemeConfig;
          const themeId = config.assignments?.[win.label];
          const theme = config.themes.find(t => t.id === themeId) || config.themes.find(t => t.id === "theme-gpu-default");
          setCurrentTheme(theme || null);
        });
        unlisteners.push(() => u2());

        const u3 = await listen("gpu_clear", () => {
          setServerData([]);
        });
        unlisteners.push(() => u3());
      } catch (e) { console.error("Widget init failed", e); }
    };
    
    load();

    return () => {
      unlisteners.forEach(f => f());
    };
  }, []);

  if (!currentTheme) return null;

  const getC = (name: string, fallback: string) => {
    const c = currentTheme.primary_colors.find(p => p.name === name);
    return c ? hexToRgba(c.value, c.opacity ?? 1.0) : fallback;
  };
  const getT = (name: string, fallback: string) => {
    const c = currentTheme.text_colors?.find(p => p.name === name);
    return c ? hexToRgba(c.value, c.opacity ?? 1.0) : fallback;
  };

  const accent = getC("Accent", "#3b82f6");
  const success = getC("Success", "#10b981");
  const warning = getC("Warning", "#f59e0b");
  const danger = getC("Danger", "#ef4444");
  const mainText = getT("Main Text", "#ffffff");
  const subText = getT("Sub Text", "#94a3b8");

  return (
    <div className="h-full flex flex-col" style={{ color: mainText }}>
      <div className="flex items-center gap-2 mb-4">
        <Cpu size={16} style={{ color: accent }} />
        <span className="text-xs font-black uppercase tracking-widest" style={{ color: subText }}>GPU Monitor</span>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-6">
        {serverData.length > 0 ? serverData.map((server: any, idx: number) => {
          const groups: Record<string, any[]> = {};
          server.gpu_list.forEach((gpu: any) => {
            const gid = gpu.job_id || "SYSTEM";
            if (!groups[gid]) groups[gid] = [];
            groups[gid].push(gpu);
          });

          return (
            <div key={idx} className="space-y-4">
              <div className="flex items-center justify-between border-l-2 border-white/10 pl-2">
                <div className="flex flex-col items-start">
                  <span className="text-[10px] font-black uppercase tracking-tighter" style={{ color: mainText }}>{server.host}</span>
                  {server.last_update && <span className="text-[7px] opacity-40 font-mono">Last: {server.last_update}</span>}
                </div>
                {server.is_online ? (
                  <span className="text-[7px] font-black uppercase" style={{ color: success }}>Online</span>
                ) : (
                  <span className="text-[7px] font-black uppercase" style={{ color: danger }}>Offline</span>
                )}
              </div>

              {server.error && <div className="text-[9px] font-medium italic px-2" style={{ color: danger }}>{server.error}</div>}

              <div className="space-y-3 pl-2">
                {Object.entries(groups).map(([jobId, gpus]) => (
                  <div key={jobId} className="space-y-1.5">
                    {jobId !== "SYSTEM" && (
                      <div className="flex items-center gap-1 text-[8px] font-black uppercase tracking-widest pl-1 group/job" style={{ color: subText }}>
                        <Activity size={10} style={{ color: accent }} /> JOB: {jobId}
                        <div className="ml-1 flex items-center">
                          <CopyButton text={jobId} />
                        </div>
                      </div>
                    )}
                    <div className="grid grid-cols-4 gap-1.5">
                      {gpus.map((gpu, i) => {
                        const usage = gpu.util / 100;
                        const usageColor = usage > 0.9 ? danger : (usage > 0.6 ? warning : accent);
                        return (
                          <div key={i} className="space-y-1 bg-white/5 p-1.5 rounded-lg border border-white/5 flex flex-col justify-center min-w-0">
                            <div className="flex justify-between items-center text-[8px] font-black tracking-tighter">
                              <span style={{ color: subText }}>#{i}</span>
                              <span style={{ color: usageColor }}>{gpu.util}%</span>
                            </div>
                            <div className="h-1 w-full bg-black/40 rounded-full overflow-hidden">
                              <motion.div initial={{ width: 0 }} animate={{ width: `${gpu.util}%` }} className="h-full rounded-full" style={{ backgroundColor: usageColor }} />
                            </div>
                            <div className="flex justify-between items-center text-[7px] font-bold tracking-tighter tabular-nums" style={{ color: subText }}>
                              <span>{(gpu.mem_used / 1024).toFixed(0)}G</span>
                              <span>{(gpu.power || 0).toFixed(0)}W</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        }) : (
          <div className="text-xs italic text-center mt-4" style={{ color: subText }}>Waiting for backend...</div>
        )}
      </div>
    </div>
  );
}

function ArxivWidgetContent() {
  const [papers, setPapers] = useState<any[]>([]);
  const [arxivConfig, setArxivConfig] = useState<any>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentTheme, setCurrentTheme] = useState<WidgetTheme | null>(null);
  const win = getCurrentWindow();

  useEffect(() => {
    const load = async () => {
      try {
        setPapers(await invoke("get_arxiv_papers"));
        setArxivConfig(await invoke("get_arxiv_config"));
        const config: WidgetThemeConfig = await invoke("get_theme_config");
        const themeId = config.assignments?.[win.label];
        const theme = config.themes.find(t => t.id === themeId) || config.themes.find(t => t.id === "theme-arxiv-default");
        setCurrentTheme(theme || null);
      } catch (e) {
        console.error("Arxiv widget load failed", e);
      }
    };

    load();

    const u1 = listen<any[]>("arxiv_update", (event) => setPapers(event.payload));
    const u2 = listen("theme_update", (event: any) => {
      const config = event.payload as WidgetThemeConfig;
      const themeId = config.assignments?.[win.label];
      const theme = config.themes.find(t => t.id === themeId) || config.themes.find(t => t.id === "theme-arxiv-default");
      setCurrentTheme(theme || null);
    });
    const u3 = listen("arxiv_config_update", (event: any) => {
      setArxivConfig(event.payload);
    });

    return () => {
      u1.then(f => f());
      u2.then(f => f());
      u3.then(f => f());
    };
  }, []);

  if (!currentTheme) return null;

  const handleAction = async (direction: "left" | "right" | "up") => {
    const paper = papers[currentIndex];
    if (!paper) return;

    if (direction === "left") {
      await invoke("mark_arxiv_seen", { id: paper.id, saved: false });
      setCurrentIndex(prev => prev + 1);
    } else if (direction === "right") {
      await invoke("mark_arxiv_seen", { id: paper.id, saved: true });
      setCurrentIndex(prev => prev + 1);
    } else if (direction === "up") {
      await invoke("open_link", { url: paper.link });
    }
  };

  const getC = (name: string, fallback: string) => {
    const c = currentTheme.primary_colors.find(p => p.name === name);
    return c ? hexToRgba(c.value, c.opacity ?? 1.0) : fallback;
  };
  const getT = (name: string, fallback: string) => {
    const c = currentTheme.text_colors?.find(p => p.name === name);
    return c ? hexToRgba(c.value, c.opacity ?? 1.0) : fallback;
  };

  const accent = getC("Accent", "#ec4899");
  const mainText = getT("Main Text", "#ffffff");
  const subText = getT("Sub Text", "#94a3b8");

  const currentPaper = papers[currentIndex];

  return (
    <div className={`h-full flex flex-col p-2 select-none`} style={{ color: mainText }}>
      <div className="flex items-center gap-2 mb-4">
        <Activity size={16} style={{ color: accent }} className="pointer-events-none" />
        <span className="text-xs font-black uppercase tracking-widest pointer-events-none" style={{ color: subText }}>Arxiv Radar</span>
      </div>

      <div className="flex-1 relative perspective-1000" data-no-drag="true">
        <AnimatePresence>
          {currentPaper ? (
            <motion.div
              key={currentPaper.id}
              drag
              dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
              onDragEnd={(_, info) => {
                if (info.offset.x < -100) handleAction("left");
                else if (info.offset.x > 100) handleAction("right");
                else if (info.offset.y < -100) handleAction("up");
              }}
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={((custom: any) => ({
                x: custom === "left" ? -500 : (custom === "right" ? 500 : 0),
                y: custom === "up" ? -500 : 0,
                opacity: 0,
                rotate: custom === "left" ? -20 : (custom === "right" ? 20 : 0),
                transition: { duration: 0.4 }
              })) as any}
              data-no-drag="true"
              className="absolute inset-0 bg-white/5 rounded-2xl border border-white/10 p-5 flex flex-col shadow-2xl backdrop-blur-md cursor-grab active:cursor-grabbing overflow-hidden"
            >
              <h3 className="text-sm font-bold mb-3 leading-relaxed">{currentPaper.title}</h3>
              <p className="text-[10px] opacity-60 mb-4 line-clamp-10 leading-relaxed" style={{ color: subText }}>{currentPaper.summary}</p>
              <div className="mt-auto pt-4 border-t border-white/5">
                <div className="flex flex-wrap gap-1">
                  <span className="text-[8px] bg-white/5 px-2 py-0.5 rounded-full font-medium" style={{ color: subText }}>
                    {currentPaper.authors.length > 0 ? (
                      <>{currentPaper.authors[0]}{currentPaper.authors.length > 1 ? " et al." : ""}</>
                    ) : "Unknown Author"}
                  </span>
                </div>
                {arxivConfig.show_card_hints !== false && (
                  <div className="flex items-center justify-between mt-3 text-[8px] font-black uppercase tracking-widest">
                    <span className="text-red-400">← Discard</span>
                    <span className="text-blue-400">Open PDF ↑</span>
                    <span className="text-emerald-400">Save →</span>
                  </div>
                )}
              </div>
              <div className="absolute top-0 right-0 w-24 h-24 rounded-full blur-3xl -mr-12 -mt-12 pointer-events-none opacity-20" style={{ backgroundColor: accent }} />
            </motion.div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-4">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                <Check size={32} className="text-emerald-500" />
              </div>
              <div className="space-y-1">
                <div className="text-sm font-bold">All caught up!</div>
                <p className="text-[10px] text-slate-500">Check back later for new papers in CS.</p>
              </div>
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function DeadlineWidgetContent() {
  const [deadlines, setDeadlines] = useState<any[]>([]);
  const [paperConfig, setPaperConfig] = useState<any>({});
  const [currentTheme, setCurrentTheme] = useState<WidgetTheme | null>(null);
  const win = getCurrentWindow();

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        setPaperConfig(await invoke("get_paper_config"));
        setDeadlines(await invoke("get_deadlines"));
        const config: WidgetThemeConfig = await invoke("get_theme_config");
        const themeId = config.assignments?.[win.label];
        const theme = config.themes.find(t => t.id === themeId) || config.themes.find(t => t.id === "theme-deadline-default");
        setCurrentTheme(theme || null);
      } catch (e) {
        console.error("Deadline widget load failed", e);
      }
    };

    fetchConfig();

    const unlistenDeadlines = listen<any[]>("paper_update", (event) => setDeadlines(event.payload));
    const unlistenConfig = listen<any>("paper_config_update", (event) => setPaperConfig(event.payload));
    const unlistenTheme = listen("theme_update", (event: any) => {
      const config = event.payload as WidgetThemeConfig;
      const themeId = config.assignments?.[win.label];
      const theme = config.themes.find(t => t.id === themeId) || config.themes.find(t => t.id === "theme-deadline-default");
      setCurrentTheme(theme || null);
    });

    return () => {
      unlistenDeadlines.then(f => f());
      unlistenConfig.then(f => f());
      unlistenTheme.then(f => f());
    };
  }, []);

  if (!currentTheme) return null;

  const getC = (name: string, fallback: string) => {
    const c = currentTheme.primary_colors.find(p => p.name === name);
    return c ? hexToRgba(c.value, c.opacity ?? 1.0) : fallback;
  };
  const getT = (name: string, fallback: string) => {
    const c = currentTheme.text_colors?.find(p => p.name === name);
    return c ? hexToRgba(c.value, c.opacity ?? 1.0) : fallback;
  };

  const accent = getC("Accent", "#8b5cf6");
  const highlight = getC("Highlight", "#f59e0b");
  const mainText = getT("Main Text", "#ffffff");
  const subText = getT("Sub Text", "#64748b");

  const pinnedTitles = paperConfig.pinned_titles || [];
  const pinnedList = deadlines.filter(d => pinnedTitles.includes(d.title));
  const displayList = pinnedList.length > 0 ? pinnedList : (deadlines.length > 0 ? [deadlines[0]] : []);

  return (
    <div className="h-full flex flex-col" style={{ color: mainText }}>
      <div className="flex items-center gap-2 mb-4">
        <Trophy size={16} style={{ color: highlight }} />
        <span className="text-xs font-black uppercase tracking-widest" style={{ color: subText }}>Deadlines</span>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar pr-1 w-full space-y-2">
        {displayList.length > 0 ? displayList.map((dl, idx) => (
          <div key={idx} className="bg-white/5 rounded-xl p-3 border border-white/5 relative overflow-hidden group transition-all hover:bg-white/10">
            <div className="flex items-center justify-between relative z-10">
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-black truncate">{dl.title} {dl.year}</span>
                  <span className="text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded-md bg-white/5" style={{ color: subText }}>{dl.sub}</span>
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-[8px] font-bold truncate" style={{ color: subText }}>📍 {dl.place || "Online"}</span>
                </div>
              </div>
              <div className="text-right flex-shrink-0 pl-2">
                <div className="text-[10px] font-black tabular-nums bg-white/5 px-2 py-1 rounded-lg border border-white/5" style={{ color: highlight }}>
                  <DeadlineCountdown date={dl.deadline_utc} />
                </div>
              </div>
            </div>
            <div className="absolute top-0 right-0 w-16 h-16 rounded-full blur-xl -mr-8 -mt-8 pointer-events-none" style={{ backgroundColor: `${accent}22` }} />
          </div>
        )) : (
          <div className="text-[10px] italic text-center mt-8" style={{ color: subText }}>No conferences tracked.</div>
        )}
      </div>
    </div>
  );
}



function SidebarLink({ icon, label, active, onClick, theme = "dark" }: { icon: any, label: string, active: boolean, onClick: () => void, theme?: string }) {
  const isLight = theme === "light";
  return (
    <button data-no-drag="true" onClick={onClick} className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl transition-all duration-300 group ${active
      ? (isLight ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20" : "bg-blue-600/20 text-blue-400 border border-blue-500/20")
      : (isLight ? "hover:bg-slate-100 text-slate-500 hover:text-slate-900" : "hover:bg-white/5 text-slate-500 hover:text-slate-200")}`}>
      <span className={`${active ? (isLight ? "text-white" : "text-blue-400") : (isLight ? "text-slate-400 group-hover:text-blue-600" : "group-hover:text-blue-400/80")}`}>{icon}</span>
      <span className={`font-bold text-sm ${active ? (isLight ? "text-white" : "text-white") : ""}`}>{label}</span>
      {active && <motion.div layoutId="active-indicator" className={`ml-auto w-1.5 h-1.5 rounded-full ${isLight ? "bg-white" : "bg-blue-400"}`} />}
    </button>
  );
}

function WindowButton({ icon, onClick, hoverColor = "hover:bg-white/10", theme = "dark" }: { icon: any, onClick: () => void, hoverColor?: string, theme?: string }) {
  const defaultHover = theme === "light" ? "hover:bg-black/10" : "hover:bg-white/10";
  return (
    <button data-no-drag="true" onClick={onClick} className={`w-12 h-10 flex items-center justify-center transition-all rounded-md ${hoverColor === "hover:bg-white/10" ? defaultHover : hoverColor} active:scale-95 z-50 pointer-events-auto`}>{icon}</button>
  );
}

function MasterSwitch({ enabled, onToggle }: { enabled: boolean, onToggle: (val: boolean) => void }) {
  return (
    <button 
      onClick={() => onToggle(!enabled)}
      className={`w-11 h-6 rounded-full relative transition-all duration-300 ${enabled ? "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.3)]" : "bg-slate-700"} flex items-center px-1`}
    >
      <motion.div 
        animate={{ x: enabled ? 20 : 0 }}
        className="w-4 h-4 bg-white rounded-full shadow-lg"
      />
    </button>
  );
}

function StatCard({ label, value, icon, theme = "dark" }: { label: string, value: string, icon: any, theme?: string }) {
  return (
    <div className="glass-card p-6 flex items-center gap-6 border-none">
      <div className={`w-14 h-14 rounded-2xl flex items-center justify-center border ${theme === "light" ? "bg-slate-100 border-slate-200" : "bg-white/5 border-white/10"}`}>{icon}</div>
      <div>
        <div className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-1">{label}</div>
        <div className={`text-3xl font-black tracking-tighter ${theme === "light" ? "text-slate-900" : "text-white"}`}>{value}</div>
      </div>
    </div>
  );
}

function WidgetPreviewCard({ title, status, detail, trend, color, theme = "dark", onLaunch }: { title: string, status: string, detail: string, trend: string, color: string, theme?: string, onLaunch: () => void }) {
  const isLight = theme === "light";
  const colors: Record<string, string> = isLight ? {
    blue: "bg-blue-50 border-blue-200/60 text-blue-600",
    purple: "bg-purple-50 border-purple-200/60 text-purple-600",
  } : {
    blue: "from-blue-600/10 to-blue-900/10 border-blue-500/20 text-blue-400",
    purple: "from-purple-600/10 to-purple-900/10 border-purple-500/20 text-purple-400",
  };
  return (
    <div className={`p-6 rounded-2xl border ${isLight ? colors[color] : `bg-gradient-to-br ${colors[color]}`} transition-all ${isLight ? "hover:shadow-md hover:border-blue-300" : "hover:border-white/30"} group shadow-sm flex flex-col justify-between`}>
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className={`font-bold text-lg tracking-tight ${isLight ? "text-slate-900" : "text-white"}`}>{title}</h3>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] uppercase font-black px-2.5 py-1 rounded-lg border ${isLight ? "bg-white border-slate-200 text-slate-600" : "bg-white/5 border-white/5 text-slate-400"}`}>{status}</span>
          </div>
        </div>
        <div className={`text-sm mb-6 font-medium h-10 ${isLight ? "text-slate-600" : "text-slate-400"}`}>{detail}</div>
      </div>
      <div className="flex items-center justify-between">
        <button onClick={onLaunch} className={`text-xs font-black tracking-wider uppercase px-4 py-2 rounded-xl transition-all ${isLight ? "bg-slate-200/50 text-slate-900 hover:bg-slate-200" : "bg-white/10 text-white hover:bg-white/20"}`}>{trend}</button>
        <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${isLight ? "bg-slate-200/50 text-slate-600 group-hover:bg-slate-200" : "bg-white/5 text-white group-hover:bg-white/10"}`}><ChevronRight size={16} /></div>
      </div>
    </div>
  );
}


function SettingsPanel({ gpuConfig, paperConfig, arxivConfig, appConfig, themeConfig, onSaveGpu, onSavePaper, onSaveArxiv, onSaveApp, onSaveThemes, isAutostart, onToggleAutostart, activeWidgets }: any) {
  const [localGpu, setLocalGpu] = useState(gpuConfig);
  const [localPaper, setLocalPaper] = useState(paperConfig);
  const [localArxiv, setLocalArxiv] = useState(arxivConfig);

  useEffect(() => {
    setLocalGpu(gpuConfig);
  }, [gpuConfig]);

  useEffect(() => {
    setLocalPaper(paperConfig);
  }, [paperConfig]);

  useEffect(() => {
    setLocalArxiv(arxivConfig);
  }, [arxivConfig]);

  const addServer = () => {
    const servers = localGpu?.servers || [];
    const next = { ...localGpu, servers: [...servers, { host: "", user: "root", password: "", port: 22 }] };
    setLocalGpu(next);
  };

  const removeServer = (idx: number) => {
    const servers = localGpu?.servers || [];
    const next = { ...localGpu, servers: servers.filter((_: any, i: number) => i !== idx) };
    setLocalGpu(next);
  };

  const updateServer = (idx: number, field: string, val: any) => {
    const next = { ...localGpu };
    const servers = [...(next.servers || [])];
    if (servers[idx]) {
      servers[idx] = { ...servers[idx], [field]: val };
      next.servers = servers;
      setLocalGpu(next);
    }
  };

  return (
    <motion.div key="settings" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-12">
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className={`text-2xl font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>General Settings</h2>
        </div>
        <div className={`p-6 border border-[var(--dashboard-border)] rounded-2xl space-y-6 ${appConfig.theme === "light" ? "bg-slate-50" : "bg-white/5"}`}>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className={`text-lg font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Dashboard Theme</div>
              <p className="text-sm text-slate-400">Choose between light and dark mode for the control panel.</p>
            </div>
            <div className={`flex p-1 rounded-xl border border-[var(--dashboard-border)] ${appConfig.theme === "light" ? "bg-slate-200" : "bg-black/20"}`}>
              <button
                onClick={() => onSaveApp({ ...appConfig, theme: "light" })}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all ${appConfig.theme === "light" ? "bg-white text-slate-900 shadow-xl" : "text-slate-500 hover:text-slate-300"}`}
              >
                <Sun size={16} /> Light
              </button>
              <button
                onClick={() => onSaveApp({ ...appConfig, theme: "dark" })}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all ${appConfig.theme === "dark" ? "bg-blue-600 text-white shadow-xl shadow-blue-600/20" : "text-slate-500 hover:text-slate-300"}`}
              >
                <Moon size={16} /> Dark
              </button>
            </div>
          </div>

          <div className="border-t border-[var(--dashboard-border)] pt-6 flex items-center justify-between">
            <div className="space-y-1">
              <div className={`text-lg font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Launch at Startup</div>
              <p className="text-sm text-slate-400">Automatically start Widgitron when you log in to Windows.</p>
            </div>
            <button
              onClick={onToggleAutostart}
              className={`px-6 py-2 rounded-xl text-sm font-bold transition-all ${isAutostart ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/20" : "bg-black/40 text-slate-500 border border-white/10"}`}
            >
              {isAutostart ? "Enabled" : "Disabled"}
            </button>
          </div>

          <div className="border-t border-[var(--dashboard-border)] pt-6 flex items-center justify-between">
            <div className="space-y-1">
              <div className={`text-lg font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Hide Dashboard on Startup</div>
              <p className="text-sm text-slate-400">Keep the control panel hidden in the system tray when the app starts.</p>
            </div>
            <button
              onClick={() => onSaveApp({ ...appConfig, hide_on_startup: !appConfig.hide_on_startup })}
              className={`px-6 py-2 rounded-xl text-sm font-bold transition-all ${appConfig.hide_on_startup ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20" : "bg-black/40 text-slate-500 border border-white/10"}`}
            >
              {appConfig.hide_on_startup ? "Yes" : "No"}
            </button>
          </div>
        </div>
      </section>
 
      <ThemeManagementSection 
        themeConfig={themeConfig} 
        onSaveThemes={onSaveThemes} 
        dashboardTheme={appConfig.theme}
        activeWidgets={activeWidgets}
      />
 
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className={`text-2xl font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>GPU Monitor Configuration</h2>
          <button onClick={() => onSaveGpu(localGpu)} className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-xl text-sm font-bold text-white transition-all shadow-lg shadow-blue-600/30">Save GPU Settings</button>
        </div>
        <div className="space-y-4">
          {(localGpu?.servers || []).map((s: any, i: number) => (
            <div key={i} className={`p-6 border border-[var(--dashboard-border)] rounded-2xl grid grid-cols-4 gap-4 relative group ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
              <button onClick={() => removeServer(i)} className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-red-500 text-white opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center shadow-lg"><X size={12} /></button>
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Host / IP</label>
                <input type="text" value={s.host || ""} onChange={e => updateServer(i, "host", e.target.value)} className={`w-full px-4 py-2 rounded-xl text-sm font-bold border transition-all ${appConfig.theme === "light" ? "bg-slate-50 border-slate-200 text-slate-900 focus:bg-white" : "bg-black/40 border-white/10 text-white focus:bg-black/60"}`} />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Username</label>
                <input type="text" value={s.user || ""} onChange={e => updateServer(i, "user", e.target.value)} className={`w-full px-4 py-2 rounded-xl text-sm font-bold border transition-all ${appConfig.theme === "light" ? "bg-slate-50 border-slate-200 text-slate-900 focus:bg-white" : "bg-black/40 border-white/10 text-white focus:bg-black/60"}`} />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Password</label>
                <input type="password" value={s.password || ""} onChange={e => updateServer(i, "password", e.target.value)} className={`w-full px-4 py-2 rounded-xl text-sm font-bold border transition-all ${appConfig.theme === "light" ? "bg-slate-50 border-slate-200 text-slate-900 focus:bg-white" : "bg-black/40 border-white/10 text-white focus:bg-black/60"}`} />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Port</label>
                <input type="number" value={s.port || 22} onChange={e => updateServer(i, "port", parseInt(e.target.value))} className={`w-full px-4 py-2 rounded-xl text-sm font-bold border transition-all ${appConfig.theme === "light" ? "bg-slate-50 border-slate-200 text-slate-900 focus:bg-white" : "bg-black/40 border-white/10 text-white focus:bg-black/60"}`} />
              </div>
              <div className="col-span-4 flex items-center gap-4 pt-2">
                <button
                  onClick={() => updateServer(i, "use_slurm", !s.use_slurm)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${s.use_slurm ? "bg-amber-500/20 text-amber-400 border border-amber-500/20 shadow-lg shadow-amber-500/10" : "bg-black/40 text-slate-500 border border-white/5 hover:border-white/20"}`}
                >
                  <div className={`w-2 h-2 rounded-full ${s.use_slurm ? "bg-amber-400 animate-pulse" : "bg-slate-600"}`} />
                  Slurm Cluster Mode
                </button>
                {s.use_slurm && (
                  <span className="text-[9px] text-amber-500/60 font-medium italic">Enables job-based monitoring via squeue & srun</span>
                )}
              </div>
            </div>
          ))}
          <button onClick={addServer} className="w-full py-4 border-2 border-dashed border-white/10 rounded-2xl text-slate-500 hover:text-white hover:border-white/20 transition-all flex items-center justify-center gap-2 font-bold uppercase tracking-widest text-xs"><Plus size={16} /> Add New Server</button>
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className={`text-2xl font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Conference Filters</h2>
        </div>
        <div className={`p-6 border border-[var(--dashboard-border)] rounded-2xl space-y-6 ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
          <div className="grid grid-cols-2 gap-8">
            <div className="space-y-4">
              <div className="space-y-3">
                <label className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-600" : "text-slate-300"}`}>Target CCF Ranks</label>
                <div className="flex flex-wrap gap-2">
                  {["A", "B", "C", "N"].map(r => (
                    <button
                      key={r}
                      onClick={() => {
                        const ranks = localPaper.filter_by_rank || [];
                        const next = ranks.includes(r) ? ranks.filter((i: string) => i !== r) : [...ranks, r];
                        const nextConfig = { ...localPaper, filter_by_rank: next };
                        setLocalPaper(nextConfig);
                        onSavePaper(nextConfig);
                      }}
                      className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${localPaper.filter_by_rank?.includes(r) ? "bg-purple-500 text-white shadow-lg shadow-purple-500/20" : (appConfig.theme === "light" ? "bg-slate-100 text-slate-500 border border-slate-200" : "bg-black/40 text-slate-500 border border-white/5 hover:border-white/20")}`}
                    >Rank {r}</button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <label className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-600" : "text-slate-300"}`}>Categories</label>
                <div className="flex flex-wrap gap-2">
                  {["AI", "CV", "NLP", "HCI", "DM", "Graphics", "Security", "Network", "Systems"].map(cat => (
                    <button
                      key={cat}
                      onClick={() => {
                        const subs = localPaper.filter_by_sub || [];
                        const next = subs.includes(cat) ? subs.filter((i: string) => i !== cat) : [...subs, cat];
                        const nextConfig = { ...localPaper, filter_by_sub: next };
                        setLocalPaper(nextConfig);
                        onSavePaper(nextConfig);
                      }}
                      className={`px-4 py-1.5 rounded-lg text-xs font-black transition-all ${localPaper.filter_by_sub?.includes(cat) ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20" : (appConfig.theme === "light" ? "bg-slate-100 text-slate-500 border border-slate-200" : "bg-black/40 text-slate-500 border border-white/5 hover:border-white/20")}`}
                    >{cat}</button>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="space-y-3">
                <label className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-600" : "text-slate-300"}`}>Display Options</label>
                <div className="flex items-center gap-4">
                  <button
                    onClick={() => {
                      const nextConfig = { ...localPaper, show_past_deadlines: !localPaper.show_past_deadlines };
                      setLocalPaper(nextConfig);
                      onSavePaper(nextConfig);
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${localPaper.show_past_deadlines ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/20" : "bg-black/40 text-slate-500 border border-white/5"}`}
                  >Show Past Events</button>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-600" : "text-slate-300"}`}>Max Display Count</label>
                  <span className="text-xs font-black text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded-md">{localPaper.max_deadlines || 5}</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="100"
                  step="5"
                  value={localPaper.max_deadlines || 5}
                  onChange={(e) => {
                    const next = parseInt(e.target.value);
                    const nextConfig = { ...localPaper, max_deadlines: next };
                    setLocalPaper(nextConfig);
                    onSavePaper(nextConfig);
                  }}
                  className="w-full h-1.5 bg-blue-600/20 rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
                <p className="text-[10px] text-slate-500 font-medium">Control how many upcoming conferences are shown.</p>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className={`text-2xl font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Arxiv Radar Settings</h2>
          <button onClick={() => onSaveArxiv(localArxiv)} className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-xl text-sm font-bold text-white transition-all shadow-lg shadow-blue-600/30">Save Arxiv Settings</button>
        </div>
        <div className={`p-6 border border-[var(--dashboard-border)] rounded-2xl space-y-6 ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
          <div className="grid grid-cols-2 gap-8">
            <div className="space-y-4">
              <div className="space-y-3">
                <label className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-600" : "text-slate-300"}`}>Research Category</label>
                <div className="flex flex-wrap gap-2">
                  {["cs", "stat", "math", "eess"].map(c => (
                    <button
                      key={c}
                      onClick={() => {
                        const next = { ...localArxiv, category: c };
                        setLocalArxiv(next);
                        onSaveArxiv(next);
                      }}
                      className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${localArxiv.category === c ? "bg-pink-500 text-white shadow-lg shadow-pink-500/20" : (appConfig.theme === "light" ? "bg-slate-100 text-slate-500 border border-slate-200" : "bg-black/40 text-slate-500 border border-white/5 hover:border-white/20")}`}
                    >{c.toUpperCase()}</button>
                  ))}
                </div>
              </div>
              <div className="space-y-3">
                <label className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-600" : "text-slate-300"}`}>Keywords (Comma separated)</label>
                <input 
                  type="text" 
                  value={(localArxiv.keywords || []).join(", ")} 
                  onChange={e => {
                    const kws = e.target.value.split(",").map(k => k.trim()).filter(k => k);
                    const next = { ...localArxiv, keywords: kws };
                    setLocalArxiv(next);
                  }}
                  onBlur={() => onSaveArxiv(localArxiv)}
                  className={`w-full px-4 py-3 rounded-xl text-sm font-bold border transition-all ${appConfig.theme === "light" ? "bg-slate-50 border-slate-200 text-slate-900 focus:bg-white" : "bg-black/40 border-white/10 text-white focus:bg-black/60"}`}
                  placeholder="e.g. gaussian, vla, llm"
                />
              </div>
            </div>
            <div className="space-y-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-600" : "text-slate-300"}`}>Update Interval (Hours)</label>
                  <span className="text-xs font-black text-pink-500 bg-pink-500/10 px-2 py-0.5 rounded-md">{Math.round((localArxiv.update_interval || 43200) / 3600)}h</span>
                </div>
                <input
                  type="range"
                  min="3600"
                  max="86400"
                  step="3600"
                  value={localArxiv.update_interval || 43200}
                  onChange={(e) => {
                    const nextVal = parseInt(e.target.value);
                    const next = { ...localArxiv, update_interval: nextVal };
                    setLocalArxiv(next);
                    onSaveArxiv(next);
                  }}
                  className="w-full h-1.5 bg-pink-600/20 rounded-lg appearance-none cursor-pointer accent-pink-600"
                />
              </div>
              <div className="flex items-center justify-between p-4 rounded-2xl bg-white/5 border border-white/5">
                <div className="space-y-1">
                  <div className={`text-sm font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Show Interaction Hints</div>
                  <div className="text-[10px] text-slate-500">Display swipe instructions at the bottom of cards</div>
                </div>
                <MasterSwitch 
                  enabled={localArxiv.show_card_hints !== false} 
                  onToggle={(val) => {
                    const next = { ...localArxiv, show_card_hints: val };
                    setLocalArxiv(next);
                    onSaveArxiv(next);
                  }} 
                />
              </div>
            </div>
          </div>
        </div>
      </section>
      
      <section className="pb-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className={`text-2xl font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>About</h2>
        </div>
        <div className={`p-8 border border-[var(--dashboard-border)] rounded-3xl flex flex-col items-center text-center space-y-6 ${appConfig.theme === "light" ? "bg-white shadow-xl shadow-slate-200/50" : "bg-white/5 backdrop-blur-xl"}`}>
          <div className="w-20 h-20 rounded-3xl bg-blue-600 flex items-center justify-center shadow-2xl shadow-blue-600/40 transform -rotate-6 overflow-hidden border-2 border-white/20">
            <img src="/logo.png" alt="Widgitron" className="w-full h-full object-cover" />
          </div>
          <div className="space-y-2">
            <h3 className={`text-xl font-black uppercase tracking-tighter ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Widgitron</h3>
            <div className="flex items-center justify-center gap-2">
              <span className="px-3 py-1 rounded-full bg-blue-500/10 text-blue-500 text-[10px] font-black uppercase tracking-widest border border-blue-500/10">v0.2.1 Stable</span>
              <span className="px-3 py-1 rounded-full bg-purple-500/10 text-purple-500 text-[10px] font-black uppercase tracking-widest border border-purple-500/10">Research Edition</span>
            </div>
          </div>
          <p className="text-xs text-slate-500 max-w-md leading-relaxed font-medium">
            Widgitron is a modular desktop widget framework designed for researchers and developers. 
            Keep track of GPUs, deadlines, and the latest Arxiv papers right on your desktop.
          </p>
          <div className="pt-6 flex items-center gap-8 border-t border-white/5 w-full justify-center">
             <div className="flex flex-col items-center gap-1">
                <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">Engine</span>
                <span className={`text-xs font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Tauri v2 + React</span>
             </div>
             <div className="flex flex-col items-center gap-1">
                <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">Developer</span>
                <span className={`text-xs font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Stark (momo)</span>
             </div>
          </div>
        </div>
      </section>
    </motion.div>
  );
}

function ThemeManagementSection({ themeConfig, onSaveThemes, dashboardTheme, activeWidgets }: { themeConfig: WidgetThemeConfig, onSaveThemes: (config: WidgetThemeConfig) => void, dashboardTheme: string, activeWidgets: string[] }) {
  const [editingThemeId, setEditingThemeId] = useState<string | null>(null);
  const [localThemes, setLocalThemes] = useState<WidgetThemeConfig>(themeConfig);

  useEffect(() => { setLocalThemes(themeConfig); }, [themeConfig]);

  const themes = localThemes.themes || [];
  const editingTheme = themes.find(t => t.id === editingThemeId);

  const save = (next: WidgetThemeConfig) => {
    setLocalThemes(next);
    onSaveThemes(next);
  };

  const addTheme = () => {
    const id = `theme-${Date.now()}`;
    const next = {
      ...localThemes,
      themes: [...themes, {
        id,
        name: "New Theme",
        is_default: false,
        bg_color: "#0f172a",
        bg_opacity: 0.95,
        text_colors: [
          { name: "Main Text", value: "#ffffff", opacity: 1.0 },
          { name: "Sub Text", value: "#94a3b8", opacity: 0.6 }
        ],
        primary_colors: [{ name: "Accent", value: "#3b82f6", opacity: 1.0 }]
      }]
    };
    save(next);
    setEditingThemeId(id);
  };

  const copyTheme = (theme: WidgetTheme) => {
    const id = `theme-copy-${Date.now()}`;
    // Deep copy to avoid shared object references (especially for primary_colors array)
    const newTheme = JSON.parse(JSON.stringify(theme));
    newTheme.id = id;
    newTheme.name = `${theme.name} (Copy)`;
    newTheme.is_default = false;
    const next = {
      ...localThemes,
      themes: [...themes, newTheme]
    };
    save(next);
    setEditingThemeId(id);
  };

  const deleteTheme = (id: string) => {
    const next = {
      ...localThemes,
      themes: themes.filter(t => t.id !== id),
      assignments: Object.fromEntries(Object.entries(localThemes.assignments || {}).filter(([_, tid]) => tid !== id))
    };
    save(next);
  };

  const updateTheme = (id: string, field: keyof WidgetTheme, val: any) => {
    const next = {
      ...localThemes,
      themes: themes.map(t => t.id === id ? { ...t, [field]: val } : t)
    };
    save(next);
  };

  const assignTheme = (widgetId: string, themeId: string) => {
    let finalThemeId = themeId;
    if (!finalThemeId) {
      if (widgetId.includes("gpu")) finalThemeId = "theme-gpu-default";
      else if (widgetId.includes("deadlines")) finalThemeId = "theme-deadline-default";
      else if (widgetId.includes("arxiv")) finalThemeId = "theme-arxiv-default";
    }
    const next = {
      ...localThemes,
      assignments: { ...(localThemes.assignments || {}), [widgetId]: finalThemeId }
    };
    save(next);
  };

  const isLight = dashboardTheme === "light";

  return (
    <section>
      <div className="flex items-center justify-between mb-6">
        <h2 className={`text-2xl font-bold ${isLight ? "text-slate-900" : "text-white"}`}>Widget Themes</h2>
        <button onClick={addTheme} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-xl text-xs font-black uppercase tracking-widest text-white transition-all flex items-center gap-2"><Plus size={14} /> Create Theme</button>
      </div>

      <div className={`p-6 border border-[var(--dashboard-border)] rounded-3xl space-y-8 ${isLight ? "bg-slate-50" : "bg-white/5"}`}>
        {/* Theme List */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {themes.map(theme => {
            const usedBy = Object.entries(localThemes.assignments || {})
              .filter(([_, tid]) => tid === theme.id)
              .map(([wid]) => wid.replace("widget-", "").replace("-default", ""));

            return (
              <div key={theme.id} className={`p-5 rounded-2xl border transition-all ${editingThemeId === theme.id ? "ring-2 ring-blue-500 border-blue-500" : (isLight ? "bg-white border-slate-200" : "bg-black/20 border-white/5")}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="font-bold text-sm truncate pr-2">{theme.name}</div>
                  {theme.is_default && <span className="text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/10 whitespace-nowrap flex-shrink-0">System Preset</span>}
                </div>
                
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-6 h-6 rounded-md border border-white/10 shadow-inner" style={{ backgroundColor: theme.bg_color, opacity: theme.bg_opacity }} />
                  <div className="flex -space-x-1">
                    {theme.primary_colors.map((c, i) => (
                      <div key={i} className="w-4 h-4 rounded-full border border-black/20" style={{ backgroundColor: c.value }} title={c.name} />
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-4 overflow-hidden h-5">
                  {usedBy.length > 0 ? (
                    <div className="flex items-center gap-1.5 overflow-hidden">
                      <span className="text-[10px] text-slate-500 font-bold uppercase truncate">Used by: {usedBy.join(", ")}</span>
                      {usedBy.some(u => activeWidgets.includes(`widget-${u}-default`)) && <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" title="Active" />}
                    </div>
                  ) : (
                    <span className="text-[10px] text-slate-600 italic">Unassigned</span>
                  )}
                </div>

                {/* Direct Assignment Buttons */}
                <div className="flex items-center gap-1.5 mb-4 p-1.5 bg-black/10 rounded-lg border border-white/5">
                  {["gpu", "deadlines", "arxiv"].map(type => {
                    const wid = `widget-${type}-default`;
                    const isActive = localThemes.assignments?.[wid] === theme.id;
                    return (
                      <button
                        key={wid}
                        onClick={() => assignTheme(wid, isActive ? "" : theme.id)}
                        className={`flex-1 py-1 rounded-md text-[8px] font-black uppercase tracking-tighter transition-all border ${isActive ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" : "bg-white/5 text-slate-600 border-transparent hover:border-white/10"}`}
                      >
                        {type}
                      </button>
                    );
                  })}
                </div>

                <div className="flex items-center gap-1.5">
                  <button onClick={() => setEditingThemeId(theme.id)} className="flex-1 py-2 rounded-lg bg-blue-600/10 text-blue-400 hover:bg-blue-600 hover:text-white transition-all text-[10px] font-black uppercase tracking-widest">
                    {theme.is_default ? "Assign" : "Edit"}
                  </button>
                  <button onClick={() => copyTheme(theme)} className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 transition-all"><Copy size={14} /></button>
                  {!theme.is_default && (
                    <button onClick={() => deleteTheme(theme.id)} className="p-2 rounded-lg bg-red-500/10 hover:bg-red-500 text-red-400 hover:text-white transition-all"><X size={14} /></button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Editor */}
        <AnimatePresence>
          {editingTheme && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} className={`p-8 rounded-3xl border ${isLight ? "bg-white border-slate-200" : "bg-black/60 border-white/10 backdrop-blur-xl"} space-y-8 relative`}>
              <button onClick={() => setEditingThemeId(null)} className="absolute top-6 right-6 text-slate-500 hover:text-white transition-colors p-2 rounded-full hover:bg-white/10"><X size={20} /></button>
              
              {!editingTheme.is_default ? (
                <div className="grid grid-cols-2 gap-12">
                  <div className="space-y-6">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Theme Name</label>
                      <input type="text" value={editingTheme.name} onChange={e => updateTheme(editingTheme.id, "name", e.target.value)} className={`w-full px-4 py-3 rounded-xl text-sm font-bold border transition-all ${isLight ? "bg-slate-50 border-slate-200" : "bg-black/40 border-white/10 text-white"}`} />
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">BG Color</label>
                        <div className="flex items-center gap-3">
                          <input type="color" value={editingTheme.bg_color} onChange={e => updateTheme(editingTheme.id, "bg_color", e.target.value)} className="w-10 h-10 rounded-full bg-black/10 border-2 border-white/20 hover:border-blue-500 transition-all cursor-pointer overflow-hidden shadow-lg shadow-black/20" />
                          <span className="text-[10px] font-mono font-bold opacity-40 uppercase">{editingTheme.bg_color}</span>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Opacity ({Math.round(editingTheme.bg_opacity * 100)}%)</label>
                        <input type="range" min="0" max="1" step="0.01" value={editingTheme.bg_opacity} onChange={e => updateTheme(editingTheme.id, "bg_opacity", parseFloat(e.target.value))} className="w-full h-8 accent-blue-600" />
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Text Colors</label>
                      </div>
                      <div className="space-y-3">
                        {editingTheme.text_colors.map((c, i) => (
                          <div key={i} className={`flex flex-col gap-2 p-4 rounded-2xl border transition-all group ${isLight ? "bg-blue-50/50 border-blue-100" : "bg-black/20 border-white/5"}`}>
                            <div className="flex items-center gap-3">
                              <input type="color" value={c.value} onChange={e => {
                                const colors = [...editingTheme.text_colors];
                                colors[i].value = e.target.value;
                                updateTheme(editingTheme.id, "text_colors", colors);
                              }} className="w-8 h-8 rounded-full bg-black/10 border-2 border-white/20 hover:border-blue-500 transition-all cursor-pointer overflow-hidden shadow-lg shadow-black/20" />
                              <input type="text" value={c.name} onChange={e => {
                                const colors = [...editingTheme.text_colors];
                                colors[i].name = e.target.value;
                                updateTheme(editingTheme.id, "text_colors", colors);
                              }} className={`flex-1 bg-transparent border-none text-xs font-bold focus:ring-0 ${isLight ? "text-blue-900" : "text-white"}`} />
                              <span className={`text-[10px] font-mono ${isLight ? "text-blue-600 font-black" : "opacity-40"}`}>{Math.round((c.opacity ?? 1) * 100)}%</span>
                            </div>
                            <input type="range" min="0" max="1" step="0.01" value={c.opacity ?? 1} onChange={e => {
                              const colors = [...editingTheme.text_colors];
                              colors[i].opacity = parseFloat(e.target.value);
                              updateTheme(editingTheme.id, "text_colors", colors);
                            }} className="w-full h-4 accent-blue-600" />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Primary Colors</label>
                      <button 
                        onClick={() => {
                          const colors = [...editingTheme.primary_colors, { name: "New Color", value: "#3b82f6" }];
                          updateTheme(editingTheme.id, "primary_colors", colors);
                        }} 
                        className="mr-12 text-[10px] font-black text-blue-400 uppercase tracking-widest flex items-center gap-1 hover:text-blue-300 transition-colors"
                      ><Plus size={12} /> Add Color</button>
                    </div>
                    <div className="space-y-3 max-h-[320px] overflow-y-auto pr-3 custom-scrollbar">
                      {editingTheme.primary_colors.map((c, i) => (
                        <div key={i} className={`flex flex-col gap-2 p-4 rounded-2xl border transition-all group ${isLight ? "bg-blue-50/50 border-blue-100" : "bg-black/20 border-white/5"}`}>
                          <div className="flex items-center gap-3">
                            <input type="color" value={c.value} onChange={e => {
                              const colors = [...editingTheme.primary_colors];
                              colors[i].value = e.target.value;
                              updateTheme(editingTheme.id, "primary_colors", colors);
                            }} className="w-8 h-8 rounded-full bg-black/10 border-2 border-white/20 hover:border-blue-500 transition-all cursor-pointer overflow-hidden shadow-lg shadow-black/20" />
                            <input type="text" value={c.name} onChange={e => {
                              const colors = [...editingTheme.primary_colors];
                              colors[i].name = e.target.value;
                              updateTheme(editingTheme.id, "primary_colors", colors);
                            }} className={`flex-1 bg-transparent border-none text-xs font-bold focus:ring-0 ${isLight ? "text-blue-900" : "text-white"}`} />
                            <span className={`text-[10px] font-mono ${isLight ? "text-blue-600 font-black" : "opacity-40"}`}>{Math.round((c.opacity ?? 1) * 100)}%</span>
                            <button 
                              onClick={() => {
                                const colors = editingTheme.primary_colors.filter((_, idx) => idx !== i);
                                updateTheme(editingTheme.id, "primary_colors", colors);
                              }} 
                              className={`p-1.5 transition-colors opacity-0 group-hover:opacity-100 ${isLight ? "text-blue-300 hover:text-red-500" : "text-slate-500 hover:text-red-500"}`}
                            ><X size={14} /></button>
                          </div>
                          <input type="range" min="0" max="1" step="0.01" value={c.opacity ?? 1} onChange={e => {
                            const colors = [...editingTheme.primary_colors];
                            colors[i].opacity = parseFloat(e.target.value);
                            updateTheme(editingTheme.id, "primary_colors", colors);
                          }} className="w-full h-4 accent-blue-600" />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-4">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="p-3 rounded-2xl bg-blue-500/10 text-blue-400 border border-blue-500/10">
                      <Settings size={24} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold">System Preset: {editingTheme.name}</h3>
                      <p className="text-xs text-slate-500">This theme is read-only. You can assign it to widgets below.</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Assignment Section (Unified) */}
              <div className="pt-8 border-t border-white/5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block mb-4">Assign Theme to Widgets</label>
                <div className="flex gap-4">
                  {["gpu", "deadlines"].map(type => {
                    const wid = `widget-${type}-default`;
                    const isActive = localThemes.assignments?.[wid] === editingTheme.id;
                    const name = type.toUpperCase();
                    return (
                      <button
                        key={wid}
                        onClick={() => assignTheme(wid, isActive ? "" : editingTheme.id)}
                        className={`flex-1 flex items-center justify-between px-6 py-4 rounded-2xl transition-all border ${isActive ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-white/5 text-slate-500 border-white/5 hover:border-white/10"}`}
                      >
                        <span className="text-xs font-black uppercase tracking-widest">{name}</span>
                        <div className={`w-2 h-2 rounded-full ${isActive ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)] animate-pulse" : "bg-white/10"}`} />
                      </button>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
 
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
 
  const handleCopy = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
 
    const doCopy = async () => {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
          return true;
        }
      } catch (e) {
        console.error("Clipboard API failed", e);
      }
 
      // Fallback
      try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        textArea.style.top = "0";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const success = document.execCommand('copy');
        document.body.removeChild(textArea);
        return success;
      } catch (err) {
        console.error("Fallback copy failed", err);
        return false;
      }
    };
 
    const result = await doCopy();
    if (result) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
 
  return (
    <button
      onClick={handleCopy}
      onMouseDown={(e) => e.stopPropagation()}
      className="p-1 hover:bg-white/10 rounded transition-colors text-slate-400/40 hover:text-blue-400 flex items-center justify-center pointer-events-auto"
      title="Copy Job ID"
      data-no-drag="true"
    >
      {copied ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
    </button>
  );
}
 
export default App;
