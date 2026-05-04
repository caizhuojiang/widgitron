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
  Moon
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { APP_VERSION } from "./constants";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { enable, disable, isEnabled } from "@tauri-apps/plugin-autostart";
import { WebviewWindow, getAllWebviewWindows } from "@tauri-apps/api/webviewWindow";

// App Component
const appWindow = getCurrentWindow();

function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [isMaximized, setIsMaximized] = useState(false);
  const [windowLabel, setWindowLabel] = useState("");
  const [isLocked, setIsLocked] = useState(true);
  const [isPinned, setIsPinned] = useState(true);
  const [gpuData, setGpuData] = useState<any[]>([]);
  const [deadlines, setDeadlines] = useState<any[]>([]);
  const [gpuConfig, setGpuConfig] = useState<any>({ servers: [] });
  const [paperConfig, setPaperConfig] = useState<any>({});
  const [appConfig, setAppConfig] = useState<any>({ theme: "dark" });
  const [isAutostart, setIsAutostart] = useState(false);
  const [activeWidgets, setActiveWidgets] = useState<string[]>([]);

  useEffect(() => {
    try {
      const win = appWindow;
      setWindowLabel(win.label);
      
      const unlisten = win.onResized(async () => {
        const maximized = await win.isMaximized();
        setIsMaximized(maximized);
      });
      
      const loadConfigs = async () => {
        try {
          const gc = await invoke("get_gpu_config");
          const pc = await invoke("get_paper_config");
          const ac = await invoke("get_app_config");
          const initialDeadlines: any = await invoke("get_deadlines");
          const initialGpuData: any = await invoke("get_gpu_data");
          
          setGpuConfig(gc);
          setPaperConfig(pc);
          setAppConfig(ac);
          setDeadlines(initialDeadlines);
          setGpuData(initialGpuData);
          setIsAutostart(await isEnabled());
          
          // Initial check for active widgets
          const windows = await getAllWebviewWindows();
          const active = [];
          for (const win of windows) {
            if (win.label.startsWith("widget-") && await win.isVisible()) {
              active.push(win.label);
            }
          }
          setActiveWidgets(active);
        } catch (e) { console.error("Failed to load configs", e); }
      };
      loadConfigs();

      const unlistenGpu = listen<any>("gpu_update", (event) => {
        const item = event.payload;
        setGpuData(prev => {
          const index = prev.findIndex(s => s.host === item.host);
          if (index === -1) return [...prev, item];
          const next = [...prev];
          next[index] = item;
          return next;
        });
      });

      const unlistenPaper = listen<any[]>("paper_update", (event) => {
        setDeadlines(event.payload);
      });

      return () => { 
        unlisten.then(f => f()); 
        unlistenGpu.then(f => f());
        unlistenPaper.then(f => f());
      };
    } catch (e) {
      console.error("Failed to init App", e);
    }
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
    } catch (e) { console.error("Save failed", e); }
  };

  const togglePinConference = async (title: string) => {
    const nextPinned = (paperConfig.pinned_titles || []).includes(title)
      ? paperConfig.pinned_titles.filter((t: string) => t !== title)
      : [...(paperConfig.pinned_titles || []), title];
    const nextConfig = { ...paperConfig, pinned_titles: nextPinned };
    await savePaperConfig(nextConfig);
  };

  const saveAppConfig = async (newConfig: any) => {
    try {
      await invoke("save_app_config", { config: newConfig });
      setAppConfig(newConfig);
    } catch (e) { console.error("Save failed", e); }
  };

  const toggleMaximize = async () => {
    try {
      await getCurrentWindow().toggleMaximize();
    } catch (e) { console.error(e); }
  };

  const handleToggleWidget = async (id: string, title: string) => {
    try {
      await invoke("toggle_widget", { id, title });
      // Update local state by checking current visibility
      const win = await WebviewWindow.getByLabel(id);
      const isVisible = await win?.isVisible();
      setActiveWidgets(prev => {
        if (isVisible) return prev.includes(id) ? prev : [...prev, id];
        return prev.filter(i => i !== id);
      });
    } catch (e) { console.error("Toggle failed", e); }
  };

  const toggleLock = () => setIsLocked(!isLocked);

  const togglePin = async () => {
    try {
      const next = !isPinned;
      await getCurrentWindow().setAlwaysOnTop(next);
      setIsPinned(next);
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

  // --- DESKTOP WIDGET VIEW ---
  if (windowLabel.startsWith("widget-")) {
    const isGpu = windowLabel.includes("gpu");
    const isDeadline = windowLabel.includes("deadlines");

    return (
      <div className="h-screen w-screen flex flex-col group select-none overflow-hidden relative bg-transparent p-0">
        {/* Floating Controls (Now inside the window, but top-right) */}
        <div className="absolute top-1 right-1 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-50">
          <button data-no-drag="true" onClick={toggleLock} className="w-7 h-7 flex items-center justify-center rounded-md bg-black/60 border border-white/10 text-white/70 hover:text-white transition-all shadow-lg backdrop-blur-md">
            {isLocked ? <Lock size={12} /> : <Unlock size={12} />}
          </button>
          <button data-no-drag="true" onClick={togglePin} className={`w-7 h-7 flex items-center justify-center rounded-md bg-black/60 border border-white/10 ${isPinned ? "text-blue-400" : "text-white/70"} hover:text-white transition-all shadow-lg backdrop-blur-md`} title={isPinned ? "Unpin from top" : "Pin to top"}>
            {isPinned ? <Pin size={12} /> : <PinOff size={12} />}
          </button>
          <button data-no-drag="true" onClick={handleClose} className="w-7 h-7 flex items-center justify-center rounded-md bg-red-500/30 border border-red-500/20 text-red-400 hover:bg-red-500 hover:text-white transition-all shadow-lg backdrop-blur-md">
            <X size={12} />
          </button>
        </div>

        {/* The Glass Card (Fills the window, buttons overlap content) */}
        <div 
          className={`flex-1 bg-slate-900/95 backdrop-blur-3xl border border-white/10 p-5 flex flex-col gap-4 relative overflow-hidden rounded-xl z-10 ${isLocked ? "pointer-events-none" : "pointer-events-auto shadow-2xl shadow-black/80"}`}
          onMouseDown={!isLocked ? startDrag : undefined}
          data-tauri-drag-region={!isLocked ? "true" : "false"}
        >
          {isGpu && <GPUWidgetContent />}
          {isDeadline && <DeadlineWidgetContent />}
        </div>
      </div>
    );
  }

  // --- MAIN CONTROL PANEL VIEW ---
  return (
    <div className={`flex h-screen w-screen overflow-hidden ${appConfig.theme === "light" ? "light-theme" : ""} glass rounded-xl border-none shadow-2xl relative`}>
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
          <div className={`my-4 border-t ${appConfig.theme === "light" ? "border-slate-200" : "border-white/10"}`} />
          <SidebarLink icon={<Settings size={20} />} label="Settings" active={activeTab === "settings"} onClick={() => setActiveTab("settings")} theme={appConfig.theme} />
        </nav>

        <div className="p-4 bg-blue-500/10 mx-4 mb-6 rounded-xl border border-blue-500/20 pointer-events-none">
          <div className="flex items-center gap-2 mb-2 text-blue-400 font-bold text-xs uppercase tracking-tighter">
            <Activity size={14} />
            <span>Active Monitors: {gpuData.filter(s => s.is_online).length}</span>
          </div>
          <div className={`w-full ${appConfig.theme === "light" ? "bg-slate-200" : "bg-white/10"} h-1.5 rounded-full overflow-hidden`}>
            <motion.div initial={{ width: 0 }} animate={{ width: "100%" }} className="bg-blue-500 h-full rounded-full" />
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 z-20">
        <header className={`h-14 flex items-center justify-between px-6 border-b border-[var(--dashboard-border)] relative bg-[var(--header-bg)] z-50 select-none pointer-events-auto`} data-tauri-drag-region="true">
          <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 pointer-events-none">{activeTab}</div>
          <div className="flex items-center gap-0.5 z-[60] pointer-events-auto">
            <WindowButton icon={<Minus size={16} />} onClick={() => appWindow.minimize()} theme={appConfig.theme} />
            <WindowButton icon={isMaximized ? <Square size={12} /> : <Square size={14} />} onClick={toggleMaximize} theme={appConfig.theme} />
            <WindowButton icon={<X size={18} />} onClick={handleClose} hoverColor="hover:bg-red-500" theme={appConfig.theme} />
          </div>
        </header>

        <div className={`flex-1 overflow-y-auto p-8 custom-scrollbar relative z-0 ${appConfig.theme === "light" ? "bg-transparent" : "bg-black/5"}`} data-no-drag="true">
          <AnimatePresence mode="wait">
            {activeTab === "dashboard" && (
              <motion.div key="dashboard" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <StatCard label="Online Servers" value={gpuData.filter(s => s.is_online).length.toString()} icon={<Server className="text-blue-400" />} theme={appConfig.theme} />
                <StatCard label="Total GPUs" value={gpuData.reduce((acc, s) => acc + s.gpu_list.length, 0).toString()} icon={<Cpu className="text-purple-400" />} theme={appConfig.theme} />
                <StatCard label="Active Deadlines" value={deadlines.length.toString()} icon={<Calendar className="text-emerald-400" />} theme={appConfig.theme} />
                
                <div className="col-span-full mt-4">
                  <h2 className={`text-xl font-bold tracking-tight mb-6 ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Quick Launch Widgets</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="cursor-pointer" onClick={() => handleToggleWidget("widget-gpu-default", "GPU Monitor")}>
                      <WidgetPreviewCard 
                        title="GPU Monitor Widget" 
                        status={activeWidgets.includes("widget-gpu-default") ? "Active" : "Ready"} 
                        detail="Floating desktop monitoring for GPU clusters" 
                        trend={activeWidgets.includes("widget-gpu-default") ? "Close" : "Launch"} 
                        color="blue" 
                        theme={appConfig.theme}
                      />
                    </div>
                    <div className="cursor-pointer" onClick={() => handleToggleWidget("widget-deadlines-default", "Deadlines")}>
                      <WidgetPreviewCard 
                        title="Paper Deadline Widget" 
                        status={activeWidgets.includes("widget-deadlines-default") ? "Active" : "Ready"} 
                        detail="Track conference deadlines on your desktop" 
                        trend={activeWidgets.includes("widget-deadlines-default") ? "Close" : "Launch"} 
                        color="purple" 
                        theme={appConfig.theme}
                      />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "gpu" && (
              <motion.div key="gpu" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="flex items-center justify-between mb-8">
                  <h2 className={`text-2xl font-bold tracking-tight ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>GPU Cluster Status</h2>
                </div>
                <div className="space-y-6">
                  {gpuData.length === 0 ? (
                    <div className="p-12 text-center bg-black/5 rounded-3xl border border-dashed border-white/10 text-slate-500 font-bold uppercase tracking-widest text-xs">No active data. Configure servers in Settings.</div>
                  ) : gpuData.map((server, idx) => (
                    <div key={idx} className={`border border-[var(--dashboard-border)] rounded-2xl p-6 shadow-sm ${appConfig.theme === "light" ? "bg-white" : "bg-white/5"}`}>
                      <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${server.is_online ? "bg-emerald-500 shadow-[0_0_10px_#10b981]" : "bg-red-500"}`} />
                          <span className={`text-lg font-bold ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>{server.host}</span>
                        </div>
                        <span className="text-xs font-black text-slate-500 uppercase tracking-widest">{server.gpu_list.length} GPUs Detected</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {server.gpu_list.map((gpu: any, gidx: number) => (
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
                      {server.error && <p className="mt-4 text-[10px] text-red-400/60 italic font-medium break-all">{server.error}</p>}
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {activeTab === "deadlines" && (
              <motion.div key="deadlines" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <h2 className={`text-2xl font-bold tracking-tight mb-8 ${appConfig.theme === "light" ? "text-slate-900" : "text-white"}`}>Upcoming Conferences</h2>
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

            {activeTab === "settings" && (
              <SettingsPanel 
                gpuConfig={gpuConfig} 
                paperConfig={paperConfig} 
                appConfig={appConfig}
                onSaveGpu={saveGpuConfig} 
                onSavePaper={savePaperConfig}
                onSaveApp={saveAppConfig}
                togglePin={togglePinConference}
                isAutostart={isAutostart}
                onToggleAutostart={async () => {
                  if (isAutostart) await disable();
                  else await enable();
                  setIsAutostart(await isEnabled());
                }}
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

  useEffect(() => {
    const unlisten = listen<any>("gpu_update", (event) => {
      const item = event.payload;
      setServerData(prev => {
        const index = prev.findIndex(s => s.host === item.host);
        if (index === -1) return [...prev, item];
        const next = [...prev];
        next[index] = item;
        return next;
      });
    });
    return () => {
      unlisten.then(f => f());
    };
  }, []);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <Cpu size={16} className="text-blue-400" />
        <span className="text-xs font-black uppercase tracking-widest text-white">GPU Monitor</span>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-6">
        {serverData.length > 0 ? serverData.map((server: any, idx: number) => {
          // Group GPUs by Job ID
          const groups: Record<string, any[]> = {};
          server.gpu_list.forEach((gpu: any) => {
            const gid = gpu.job_id || "SYSTEM";
            if (!groups[gid]) groups[gid] = [];
            groups[gid].push(gpu);
          });

          return (
            <div key={idx} className="space-y-4">
              <div className="flex items-center justify-between border-l-2 border-white/10 pl-2">
                <span className="text-[10px] font-black text-slate-300 uppercase tracking-tighter">{server.host}</span>
                {server.is_online ? (
                  <span className="text-[7px] text-emerald-400 font-black uppercase opacity-60">Online</span>
                ) : (
                  <span className="text-[7px] text-red-400 font-black uppercase opacity-60">Offline</span>
                )}
              </div>
              
              {server.error && <div className="text-[9px] text-red-400/60 font-medium italic px-2">{server.error}</div>}
              
              <div className="space-y-3 pl-2">
                {Object.entries(groups).map(([jobId, gpus]) => (
                  <div key={jobId} className="space-y-1.5">
                    {jobId !== "SYSTEM" && (
                      <div className="flex items-center gap-1 text-[8px] font-black text-blue-400/70 uppercase tracking-widest pl-1 group/job">
                        <Activity size={10} /> JOB: {jobId}
                        <div className="ml-0 flex items-center">
                          <CopyButton text={jobId} />
                        </div>
                      </div>
                    )}
                    <div className="grid grid-cols-4 gap-1.5">
                      {gpus.map((gpu, i) => (
                        <div key={i} className="space-y-1 bg-white/5 p-1.5 rounded-lg border border-white/5 flex flex-col justify-center min-w-0">
                          <div className="flex justify-between items-center text-[8px] font-black tracking-tighter">
                            <span className="text-slate-500">#{i}</span>
                            <span className="text-white">{gpu.util}%</span>
                          </div>
                          <div className="h-1 w-full bg-black/40 rounded-full overflow-hidden">
                            <motion.div initial={{ width: 0 }} animate={{ width: `${gpu.util}%` }} className="h-full bg-blue-500 rounded-full" />
                          </div>
                          <div className="flex justify-between items-center text-[7px] font-bold tracking-tighter tabular-nums">
                            <span className="text-slate-500">{(gpu.mem_used / 1024).toFixed(0)}G</span>
                            <span className="text-slate-400">{(gpu.power || 0).toFixed(0)}W</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        }) : (
          <div className="text-xs text-slate-500 italic text-center mt-4">Waiting for backend...</div>
        )}
      </div>
    </div>
  );
}

function DeadlineWidgetContent() {
  const [deadlines, setDeadlines] = useState<any[]>([]);
  const [paperConfig, setPaperConfig] = useState<any>({});

  useEffect(() => {
    const fetchConfig = async () => {
      const pc = await invoke("get_paper_config");
      setPaperConfig(pc);
    };
    const fetchDeadlines = async () => {
      const dls: any = await invoke("get_deadlines");
      setDeadlines(dls);
    };
    fetchConfig();
    fetchDeadlines();

    const unlisten = listen<any[]>("paper_update", (event) => {
      setDeadlines(event.payload);
      fetchConfig(); // Sync config when update happens
    });
    return () => {
      unlisten.then(f => f());
    };
  }, []);

  const pinnedTitles = paperConfig.pinned_titles || [];
  const pinnedList = deadlines.filter(d => pinnedTitles.includes(d.title));
  
  // If no pinned, show the closest one
  const displayList = pinnedList.length > 0 ? pinnedList : (deadlines.length > 0 ? [deadlines[0]] : []);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <Trophy size={16} className="text-amber-400" />
        <span className="text-xs font-black uppercase tracking-widest text-white">Deadlines</span>
      </div>
      
      <div className="flex-1 overflow-y-auto custom-scrollbar pr-1 w-full space-y-2">
        {displayList.length > 0 ? displayList.map((dl, idx) => (
          <div key={idx} className="bg-white/5 rounded-xl p-3 border border-white/5 relative overflow-hidden group transition-all hover:bg-white/10">
            <div className="flex items-center justify-between relative z-10">
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-black text-white truncate">{dl.title} {dl.year}</span>
                  <span className="text-[8px] text-slate-500 font-bold uppercase tracking-widest px-1.5 py-0.5 rounded-md bg-white/5">{dl.sub}</span>
                </div>
                <div className="flex items-center gap-1.5 mt-1 opacity-60">
                  <span className="text-[8px] text-slate-400 font-bold truncate">📍 {dl.place || "Online"}</span>
                </div>
              </div>
              <div className="text-right flex-shrink-0 pl-2">
                <div className="text-[10px] font-black text-amber-400 tabular-nums bg-amber-500/10 px-2 py-1 rounded-lg border border-amber-500/10">
                  <DeadlineCountdown date={dl.deadline_utc} />
                </div>
              </div>
            </div>
            {/* Background Accent */}
            <div className="absolute top-0 right-0 w-16 h-16 bg-purple-500/5 rounded-full blur-xl -mr-8 -mt-8 pointer-events-none" />
          </div>
        )) : (
          <div className="text-[10px] text-slate-500 italic text-center mt-8">No conferences tracked.</div>
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

function WidgetPreviewCard({ title, status, detail, trend, color, theme = "dark" }: { title: string, status: string, detail: string, trend: string, color: string, theme?: string }) {
  const isLight = theme === "light";
  const colors: Record<string, string> = isLight ? {
    blue: "bg-blue-50 border-blue-200/60 text-blue-600",
    purple: "bg-purple-50 border-purple-200/60 text-purple-600",
  } : {
    blue: "from-blue-600/10 to-blue-900/10 border-blue-500/20 text-blue-400",
    purple: "from-purple-600/10 to-purple-900/10 border-purple-500/20 text-purple-400",
  };
  return (
    <div className={`p-6 rounded-2xl border ${isLight ? colors[color] : `bg-gradient-to-br ${colors[color]}`} transition-all ${isLight ? "hover:shadow-md hover:border-blue-300" : "hover:border-white/30"} group cursor-pointer shadow-sm`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className={`font-bold text-lg tracking-tight ${isLight ? "text-slate-900" : "text-white"}`}>{title}</h3>
        <span className={`text-[10px] uppercase font-black px-2.5 py-1 rounded-lg border ${isLight ? "bg-white border-slate-200 text-slate-600" : "bg-white/5 border-white/5 text-slate-400"}`}>{status}</span>
      </div>
      <div className={`text-sm mb-6 font-medium h-10 ${isLight ? "text-slate-600" : "text-slate-400"}`}>{detail}</div>
      <div className="flex items-center justify-between">
        <div className={`text-xs font-black tracking-wider uppercase ${isLight ? "text-slate-900" : "text-white"}`}>{trend}</div>
        <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${isLight ? "bg-slate-200/50 text-slate-600 group-hover:bg-slate-200" : "bg-white/5 text-white group-hover:bg-white/10"}`}><ChevronRight size={16} /></div>
      </div>
    </div>
  );
}


function SettingsPanel({ gpuConfig, paperConfig, appConfig, onSaveGpu, onSavePaper, onSaveApp, isAutostart, onToggleAutostart }: any) {
  const [localGpu, setLocalGpu] = useState(gpuConfig);
  const [localPaper, setLocalPaper] = useState(paperConfig);

  useEffect(() => {
    setLocalGpu(gpuConfig);
  }, [gpuConfig]);

  useEffect(() => {
    setLocalPaper(paperConfig);
  }, [paperConfig]);

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
        </div>
      </section>
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
    </motion.div>
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
