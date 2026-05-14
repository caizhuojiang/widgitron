use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::Read;
use std::net::TcpStream;
use std::path::PathBuf;
use std::time::Duration;
use ssh2::Session;
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};
use tauri::tray::{TrayIconBuilder};
use chrono::{DateTime, Utc};
use std::sync::Arc;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

// --- Config Models ---
#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct ServerConfig {
    host: String,
    port: Option<u16>,
    user: Option<String>,
    password: Option<String>,
    key_file: Option<String>,
    use_slurm: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct GpuConfig {
    servers: Vec<ServerConfig>,
    update_interval: Option<u64>,
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct PaperConfig {
    update_interval: Option<u64>,
    max_deadlines: Option<usize>,
    show_past_deadlines: Option<bool>,
    filter_by_rank: Option<Vec<String>>,
    filter_by_sub: Option<Vec<String>>,
    pinned_titles: Option<Vec<String>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ArxivConfig {
    pub keywords: Vec<String>,
    pub categories: Vec<String>,
    pub update_interval: u64,
    pub show_card_hints: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ArxivPaper {
    pub id: String,
    pub title: String,
    pub summary: String,
    pub authors: Vec<String>,
    pub link: String,
    pub published: String,
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct AppConfig {
    theme: Option<String>,
    always_on_top: Option<HashMap<String, bool>>,
    embedded: Option<HashMap<String, bool>>,
    gpu_enabled: Option<bool>,
    deadline_enabled: Option<bool>,
    arxiv_enabled: Option<bool>,
    hide_on_startup: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct ColorConfig {
    name: String,
    value: String,
    opacity: Option<f32>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct WidgetTheme {
    id: String,
    name: String,
    is_default: bool,
    bg_color: String,
    bg_opacity: f32,
    text_colors: Vec<ColorConfig>,
    primary_colors: Vec<ColorConfig>,
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct WidgetThemeConfig {
    themes: Vec<WidgetTheme>,
    assignments: HashMap<String, String>, // widget_id -> theme_id
}

// --- Payload Models ---
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GpuInfo {
    name: String,
    mem_used: f32,
    mem_total: f32,
    util: f32,
    temp: Option<f32>,
    power: Option<f32>,
    job_id: Option<String>,
    node: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ServerGpuData {
    host: String,
    is_online: bool,
    pub gpu_list: Vec<GpuInfo>,
    pub error: Option<String>,
    pub last_update: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PaperDeadlineInfo {
    title: String,
    year: String,
    deadline_utc: String, // ISO8601
    timezone: String,
    rank: String,
    sub: String,
    place: String,
    link: String,
}

#[derive(Debug, Deserialize)]
struct YamlConfTimeline {
    deadline: Option<String>,
    // comment: Option<String>,
}

#[derive(Debug, Deserialize)]
struct YamlConfYear {
    year: String,
    timezone: Option<String>,
    place: Option<String>,
    link: Option<String>,
    timeline: Option<Vec<YamlConfTimeline>>,
}

#[derive(Debug, Deserialize)]
struct YamlConfRank {
    ccf: Option<String>,
}

#[derive(Debug, Deserialize)]
struct YamlConfItem {
    title: String,
    sub: Option<String>,
    rank: Option<YamlConfRank>,
    confs: Option<Vec<YamlConfYear>>,
}

struct GlobalState {
    deadlines: Arc<std::sync::Mutex<Vec<PaperDeadlineInfo>>>,
    gpu_data: Arc<std::sync::Mutex<HashMap<String, ServerGpuData>>>,
    last_yaml: Arc<std::sync::Mutex<Option<String>>>,
    active_monitors: Arc<std::sync::Mutex<HashMap<String, tokio::task::JoinHandle<()>>>>,
    active_workers: Arc<std::sync::Mutex<HashMap<String, tokio::task::JoinHandle<()>>>>,
    arxiv_papers: Arc<std::sync::Mutex<Vec<ArxivPaper>>>,
}

// Helper to find/initialize config file
fn get_config_path(app: &AppHandle, filename: &str) -> PathBuf {
    // 1. Try next to EXE (Highest priority, works for portable/bin usage)
    if let Ok(mut p) = std::env::current_exe() {
        p.pop();
        p.push("configs");
        let path = p.join(filename);
        if p.exists() { return path; }
        
        // Try to create it if it doesn't exist (only if writable)
        if fs::create_dir_all(&p).is_ok() {
            // Check if we can actually write to it
            let test_file = p.join(".write_test");
            if fs::write(&test_file, "").is_ok() {
                let _ = fs::remove_file(test_file);
                return path;
            }
        }
    }

    // 2. Fallback to AppData (Standard for installed apps in C:\Program Files)
    let config_dir = app.path().app_config_dir().unwrap_or_else(|_| {
        std::env::current_dir().unwrap_or_default().join("configs")
    });
    
    if !config_dir.exists() {
        let _ = fs::create_dir_all(&config_dir);
    }
    
    let path = config_dir.join(filename);
    
    // If doesn't exist in AppData, try to copy from bundled resources
    if !path.exists() {
        if let Ok(resource_dir) = app.path().resource_dir() {
            let resource_path = resource_dir.join("configs").join(filename);
            if resource_path.exists() {
                let _ = fs::copy(resource_path, &path);
            }
        }
    }
    
    path
}

fn parse_nvidia_smi_output(output: &str) -> Vec<GpuInfo> {
    let mut list = Vec::new();
    for line in output.lines() {
        let mut node_id = None;
        let mut content = line;

        // Handle Slurm --label output: "0: name, used, ..."
        if line.contains(": ") {
            let parts: Vec<&str> = line.splitn(2, ": ").collect();
            if parts.len() == 2 && parts[0].chars().all(|c| c.is_numeric()) {
                node_id = Some(parts[0].trim().to_string());
                content = parts[1];
            }
        }

        let parts: Vec<&str> = content.split(',').collect();
        if parts.len() >= 6 {
            list.push(GpuInfo {
                node: node_id,
                name: parts[0].trim().to_string(),
                mem_used: parts[1].trim().parse().unwrap_or(0.0),
                mem_total: parts[2].trim().parse().unwrap_or(0.0),
                util: parts[3].trim().parse().unwrap_or(0.0),
                temp: parts[4].trim().parse().ok(),
                power: parts[5].trim().parse().ok(),
                job_id: None,
            });
        }
    }
    list
}

// --- GPU Polling Task (Persistent Workers) ---

fn ssh_authenticate(sess: &mut Session, s: &ServerConfig) -> Result<(), String> {
    let user = s.user.as_deref().unwrap_or("root");
    if let Some(key_path) = &s.key_file {
        let expanded = shellexpand::tilde(key_path).to_string();
        sess.userauth_pubkey_file(user, None, std::path::Path::new(&expanded), None).map_err(|e| format!("Key auth failed: {}", e))?;
    } else if let Some(pass) = &s.password {
        sess.userauth_password(user, pass).map_err(|e| format!("Password auth failed: {}", e))?;
    } else {
        let default_key = shellexpand::tilde("~/.ssh/id_rsa").to_string();
        if std::path::Path::new(&default_key).exists() {
            sess.userauth_pubkey_file(user, None, std::path::Path::new(&default_key), None).map_err(|e| format!("Default key auth failed: {}", e))?;
        } else {
            let _ = sess.userauth_agent(user);
        }
    }
    Ok(())
}

fn start_ssh_monitor_task(
    app: AppHandle,
    state: Arc<GlobalState>,
    server: ServerConfig,
    jid: Option<String>,
    node_count: Option<String>,
    interval: u64,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let smi_cmd = "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw --format=csv,noheader,nounits";
        loop {
            let app_inner = app.clone();
            let state_inner = state.clone();
            let s_m = server.clone();
            let j_m = jid.clone();
            let n_m = node_count.clone();
            
            let res = tokio::task::spawn_blocking(move || -> Option<()> {
                let host_id = format!("{}:{}", s_m.host, s_m.port.unwrap_or(22));
                // Use a standard connect but set a read timeout immediately to avoid forever hangs
                let tcp = TcpStream::connect(&host_id).ok()?;
                let _ = tcp.set_read_timeout(Some(Duration::from_secs(60)));
                
                let mut sess = Session::new().ok()?;
                sess.set_timeout(30000); // 30s timeout for SSH operations
                sess.set_tcp_stream(tcp);
                sess.handshake().ok()?;
                
                ssh_authenticate(&mut sess, &s_m).ok()?;
                
                let mut channel = sess.channel_session().ok()?;
                let watch_cmd = match &j_m {
                    Some(id) => {
                        let n_arg = match &n_m {
                            Some(n) => format!("-n {} --ntasks-per-node=1", n),
                            None => "--ntasks-per-node=1".to_string(),
                        };
                        format!("srun --jobid {} --overlap {} --label --job-name=widgitron-gpu sh -c 'while true; do {}; echo \"END_BATCH\"; sleep {}; done'", id, n_arg, smi_cmd, interval)
                    },
                    None => format!("sh -c 'while true; do {}; echo \"END_BATCH\"; sleep {}; done'", smi_cmd, interval),
                };
                
                if channel.exec(&watch_cmd).is_err() { return None; }
                
                let mut task_batches: HashMap<String, String> = HashMap::new();
                let reader = std::io::BufReader::new(channel);
                use std::io::BufRead;
                for line in reader.lines() {
                    if let Ok(l) = line {
                        // Identify task ID from Slurm --label prefix (e.g., "0: ...")
                        let task_id = if l.contains(": ") {
                            let parts: Vec<&str> = l.splitn(2, ": ").collect();
                            if parts.len() == 2 && parts[0].trim().chars().all(|c| c.is_numeric()) {
                                parts[0].trim().to_string()
                            } else { "default".to_string() }
                        } else { "default".to_string() };

                        if l.contains("END_BATCH") {
                            let app_config_path = get_config_path(&app_inner, "app_config.json");
                            let app_config_str = fs::read_to_string(&app_config_path).unwrap_or_default();
                            let app_config: AppConfig = serde_json::from_str(&app_config_str).unwrap_or_default();
                            if !app_config.gpu_enabled.unwrap_or(true) {
                                return None;
                            }

                            let batch = task_batches.entry(task_id.clone()).or_default();
                            let mut parsed = parse_nvidia_smi_output(batch);
                            if !parsed.is_empty() {
                                for p in &mut parsed { p.job_id = j_m.clone(); }
                                
                                let node_to_replace = parsed[0].node.clone();

                                if let Ok(mut state_gpu) = state_inner.gpu_data.lock() {
                                    let data = state_gpu.entry(s_m.host.clone()).or_insert(ServerGpuData {
                                        host: s_m.host.clone(), is_online: true, gpu_list: vec![], error: None, last_update: None
                                    });
                                    
                                    if let Some(node) = node_to_replace {
                                        data.gpu_list.retain(|g| !(g.job_id == j_m && g.node == Some(node.clone())));
                                    } else {
                                        data.gpu_list.retain(|g| g.job_id != j_m);
                                    }
                                    
                                    data.gpu_list.extend(parsed.clone());
                                    data.last_update = Some(Utc::now().format("%H:%M:%S").to_string());
                                    let data_clone = data.clone();
                                    let _ = app_inner.emit("gpu_update", data_clone);
                                }
                            }
                            batch.clear();
                        } else {
                            let batch = task_batches.entry(task_id).or_default();
                            batch.push_str(&l);
                            batch.push('\n');
                        }
                    }
                }
                Some(())
            }).await;
            
            if res.is_err() || res.unwrap().is_none() {
                tokio::time::sleep(Duration::from_secs(10)).await;
            } else {
                tokio::time::sleep(Duration::from_secs(5)).await;
            }
        }
    })
}

async fn start_gpu_monitor(app: AppHandle, state: Arc<GlobalState>) {
    let smi_cmd = "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw --format=csv,noheader,nounits";

    loop {
        let app_config_path = get_config_path(&app, "app_config.json");
        let app_config_str = fs::read_to_string(&app_config_path).unwrap_or_default();
        let app_config: AppConfig = serde_json::from_str(&app_config_str).unwrap_or_default();
        let gpu_enabled = app_config.gpu_enabled.unwrap_or(true);

        let config_path = get_config_path(&app, "gpu_monitor.json");
        let config_str = fs::read_to_string(&config_path).unwrap_or_default();
        let config: GpuConfig = serde_json::from_str(&config_str).unwrap_or_else(|_| {
            GpuConfig { servers: vec![], update_interval: Some(5) }
        });

        let mut current_server_ids = Vec::new();
        if gpu_enabled {
            for server in &config.servers {
                let server_id = format!("{}:{}", server.host, server.port.unwrap_or(22));
                current_server_ids.push(server_id.clone());

                let mut workers = state.active_workers.lock().unwrap();
                let needs_start = match workers.get(&server_id) {
                    None => true,
                    Some(h) => h.is_finished(),
                };
                if needs_start {
                    let app_inner = app.clone();
                    let state_inner = state.clone();
                    let server_inner = server.clone();
                    let smi_cmd_inner = smi_cmd.to_string();
                    let update_interval = config.update_interval.unwrap_or(5);

                    let handle = tokio::spawn(async move {
                    println!("--- Starting persistent worker for host: {} ---", server_inner.host);
                    let mut session: Option<Session> = None;
                    let mut last_squeue_update = Utc::now() - Duration::from_secs(60);
                    let mut slurm_job_ids: Vec<String> = Vec::new();

                    loop {
                        let res = tokio::task::spawn_blocking({
                            let s = server_inner.clone();
                            let smi = smi_cmd_inner.clone();
                            let state_task = state_inner.clone();
                            let app_task = app_inner.clone();
                            let sess_opt = session.take();
                            let mut job_ids = slurm_job_ids.clone();
                            let squeue_needed = (Utc::now() - last_squeue_update).num_seconds() >= 30;

                            move || -> Result<(Option<Session>, Vec<String>), String> {
                                let mut gpu_data = ServerGpuData {
                                    host: s.host.clone(),
                                    is_online: false,
                                    gpu_list: vec![],
                                    error: None,
                                    last_update: None,
                                };

                                if s.host == "localhost" || s.host == "127.0.0.1" {
                                    // Direct execution to avoid shell (and its .bashrc hooks)
                                    let local_smi_args = ["--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw", "--format=csv,noheader,nounits"];
                                    #[cfg(windows)]
                                    let output = std::process::Command::new("nvidia-smi")
                                        .args(local_smi_args)
                                        .creation_flags(0x08000000) // CREATE_NO_WINDOW
                                        .output();
                                    #[cfg(not(windows))]
                                    let output = std::process::Command::new("nvidia-smi")
                                        .args(local_smi_args)
                                        .output();

                                    match output {
                                        Ok(out) => {
                                            let s_out = String::from_utf8_lossy(&out.stdout);
                                            gpu_data.gpu_list = parse_nvidia_smi_output(&s_out);
                                            gpu_data.is_online = true;
                                        }
                                        Err(e) => { gpu_data.error = Some(format!("Local smi failed: {}", e)); }
                                    }
                                    
                                    if let Ok(mut data) = state_task.gpu_data.lock() {
                                        data.insert(s.host.clone(), gpu_data.clone());
                                    }
                                    let _ = app_task.emit("gpu_update", gpu_data);
                                    
                                    Ok((None, vec![]))
                                } else {
                                    // SSH Logic
                                    let sess = match sess_opt {
                                        Some(sess) => sess,
                                        None => {
                                            let host_id = format!("{}:{}", s.host, s.port.unwrap_or(22));
                                            let tcp = TcpStream::connect(&host_id).map_err(|e| format!("TCP connect failed: {}", e))?;
                                            let _ = tcp.set_read_timeout(Some(Duration::from_secs(30)));
                                            let mut sess = Session::new().map_err(|e| e.to_string())?;
                                            sess.set_timeout(30000);
                                            sess.set_tcp_stream(tcp);
                                            sess.handshake().map_err(|e| format!("SSH handshake failed: {}", e))?;
                                            ssh_authenticate(&mut sess, &s)?;
                                            sess
                                        }
                                    };

                                    gpu_data.is_online = true;
                                    let mut desired_monitor_keys = Vec::new();
                                    
                                    if s.use_slurm.unwrap_or(false) {
                                        let mut job_nodes = HashMap::new();
                                        if squeue_needed {
                                            let user = s.user.as_deref().unwrap_or("root");
                                            if let Ok(mut channel) = sess.channel_session() {
                                                let q_cmd = format!("squeue --me -t RUNNING -h -o \"%A|%D\" 2>/dev/null || squeue -t RUNNING -u $(whoami) -h -o \"%A|%D\" || squeue -t RUNNING -u {} -h -o \"%A|%D\"", user);
                                                if let Ok(_) = channel.exec(&q_cmd) {
                                                    let mut s_q = String::new();
                                                    let _ = channel.read_to_string(&mut s_q);
                                                    let lines: Vec<String> = s_q.lines().map(|l| l.trim().to_string()).filter(|l| !l.is_empty()).collect();
                                                    for line in lines {
                                                        let parts: Vec<&str> = line.split('|').collect();
                                                        if parts.len() >= 2 {
                                                            job_nodes.insert(parts[0].to_string(), parts[1].to_string());
                                                        } else if !line.is_empty() {
                                                            job_nodes.insert(line, "1".to_string());
                                                        }
                                                    }
                                                    job_ids = job_nodes.keys().cloned().collect();
                                                }
                                            }
                                        }
                                        for jid in &job_ids {
                                            let n_count = job_nodes.get(jid).cloned().unwrap_or_else(|| "1".to_string());
                                            desired_monitor_keys.push(format!("{}:{}:{}", s.host, jid, n_count));
                                        }
                                    } else {
                                        desired_monitor_keys.push(format!("{}:node:0", s.host));
                                    }

                                    // Ensure monitor tasks are running
                                    for key in &desired_monitor_keys {
                                        let mut monitors = state_task.active_monitors.lock().unwrap();
                                        let needs_start = match monitors.get(key) {
                                            None => true,
                                            Some(h) => h.is_finished(),
                                        };
                                        if needs_start {
                                            let parts: Vec<&str> = key.split(':').collect();
                                            let (jid, n_count) = if parts.len() >= 3 {
                                                if parts[1] == "node" { (None, None) } 
                                                else { (Some(parts[1].to_string()), Some(parts[2].to_string())) }
                                            } else { (None, None) };

                                            let handle = start_ssh_monitor_task(
                                                app_task.clone(),
                                                state_task.clone(),
                                                s.clone(),
                                                jid,
                                                n_count,
                                                update_interval,
                                            );
                                            monitors.insert(key.clone(), handle);
                                        }
                                    }
                                    
                                    // Cleanup monitors for THIS host that are no longer needed
                                    {
                                        let mut monitors = state_task.active_monitors.lock().unwrap();
                                        let host_prefix = format!("{}:", s.host);
                                        let mut removed_jids = Vec::new();
                                        monitors.retain(|key, handle| {
                                            if key.starts_with(&host_prefix) {
                                                if !desired_monitor_keys.contains(key) {
                                                    handle.abort();
                                                    let parts: Vec<&str> = key.split(':').collect();
                                                    if parts.len() >= 2 && parts[1] != "node" {
                                                        removed_jids.push(parts[1].to_string());
                                                    }
                                                    false
                                                } else {
                                                    true
                                                }
                                            } else {
                                                true
                                            }
                                        });

                                        if !removed_jids.is_empty() {
                                            if let Ok(mut data) = state_task.gpu_data.lock() {
                                                if let Some(server_data) = data.get_mut(&s.host) {
                                                    server_data.gpu_list.retain(|g| {
                                                        if let Some(jid) = &g.job_id {
                                                            !removed_jids.contains(jid)
                                                        } else {
                                                            true
                                                        }
                                                    });
                                                }
                                            }
                                        }
                                    }

                                    // Sync GPU data from global state (updated by background monitors)
                                    if let Ok(data) = state_task.gpu_data.lock() {
                                        if let Some(cached) = data.get(&s.host) {
                                            gpu_data.gpu_list = cached.gpu_list.clone();
                                        }
                                    }

                                    // Fallback poll if no jobs or no data yet
                                    if gpu_data.gpu_list.is_empty() {
                                        if let Ok(mut channel) = sess.channel_session() {
                                            if let Ok(_) = channel.exec(&smi) {
                                                let mut s_out = String::new();
                                                let _ = channel.read_to_string(&mut s_out);
                                                gpu_data.gpu_list = parse_nvidia_smi_output(&s_out);
                                            }
                                        }
                                    }
                                    
                                    if let Ok(mut data) = state_task.gpu_data.lock() {
                                        gpu_data.last_update = Some(Utc::now().format("%H:%M:%S").to_string());
                                        data.insert(s.host.clone(), gpu_data.clone());
                                    } else {
                                        println!("ERROR: gpu_data lock poisoned in main worker for {}", s.host);
                                    }
                                    println!("Main Worker for {} emitting update", s.host);
                                    let _ = app_task.emit("gpu_update", gpu_data);
                                    
                                    Ok((Some(sess), job_ids))
                                }
                            }
                        }).await;

                        match res {
                            Ok(Ok((sess, jobs))) => {
                                session = sess;
                                slurm_job_ids = jobs;
                                if (Utc::now() - last_squeue_update).num_seconds() >= 30 {
                                    last_squeue_update = Utc::now();
                                }
                            }
                            _ => {
                                println!("Worker for {} failed or disconnected, retrying in 10s", server_inner.host);
                                session = None;
                                tokio::time::sleep(Duration::from_secs(10)).await;
                            }
                        }

                        tokio::time::sleep(Duration::from_secs(update_interval)).await;
                    }
                });
                workers.insert(server_id, handle);
            }
        }
    } else {
        // Clear data when disabled
        if let Ok(mut data) = state.gpu_data.lock() {
            data.clear();
        }
        let _ = app.emit("gpu_clear", ());
    }

    // Cleanup workers for removed servers
    {
        let mut workers = state.active_workers.lock().unwrap();
            workers.retain(|id, handle| {
                if !current_server_ids.contains(id) {
                    handle.abort();
                    // Also cleanup monitors for this host
                    let host = id.split(':').next().unwrap_or_default();
                    if !host.is_empty() {
                        let mut monitors = state.active_monitors.lock().unwrap();
                        let prefix = format!("{}:", host);
                        monitors.retain(|k, h| {
                            if k.starts_with(&prefix) {
                                h.abort();
                                false
                            } else { true }
                        });
                    }
                    false
                } else {
                    true
                }
            });
        }

        tokio::time::sleep(Duration::from_secs(1)).await; // Re-check config every 1s
    }
}


fn process_deadlines(app: AppHandle, state: Arc<GlobalState>, config: PaperConfig, text: String) {
    let app_inner = app.clone();
    let config_inner = config.clone();
    let state_inner = state.clone();

    // Offload heavy YAML parsing and processing to blocking thread
    tokio::task::spawn_blocking(move || {
        match serde_yaml::from_str::<Vec<YamlConfItem>>(&text) {
            Ok(items) => {
                let mut deadlines = Vec::new();
                let now = Utc::now();

                for item in items {
                    let rank = item.rank.and_then(|r| r.ccf).unwrap_or_else(|| "N".to_string());
                    let sub = item.sub.unwrap_or_else(|| "Unknown".to_string());

                    if let Some(allowed) = &config_inner.filter_by_rank {
                        if !allowed.is_empty() && !allowed.contains(&rank) { continue; }
                    }
                    if let Some(allowed) = &config_inner.filter_by_sub {
                        if !allowed.is_empty() && !allowed.contains(&sub) { continue; }
                    }

                    if let Some(confs) = item.confs {
                        for conf in confs {
                            if let Some(timeline) = conf.timeline {
                                for t in timeline {
                                    if let Some(dl) = t.deadline {
                                        if dl == "TBD" { continue; }

                                        let mut dt_str = dl.clone();
                                        if dt_str.len() == 10 {
                                            dt_str.push_str("T23:59:59Z");
                                        } else if !dt_str.ends_with('Z') && !dt_str.contains('+') {
                                            dt_str.push_str("Z");
                                        }
                                        dt_str = dt_str.replace(" ", "T");

                                        if let Ok(parsed) = DateTime::parse_from_rfc3339(&dt_str) {
                                            let utc_dt = parsed.with_timezone(&Utc);
                                            if utc_dt >= now || config_inner.show_past_deadlines.unwrap_or(false) {
                                                deadlines.push(PaperDeadlineInfo {
                                                    title: item.title.clone(),
                                                    year: conf.year.clone(),
                                                    deadline_utc: utc_dt.to_rfc3339(),
                                                    timezone: conf.timezone.clone().unwrap_or_else(|| "UTC".into()),
                                                    rank: rank.clone(),
                                                    sub: sub.clone(),
                                                    place: conf.place.clone().unwrap_or_default(),
                                                    link: conf.link.clone().unwrap_or_default(),
                                                });
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                deadlines.sort_by(|a, b| a.deadline_utc.cmp(&b.deadline_utc));
                deadlines.truncate(config_inner.max_deadlines.unwrap_or(50));

                {
                    if let Ok(mut state_deadlines) = state_inner.deadlines.lock() {
                        *state_deadlines = deadlines.clone();
                    }
                }

                if !deadlines.is_empty() {
                    let _ = app_inner.emit("paper_update", &deadlines);
                }
            }
            Err(e) => { println!("Error parsing Paper Deadlines YAML: {}", e); }
        }
    });
}

// --- Paper Deadline Polling Task ---
async fn start_paper_monitor(app: AppHandle, state: Arc<GlobalState>) {
    loop {
        let app_config_path = get_config_path(&app, "app_config.json");
        let app_config_str = fs::read_to_string(&app_config_path).unwrap_or_default();
        let app_config: AppConfig = serde_json::from_str(&app_config_str).unwrap_or_default();
        
        if !app_config.deadline_enabled.unwrap_or(true) {
            if let Ok(mut state_deadlines) = state.deadlines.lock() {
                state_deadlines.clear();
            }
            let _ = app.emit("paper_update", Vec::<PaperDeadlineInfo>::new());
            tokio::time::sleep(Duration::from_secs(5)).await;
            continue;
        }

        let config_path = get_config_path(&app, "paper_deadline.json");
        let config_str = fs::read_to_string(&config_path).unwrap_or_default();
        let config: PaperConfig = serde_json::from_str(&config_str).unwrap_or(PaperConfig { 
            update_interval: Some(3600), max_deadlines: Some(50), show_past_deadlines: Some(false), filter_by_rank: None, filter_by_sub: None, pinned_titles: None 
        });

        // Use exact URL from Python code
        let url = "https://ccfddl.github.io/conference/allconf.yml";
        match reqwest::get(url).await {
            Ok(res) => {
                if let Ok(text) = res.text().await {
                    println!("Fetched Paper Deadlines YAML ({} bytes)", text.len());
                    {
                        if let Ok(mut last) = state.last_yaml.lock() {
                            *last = Some(text.clone());
                        }
                    }
                    process_deadlines(app.clone(), state.clone(), config.clone(), text);
                }
            }
            Err(e) => { println!("Error fetching paper deadlines: {}", e); }
        }

        let interval = config.update_interval.unwrap_or(3600);
        for _ in 0..interval {
            let config_str = fs::read_to_string(&app_config_path).unwrap_or_default();
            let ac: AppConfig = serde_json::from_str(&config_str).unwrap_or_default();
            if !ac.deadline_enabled.unwrap_or(true) { break; }
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }
}

// --- Commands ---

#[tauri::command]
async fn save_gpu_config(app: AppHandle, config: GpuConfig) -> Result<(), String> {
    let path = get_config_path(&app, "gpu_monitor.json");
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(path, content).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn save_paper_config(app: AppHandle, state: tauri::State<'_, GlobalState>, config: PaperConfig) -> Result<(), String> {
    let path = get_config_path(&app, "paper_deadline.json");
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(path, content).map_err(|e| e.to_string())?;

    // Trigger immediate UI refresh if we have cached YAML
    let yaml = {
        let last = state.last_yaml.lock().map_err(|e| e.to_string())?;
        last.clone()
    };
    if let Some(text) = yaml {
        let state_arc = Arc::new(GlobalState {
            deadlines: state.deadlines.clone(),
            gpu_data: state.gpu_data.clone(),
            last_yaml: state.last_yaml.clone(),
            active_monitors: state.active_monitors.clone(),
            active_workers: state.active_workers.clone(),
            arxiv_papers: state.arxiv_papers.clone(),
        });
        process_deadlines(app, state_arc, config, text);
    }
    Ok(())
}

#[tauri::command]
async fn get_gpu_config(app: AppHandle) -> Result<GpuConfig, String> {
    let path = get_config_path(&app, "gpu_monitor.json");
    if !path.exists() { return Ok(GpuConfig::default()); }
    let config_str = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&config_str).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_paper_config(app: AppHandle) -> Result<PaperConfig, String> {
    let path = get_config_path(&app, "paper_deadline.json");
    if !path.exists() { 
        return Ok(PaperConfig { 
            update_interval: Some(3600), max_deadlines: Some(50), show_past_deadlines: Some(false), filter_by_rank: None, filter_by_sub: None, pinned_titles: None 
        }); 
    }
    let config_str = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&config_str).map_err(|e| e.to_string())
}

#[tauri::command]
async fn save_app_config(app: AppHandle, config: AppConfig) -> Result<(), String> {
    let path = get_config_path(&app, "app_config.json");
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(path, content).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn get_app_config(app: AppHandle) -> Result<AppConfig, String> {
    let path = get_config_path(&app, "app_config.json");
    if !path.exists() { 
        return Ok(AppConfig { 
            theme: Some("dark".into()), 
            always_on_top: None, 
            embedded: None,
            gpu_enabled: Some(true),
            deadline_enabled: Some(true),
            arxiv_enabled: Some(true),
            hide_on_startup: Some(false),
        }); 
    }
    let config_str = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&config_str).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_deadlines(state: tauri::State<'_, GlobalState>) -> Result<Vec<PaperDeadlineInfo>, String> {
    let deadlines = state.deadlines.lock().map_err(|e| e.to_string())?;
    Ok(deadlines.clone())
}

#[tauri::command]
async fn get_gpu_data(state: tauri::State<'_, GlobalState>) -> Result<Vec<ServerGpuData>, String> {
    let gpu_data = state.gpu_data.lock().map_err(|e| e.to_string())?;
    Ok(gpu_data.values().cloned().collect())
}

#[tauri::command]
async fn show_main(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
    if let Some(tray_menu) = app.get_webview_window("tray-menu") {
        let _ = tray_menu.hide();
    }
    Ok(())
}

#[tauri::command]
async fn exit_app(app: tauri::AppHandle) {
    app.exit(0);
}

#[tauri::command]
async fn get_theme_config(app: AppHandle) -> Result<WidgetThemeConfig, String> {
    let path = get_config_path(&app, "widget_themes.json");
    let gpu_default = WidgetTheme {
        id: "theme-gpu-default".into(),
        name: "GPU Default".into(),
        is_default: true,
        bg_color: "#0f172a".into(),
        bg_opacity: 0.95,
        text_colors: vec![
            ColorConfig { name: "Main Text".into(), value: "#ffffff".into(), opacity: Some(1.0) },
            ColorConfig { name: "Sub Text".into(), value: "#94a3b8".into(), opacity: Some(0.6) },
        ],
        primary_colors: vec![
            ColorConfig { name: "Accent".into(), value: "#3b82f6".into(), opacity: Some(1.0) },
            ColorConfig { name: "Success".into(), value: "#10b981".into(), opacity: Some(1.0) },
            ColorConfig { name: "Warning".into(), value: "#f59e0b".into(), opacity: Some(1.0) },
            ColorConfig { name: "Danger".into(), value: "#ef4444".into(), opacity: Some(1.0) },
        ],
    };
    let deadline_default = WidgetTheme {
        id: "theme-deadline-default".into(),
        name: "Deadline Default".into(),
        is_default: true,
        bg_color: "#0f172a".into(),
        bg_opacity: 0.95,
        text_colors: vec![
            ColorConfig { name: "Main Text".into(), value: "#ffffff".into(), opacity: Some(1.0) },
            ColorConfig { name: "Sub Text".into(), value: "#94a3b8".into(), opacity: Some(0.6) },
        ],
        primary_colors: vec![
            ColorConfig { name: "Accent".into(), value: "#8b5cf6".into(), opacity: Some(1.0) },
            ColorConfig { name: "Highlight".into(), value: "#f59e0b".into(), opacity: Some(1.0) },
        ],
    };
    let gpu_transparent = WidgetTheme {
        id: "theme-gpu-transparent".into(),
        name: "GPU Transparent".into(),
        is_default: true,
        bg_color: "#ffffff".into(),
        bg_opacity: 0.1,
        text_colors: vec![
            ColorConfig { name: "Main Text".into(), value: "#000000".into(), opacity: Some(1.0) },
            ColorConfig { name: "Sub Text".into(), value: "#000000".into(), opacity: Some(1.0) },
        ],
        primary_colors: vec![
            ColorConfig { name: "Accent".into(), value: "#3b82f6".into(), opacity: Some(1.0) },
            ColorConfig { name: "Success".into(), value: "#10b981".into(), opacity: Some(1.0) },
            ColorConfig { name: "Warning".into(), value: "#f59e0b".into(), opacity: Some(1.0) },
            ColorConfig { name: "Danger".into(), value: "#ef4444".into(), opacity: Some(1.0) },
        ],
    };
    let deadline_transparent = WidgetTheme {
        id: "theme-deadline-transparent".into(),
        name: "Deadline Transparent".into(),
        is_default: true,
        bg_color: "#ffffff".into(),
        bg_opacity: 0.1,
        text_colors: vec![
            ColorConfig { name: "Main Text".into(), value: "#000000".into(), opacity: Some(1.0) },
            ColorConfig { name: "Sub Text".into(), value: "#000000".into(), opacity: Some(1.0) },
        ],
        primary_colors: vec![
            ColorConfig { name: "Accent".into(), value: "#8b5cf6".into(), opacity: Some(1.0) },
            ColorConfig { name: "Highlight".into(), value: "#f59e0b".into(), opacity: Some(1.0) },
        ],
    };
    let arxiv_default = WidgetTheme {
        id: "theme-arxiv-default".into(),
        name: "Arxiv Radar Default".into(),
        is_default: true,
        bg_color: "#0f172a".into(),
        bg_opacity: 0.8,
        text_colors: vec![
            ColorConfig { name: "Main Text".into(), value: "#ffffff".into(), opacity: Some(1.0) },
            ColorConfig { name: "Sub Text".into(), value: "#94a3b8".into(), opacity: Some(0.8) },
        ],
        primary_colors: vec![
            ColorConfig { name: "Accent".into(), value: "#ec4899".into(), opacity: Some(1.0) },
        ],
    };
    let arxiv_transparent = WidgetTheme {
        id: "theme-arxiv-transparent".into(),
        name: "Arxiv Transparent".into(),
        is_default: true,
        bg_color: "#ffffff".into(),
        bg_opacity: 0.1,
        text_colors: vec![
            ColorConfig { name: "Main Text".into(), value: "#000000".into(), opacity: Some(1.0) },
            ColorConfig { name: "Sub Text".into(), value: "#000000".into(), opacity: Some(1.0) },
        ],
        primary_colors: vec![
            ColorConfig { name: "Accent".into(), value: "#ec4899".into(), opacity: Some(1.0) },
        ],
    };

    if !path.exists() {
        let mut assignments = HashMap::new();
        assignments.insert("widget-gpu-default".into(), "theme-gpu-default".into());
        assignments.insert("widget-deadlines-default".into(), "theme-deadline-default".into());
        assignments.insert("widget-arxiv-default".into(), "theme-arxiv-default".into());
        return Ok(WidgetThemeConfig {
            themes: vec![gpu_default.clone(), deadline_default.clone(), arxiv_default.clone(), gpu_transparent.clone(), deadline_transparent.clone(), arxiv_transparent.clone()],
            assignments,
        });
    }

    let config_str = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    
    // Try current format
    match serde_json::from_str::<WidgetThemeConfig>(&config_str) {
        Ok(mut config) => {
            // Ensure defaults are present and updated
            config.themes.retain(|t| !t.id.ends_with("-transparent"));
            if !config.themes.iter().any(|t| t.id == "theme-gpu-default") {
                config.themes.push(gpu_default.clone());
            }
            if !config.themes.iter().any(|t| t.id == "theme-deadline-default") {
                config.themes.push(deadline_default.clone());
            }
            if !config.themes.iter().any(|t| t.id == "theme-arxiv-default") {
                config.themes.push(arxiv_default.clone());
            }
            config.themes.push(gpu_transparent.clone());
            config.themes.push(deadline_transparent.clone());
            config.themes.push(arxiv_transparent.clone());

            if !config.assignments.contains_key("widget-gpu-default") || config.assignments.get("widget-gpu-default").map_or(true, |s| s.is_empty()) {
                config.assignments.insert("widget-gpu-default".into(), "theme-gpu-default".into());
            }
            if !config.assignments.contains_key("widget-deadlines-default") || config.assignments.get("widget-deadlines-default").map_or(true, |s| s.is_empty()) {
                config.assignments.insert("widget-deadlines-default".into(), "theme-deadline-default".into());
            }
            if !config.assignments.contains_key("widget-arxiv-default") || config.assignments.get("widget-arxiv-default").map_or(true, |s| s.is_empty()) {
                config.assignments.insert("widget-arxiv-default".into(), "theme-arxiv-default".into());
            }
            Ok(config)
        },
        Err(_) => {
            // Migration from old format (text_color: String)
            let mut val: serde_json::Value = serde_json::from_str(&config_str).map_err(|e| e.to_string())?;
            if let Some(themes) = val.get_mut("themes").and_then(|t| t.as_array_mut()) {
                for theme in themes {
                    let old_color = theme.get("text_color").cloned();
                    if let Some(color_val) = old_color {
                        if color_val.is_string() {
                            let obj = theme.as_object_mut().unwrap();
                            obj.insert("text_colors".into(), serde_json::json!([
                                { "name": "Main Text", "value": color_val, "opacity": 1.0 },
                                { "name": "Sub Text", "value": "#94a3b8", "opacity": 0.6 }
                            ]));
                            obj.remove("text_color");
                        }
                    }
                }
            }
            let mut migrated: WidgetThemeConfig = serde_json::from_value(val).map_err(|e| e.to_string())?;
            
            // Ensure defaults and update transparent themes
            migrated.themes.retain(|t| !t.id.ends_with("-transparent"));
            if !migrated.themes.iter().any(|t| t.id == "theme-gpu-default") {
                migrated.themes.push(gpu_default);
            }
            if !migrated.themes.iter().any(|t| t.id == "theme-deadline-default") {
                migrated.themes.push(deadline_default);
            }
            if !migrated.themes.iter().any(|t| t.id == "theme-arxiv-default") {
                migrated.themes.push(arxiv_default);
            }
            migrated.themes.push(gpu_transparent);
            migrated.themes.push(deadline_transparent);
            migrated.themes.push(arxiv_transparent);

            if !migrated.assignments.contains_key("widget-gpu-default") || migrated.assignments.get("widget-gpu-default").map_or(true, |s| s.is_empty()) {
                migrated.assignments.insert("widget-gpu-default".into(), "theme-gpu-default".into());
            }
            if !migrated.assignments.contains_key("widget-deadlines-default") || migrated.assignments.get("widget-deadlines-default").map_or(true, |s| s.is_empty()) {
                migrated.assignments.insert("widget-deadlines-default".into(), "theme-deadline-default".into());
            }
            if !migrated.assignments.contains_key("widget-arxiv-default") || migrated.assignments.get("widget-arxiv-default").map_or(true, |s| s.is_empty()) {
                migrated.assignments.insert("widget-arxiv-default".into(), "theme-arxiv-default".into());
            }

            let _ = fs::write(&path, serde_json::to_string_pretty(&migrated).unwrap());
            Ok(migrated)
        }
    }
}

#[tauri::command]
async fn save_theme_config(app: AppHandle, config: WidgetThemeConfig) -> Result<(), String> {
    let path = get_config_path(&app, "widget_themes.json");
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(path, content).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn create_widget(app: AppHandle, id: String, title: String) -> Result<(), String> {
    println!("Creating/Showing widget: {} ({})", title, id);
    if let Some(win) = app.get_webview_window(&id) {
        let _ = win.show();
        let _ = win.set_focus();
        return Ok(());
    }
    
    let builder = WebviewWindowBuilder::new(&app, &id, WebviewUrl::App("index.html".into()))
        .title(title)
        .inner_size(320.0, 400.0)
        .decorations(false)
        .resizable(true)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true);

    match builder.build() {
        Ok(win) => {
            let _ = win.show();
            let _ = win.set_focus();
            Ok(())
        },
        Err(e) => Err(e.to_string())
    }
}

#[tauri::command]
async fn close_widget(app: AppHandle, id: String) -> Result<(), String> {
    if let Some(win) = app.get_webview_window(&id) {
        let _ = win.hide();
    }
    Ok(())
}

#[tauri::command]
async fn toggle_widget(app: AppHandle, id: String, title: String) -> Result<(), String> {
    if let Some(win) = app.get_webview_window(&id) {
        if win.is_visible().unwrap_or(false) {
            let _ = win.hide();
        } else {
            let _ = win.show();
            let _ = win.set_focus();
        }
    } else {
        create_widget(app.clone(), id, title).await?;
    }
    Ok(())
}

#[cfg(windows)]
unsafe extern "system" fn enum_window(hwnd: windows::Win32::Foundation::HWND, lparam: windows::Win32::Foundation::LPARAM) -> windows::core::BOOL {
    use windows::Win32::UI::WindowsAndMessaging::{FindWindowExW, GetClassNameW};
    use windows::Win32::Foundation::HWND;
    use windows::core::BOOL;
    
    let p_workerw = lparam.0 as *mut HWND;
    let mut class_name = [0u16; 256];
    let len = GetClassNameW(hwnd, &mut class_name);
    let name = String::from_utf16_lossy(&class_name[..len as usize]);
    
    if name == "WorkerW" {
        let shell_view = FindWindowExW(Some(hwnd), None, windows::core::w!("SHELLDLL_DefView"), None).ok();
        if let Some(sv) = shell_view {
            // Parent directly to SHELLDLL_DefView
            *p_workerw = sv;
            return BOOL(0);
        }
    }
    BOOL(1)
}

#[tauri::command]
async fn set_desktop_mode(app: AppHandle, label: String, enabled: bool) -> Result<(), String> {
    if let Some(win) = app.get_webview_window(&label) {
        #[cfg(windows)]
        {
            use windows::Win32::Foundation::{HWND, LPARAM, WPARAM};
            use windows::Win32::UI::WindowsAndMessaging::{
                EnumWindows, FindWindowW, FindWindowExW, SendMessageTimeoutW, SetParent, SMTO_NORMAL,
                GetWindowLongW, SetWindowLongW, GWL_EXSTYLE, WS_EX_TOPMOST, SetWindowPos,
                HWND_TOP, SWP_NOSIZE, SWP_SHOWWINDOW, SWP_FRAMECHANGED, GWL_STYLE, WS_CHILD, WS_POPUP,
            };

            let hwnd_raw = win.hwnd().map_err(|e| e.to_string())?;
            let hwnd = HWND(hwnd_raw.0 as *mut _);

            if enabled {
                println!("Enabling desktop mode for {}", label);
                
                use windows::Win32::Foundation::RECT;
                use windows::Win32::UI::WindowsAndMessaging::GetWindowRect;
                let mut rect = RECT::default();
                unsafe { let _ = GetWindowRect(hwnd, &mut rect); }

                let progman = unsafe { FindWindowW(windows::core::w!("Progman"), None) }.ok();
                let mut result = 0;
                if let Some(p) = progman {
                    unsafe {
                        SendMessageTimeoutW(p, 0x052C, WPARAM(0), LPARAM(0), SMTO_NORMAL, 1000, Some(&mut result));
                    }
                }

                // Find SHELLDLL_DefView anywhere
                let mut shell_view = HWND(std::ptr::null_mut());
                
                // Check Progman first
                if let Some(p) = progman {
                    if let Ok(sv) = unsafe { FindWindowExW(Some(p), None, windows::core::w!("SHELLDLL_DefView"), None) } {
                        shell_view = sv;
                    }
                }
                
                // Check WorkerW if not found
                if shell_view.0.is_null() {
                    let mut workerw = HWND(std::ptr::null_mut());
                    unsafe {
                        let _ = EnumWindows(Some(enum_window), LPARAM(&mut workerw as *mut HWND as isize));
                    }
                    if !workerw.0.is_null() {
                        shell_view = workerw; // enum_window now returns SHELLDLL_DefView directly
                    }
                }

                let target_parent = if !shell_view.0.is_null() {
                    use windows::Win32::UI::WindowsAndMessaging::GetParent as GetWindowParent;
                    unsafe { GetWindowParent(shell_view).ok() }
                } else if let Some(p) = progman {
                    Some(p)
                } else {
                    None
                };

                if let Some(parent) = target_parent {
                    println!("Found target desktop handle (Progman/WorkerW): {:?}", parent);
                    
                    use windows::Win32::Foundation::POINT;
                    let pt = POINT { x: rect.left, y: rect.top };
                    
                    unsafe {
                        // 1. Manually calculate client coordinates to bypass GDI DPI scaling bugs on multi-monitors
                        use windows::Win32::UI::WindowsAndMessaging::GetWindowRect;
                        use windows::Win32::Foundation::RECT;
                        let mut parent_rect = RECT::default();
                        let _ = GetWindowRect(parent, &mut parent_rect);
                        
                        let client_x = rect.left - parent_rect.left;
                        let client_y = rect.top - parent_rect.top;

                        // 2. Adjust Styles BEFORE SetParent
                        let style = GetWindowLongW(hwnd, GWL_STYLE);
                        let clean_style = (style | WS_CHILD.0 as i32 | 0x04000000 | 0x02000000 | 0x10000000) & !(WS_POPUP.0 as i32);
                        let _ = SetWindowLongW(hwnd, GWL_STYLE, clean_style);
                        
                        let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE);
                        let _ = SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style & !(WS_EX_TOPMOST.0 as i32 | 0x00000020));

                        // 3. Parent to desktop
                        let _ = SetParent(hwnd, Some(parent));
                        
                        // 4. Update position (use SWP_NOSIZE so we don't break Tauri's internal resize logic)
                        use windows::Win32::UI::WindowsAndMessaging::{SetWindowPos, SWP_SHOWWINDOW, SWP_FRAMECHANGED, HWND_TOP, SWP_NOSIZE};
                        let _ = SetWindowPos(hwnd, Some(HWND_TOP), client_x, client_y, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW | SWP_FRAMECHANGED);
                        
                        use windows::Win32::UI::WindowsAndMessaging::{ShowWindow, SW_SHOW};
                        let _ = ShowWindow(hwnd, SW_SHOW);
                        
                        use windows::Win32::UI::Input::KeyboardAndMouse::SetFocus;
                        let _ = SetFocus(Some(hwnd));
                    }
                    println!("Desktop mode set successfully at local ({}, {})", pt.x, pt.y);

                    // 5. Force a repaint via Tauri API to fix transparent bug without breaking resize grip
                    if let Ok(size) = win.inner_size() {
                        let _ = win.set_size(tauri::Size::Physical(tauri::PhysicalSize { width: size.width, height: size.height + 1 }));
                        let win_clone = win.clone();
                        tokio::spawn(async move {
                            tokio::time::sleep(std::time::Duration::from_millis(50)).await;
                            let _ = win_clone.set_size(tauri::Size::Physical(tauri::PhysicalSize { width: size.width, height: size.height }));
                        });
                    }
                } else {
                    println!("Failed to find desktop handle");
                }
            } else {
                println!("Disabling desktop mode for {}", label);
                use windows::Win32::Foundation::RECT;
                use windows::Win32::UI::WindowsAndMessaging::GetWindowRect;
                let mut rect = RECT::default();
                unsafe { let _ = GetWindowRect(hwnd, &mut rect); }

                unsafe {
                    let _ = SetParent(hwnd, None);
                    
                    let style = GetWindowLongW(hwnd, GWL_STYLE);
                    let _ = SetWindowLongW(hwnd, GWL_STYLE, (style & !(WS_CHILD.0 as i32)) | WS_POPUP.0 as i32);
                    
                    // Restore position to where it was in the desktop
                    // Use HWND_TOP to ensure it's visible as a normal window after exiting desktop mode
                    let _ = SetWindowPos(hwnd, Some(HWND_TOP), rect.left, rect.top, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW | SWP_FRAMECHANGED);
                }
            }
        }
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
// Arxiv Polling Task
async fn start_arxiv_monitor(app: AppHandle, state: Arc<GlobalState>) {
    let client = reqwest::Client::builder()
        .user_agent("Widgitron/1.0 (contact: researcher@widgitron.app)")
        .timeout(Duration::from_secs(30))
        .build()
        .unwrap_or_default();

    loop {
        let app_config_path = get_config_path(&app, "app_config.json");
        let app_config_str = fs::read_to_string(&app_config_path).unwrap_or_default();
        let app_config: AppConfig = serde_json::from_str(&app_config_str).unwrap_or_default();
        
        let config_path = get_config_path(&app, "arxiv_config.json");
        let config_str = fs::read_to_string(&config_path).unwrap_or_default();
        let config: ArxivConfig = serde_json::from_str(&config_str).unwrap_or_else(|_| ArxivConfig {
            keywords: vec!["gaussian".into(), "vla".into(), "llm".into()],
            categories: vec!["cs".into()],
            update_interval: 43200, // 12 hours
            show_card_hints: Some(true),
        });
        
        let interval = config.update_interval;

        if !app_config.arxiv_enabled.unwrap_or(true) {
            if let Ok(mut state_papers) = state.arxiv_papers.lock() {
                state_papers.clear();
            }
            let _ = app.emit("arxiv_update", Vec::<ArxivPaper>::new());
            
            for _ in 0..interval {
                let ac_str = fs::read_to_string(&app_config_path).unwrap_or_default();
                let ac: AppConfig = serde_json::from_str(&ac_str).unwrap_or_default();
                if ac.arxiv_enabled.unwrap_or(true) { break; }
                tokio::time::sleep(Duration::from_secs(1)).await;
            }
            continue;
        }

        let kws = &config.keywords;
        let cats = &config.categories;
        
        // Build query for multiple categories and keywords
        let cat_query = if cats.is_empty() {
            "cat:cs*".to_string()
        } else {
            let joined = cats.iter().map(|c| format!("cat:{}*", c)).collect::<Vec<_>>().join("+OR+");
            format!("({})", joined)
        };

        let mut query = cat_query;
        if !kws.is_empty() {
            let kw_query = kws.iter().map(|k| format!("all:{}", k)).collect::<Vec<_>>().join("+OR+");
            query = format!("{}+AND+({})", query, kw_query);
        }
        
        let url = format!("https://export.arxiv.org/api/query?search_query={}&start=0&max_results=50&sortBy=submittedDate&sortOrder=descending", query);
        
        match client.get(&url).send().await {
            Ok(res) => {
                if let Ok(xml) = res.text().await {
                    let mut reader = quick_xml::Reader::from_str(&xml);
                    reader.config_mut().trim_text(true);
                    
                    let mut buf = Vec::new();
                    let mut papers = Vec::new();
                    
                    let mut current_paper = ArxivPaper {
                        id: String::new(), title: String::new(), summary: String::new(),
                        authors: Vec::new(), link: String::new(), published: String::new()
                    };
                    let mut in_entry = false;
                    let mut current_tag = String::new();
                    let mut in_author = false;

                    use quick_xml::events::Event;
                    loop {
                        match reader.read_event_into(&mut buf) {
                            Err(e) => { println!("Error parsing arxiv XML: {}", e); break; },
                            Ok(Event::Eof) => break,
                            Ok(Event::Start(e)) => {
                                let name = String::from_utf8_lossy(e.local_name().as_ref()).into_owned();
                                if name == "entry" {
                                    in_entry = true;
                                    current_paper = ArxivPaper {
                                        id: String::new(), title: String::new(), summary: String::new(),
                                        authors: Vec::new(), link: String::new(), published: String::new()
                                    };
                                } else if in_entry {
                                    if name == "author" { in_author = true; }
                                    else if name == "name" && in_author {
                                        current_paper.authors.push(String::new());
                                    }
                                    else if name == "link" {
                                        let mut is_pdf = false;
                                        let mut href = String::new();
                                        for attr in e.attributes() {
                                            if let Ok(a) = attr {
                                                let key = a.key.local_name();
                                                let k = String::from_utf8_lossy(key.as_ref());
                                                let v = String::from_utf8_lossy(a.value.as_ref());
                                                if k == "title" && v == "pdf" { is_pdf = true; }
                                                if k == "href" { href = v.into_owned(); }
                                            }
                                        }
                                        if is_pdf { current_paper.link = href.replace("http://", "https://"); }
                                        else if current_paper.link.is_empty() { current_paper.link = href.replace("http://", "https://"); } // fallback
                                    }
                                    current_tag = name;
                                }
                            },
                            Ok(Event::Empty(e)) => {
                                let name = String::from_utf8_lossy(e.local_name().as_ref()).into_owned();
                                if in_entry && name == "link" {
                                    let mut is_pdf = false;
                                    let mut href = String::new();
                                    for attr in e.attributes() {
                                        if let Ok(a) = attr {
                                            let key = a.key.local_name();
                                            let k = String::from_utf8_lossy(key.as_ref());
                                            let v = String::from_utf8_lossy(a.value.as_ref());
                                            if k == "title" && v == "pdf" { is_pdf = true; }
                                            if k == "href" { href = v.into_owned(); }
                                        }
                                    }
                                    if is_pdf { current_paper.link = href.replace("http://", "https://"); }
                                    else if current_paper.link.is_empty() { current_paper.link = href.replace("http://", "https://"); }
                                }
                            },
                            Ok(Event::End(e)) => {
                                let name = String::from_utf8_lossy(e.local_name().as_ref()).into_owned();
                                if name == "entry" {
                                    in_entry = false;
                                    papers.push(current_paper.clone());
                                } else if name == "author" {
                                    in_author = false;
                                }
                                current_tag = String::new();
                            },
                            Ok(Event::Text(e)) => {
                                if in_entry {
                                    let text = String::from_utf8_lossy(e.as_ref()).into_owned();
                                    match current_tag.as_str() {
                                        "id" => current_paper.id += &text,
                                        "title" => current_paper.title += &text.replace("\n", " ").replace("  ", " "),
                                        "summary" => current_paper.summary += &text.replace("\n", " ").replace("  ", " "),
                                        "published" => current_paper.published += &text,
                                        "name" if in_author => {
                                            if let Some(last) = current_paper.authors.last_mut() {
                                                *last += &text.trim();
                                            }
                                        },
                                        _ => {}
                                    }
                                }
                            },
                            _ => {}
                        }
                        buf.clear();
                    }
                    
                    // Filter out seen papers
                    let seen_path = get_config_path(&app, "arxiv_seen.json");
                    let seen_str = fs::read_to_string(&seen_path).unwrap_or_default();
                    let seen: Vec<String> = serde_json::from_str(&seen_str).unwrap_or_default();
                    
                    papers.retain(|p| !seen.iter().any(|s| s == p.id.trim()));
                    
                    {
                        if let Ok(mut state_papers) = state.arxiv_papers.lock() {
                            *state_papers = papers.clone();
                        }
                    }
                    if !papers.is_empty() {
                        let _ = app.emit("arxiv_update", &papers);
                    }
                } else {
                    println!("Error reading Arxiv response. Retrying in 60s.");
                    tokio::time::sleep(Duration::from_secs(60)).await;
                    continue;
                }
            }
            Err(e) => { 
                println!("Error fetching Arxiv: {}. Retrying in 60s.", e);
                tokio::time::sleep(Duration::from_secs(60)).await;
                continue;
            }
        }

        let mut last_config_str = fs::read_to_string(&config_path).unwrap_or_default();
        for _ in 0..interval {
            let ac_str = fs::read_to_string(&app_config_path).unwrap_or_default();
            let ac: AppConfig = serde_json::from_str(&ac_str).unwrap_or_default();
            if !ac.arxiv_enabled.unwrap_or(true) { break; }
            
            let current_config_str = fs::read_to_string(&config_path).unwrap_or_default();
            if current_config_str != last_config_str { break; }

            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }
}

#[tauri::command]
async fn save_arxiv_config(app: AppHandle, config: ArxivConfig) -> Result<(), String> {
    let path = get_config_path(&app, "arxiv_config.json");
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(path, content).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn get_arxiv_config(app: AppHandle) -> Result<ArxivConfig, String> {
    let path = get_config_path(&app, "arxiv_config.json");
    if !path.exists() { 
        return Ok(ArxivConfig { 
            keywords: vec!["gaussian".into(), "vla".into(), "llm".into()],
            categories: vec!["cs".into()],
            update_interval: 43200, // 12 hours
            show_card_hints: Some(true),
        }); 
    }
    let config_str = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&config_str).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_arxiv_papers(state: tauri::State<'_, GlobalState>) -> Result<Vec<ArxivPaper>, String> {
    let papers = state.arxiv_papers.lock().map_err(|e| e.to_string())?;
    Ok(papers.clone())
}

#[tauri::command]
async fn mark_arxiv_seen(app: AppHandle, state: tauri::State<'_, GlobalState>, id: String, saved: bool) -> Result<(), String> {
    let seen_path = get_config_path(&app, "arxiv_seen.json");
    let mut seen: Vec<String> = fs::read_to_string(&seen_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default();
    
    if !seen.contains(&id) {
        seen.push(id.clone());
        let _ = fs::write(&seen_path, serde_json::to_string_pretty(&seen).unwrap_or_default());
    }

    if saved {
        let mut paper_to_save = None;
        if let Ok(mut papers) = state.arxiv_papers.lock() {
            if let Some(idx) = papers.iter().position(|p| p.id == id) {
                paper_to_save = Some(papers[idx].clone());
                papers.remove(idx);
            }
        }
        
        if let Some(p) = paper_to_save {
            let saved_path = get_config_path(&app, "arxiv_saved.json");
            let mut saved_papers: Vec<ArxivPaper> = fs::read_to_string(&saved_path)
                .ok()
                .and_then(|s| serde_json::from_str(&s).ok())
                .unwrap_or_default();
            
            saved_papers.push(p.clone());
            let _ = fs::write(&saved_path, serde_json::to_string_pretty(&saved_papers).unwrap_or_default());
        }
    } else {
        let mut paper_to_discard = None;
        if let Ok(mut papers) = state.arxiv_papers.lock() {
            if let Some(idx) = papers.iter().position(|p| p.id == id) {
                paper_to_discard = Some(papers[idx].clone());
                papers.remove(idx);
            }
        }
        
        if let Some(p) = paper_to_discard {
            let discard_path = get_config_path(&app, "arxiv_discarded.json");
            let mut discarded: Vec<ArxivPaper> = fs::read_to_string(&discard_path)
                .ok()
                .and_then(|s| serde_json::from_str(&s).ok())
                .unwrap_or_default();
            discarded.push(p);
            let _ = fs::write(&discard_path, serde_json::to_string_pretty(&discarded).unwrap_or_default());
        }

        if let Ok(papers) = state.arxiv_papers.lock() {
            let _ = app.emit("arxiv_update", &*papers);
        }
    }
    let _ = app.emit("arxiv_saved_update", ());
    let _ = app.emit("arxiv_discarded_update", ());
    Ok(())
}

#[tauri::command]
async fn get_arxiv_saved_papers(app: AppHandle) -> Result<Vec<ArxivPaper>, String> {
    let saved_path = get_config_path(&app, "arxiv_saved.json");
    let saved_papers: Vec<ArxivPaper> = fs::read_to_string(&saved_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default();
    Ok(saved_papers)
}

#[tauri::command]
async fn open_link(app: AppHandle, url: String) -> Result<(), String> {
    println!("Opening link: {}", url);
    use tauri_plugin_opener::OpenerExt;
    app.opener().open_url(&url, None::<String>).map_err(|e| e.to_string())
}

#[tauri::command]
async fn remove_arxiv_saved_paper(app: AppHandle, id: String) -> Result<(), String> {
    let saved_path = get_config_path(&app, "arxiv_saved.json");
    let mut saved_papers: Vec<ArxivPaper> = fs::read_to_string(&saved_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default();
    
    saved_papers.retain(|p| p.id != id);
    let _ = fs::write(&saved_path, serde_json::to_string_pretty(&saved_papers).unwrap_or_default());
    let _ = app.emit("arxiv_saved_update", ());
    Ok(())
}

#[tauri::command]
async fn get_arxiv_discarded_papers(app: AppHandle) -> Result<Vec<ArxivPaper>, String> {
    let path = get_config_path(&app, "arxiv_discarded.json");
    let papers: Vec<ArxivPaper> = fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default();
    Ok(papers)
}

#[tauri::command]
async fn remove_arxiv_discarded_paper(app: AppHandle, id: String) -> Result<(), String> {
    let path = get_config_path(&app, "arxiv_discarded.json");
    let mut papers: Vec<ArxivPaper> = fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default();
    
    papers.retain(|p| p.id != id);
    let _ = fs::write(&path, serde_json::to_string_pretty(&papers).unwrap_or_default());
    let _ = app.emit("arxiv_discarded_update", ());
    Ok(())
}


pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, Some(vec!["--minimized"])))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            create_widget,
            close_widget,
            toggle_widget,
            set_desktop_mode,
            save_gpu_config,
            save_paper_config,
            get_gpu_config,
            get_paper_config,
            get_app_config,
            save_app_config,
            get_deadlines,
            get_gpu_data,
            show_main,
            exit_app,
            get_theme_config,
            save_theme_config,
            save_arxiv_config,
            get_arxiv_config,
            get_arxiv_papers,
            mark_arxiv_seen,
            get_arxiv_saved_papers,
            get_arxiv_discarded_papers,
            open_link,
            remove_arxiv_saved_paper,
            remove_arxiv_discarded_paper
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            
            // Global State
            let state = Arc::new(GlobalState {
                deadlines: Arc::new(std::sync::Mutex::new(Vec::new())),
                gpu_data: Arc::new(std::sync::Mutex::new(HashMap::new())),
                last_yaml: Arc::new(std::sync::Mutex::new(None)),
                active_monitors: Arc::new(std::sync::Mutex::new(HashMap::new())),
                active_workers: Arc::new(std::sync::Mutex::new(HashMap::new())),
                arxiv_papers: Arc::new(std::sync::Mutex::new(Vec::new())),
            });
            app.manage(GlobalState {
                deadlines: state.deadlines.clone(),
                gpu_data: state.gpu_data.clone(),
                last_yaml: state.last_yaml.clone(),
                active_monitors: state.active_monitors.clone(),
                active_workers: state.active_workers.clone(),
                arxiv_papers: state.arxiv_papers.clone(),
            });
            
            // Tray
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    use tauri::tray::{TrayIconEvent, MouseButton};
                    match event {
                        TrayIconEvent::Click { button: MouseButton::Right, .. } => {
                            if let Some(window) = tray.app_handle().get_webview_window("tray-menu") {
                                // Get cursor position to place the menu
                                use windows::Win32::UI::WindowsAndMessaging::GetCursorPos;
                                use windows::Win32::Foundation::POINT;
                                let mut pt = POINT::default();
                                unsafe { let _ = GetCursorPos(&mut pt); }
                                
                                // Set position so bottom-left of menu is at cursor tip
                                let scale_factor = window.scale_factor().unwrap_or(1.0);
                                let physical_height = (70.0 * scale_factor) as i32;
                                let _ = window.set_position(tauri::PhysicalPosition::new(pt.x, pt.y - physical_height));
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        },
                        TrayIconEvent::Click { button: MouseButton::Left, .. } => {
                             // Left click can also toggle or do nothing, keeping it clean
                        },
                        TrayIconEvent::DoubleClick { button: MouseButton::Left, .. } => {
                            if let Some(window) = tray.app_handle().get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        },
                        _ => {}
                    }
                })
                .build(&handle)?;

            // Bug fix: Explicitly hide tray-menu window on startup
            if let Some(tray_menu) = app.get_webview_window("tray-menu") {
                let _ = tray_menu.hide();
            }

            // Background Workers
            let app_clone1 = handle.clone();
            let state_clone1 = state.clone();
            tauri::async_runtime::spawn(async move {
                start_gpu_monitor(app_clone1, state_clone1).await;
            });

            let app_clone2 = handle.clone();
            let state_clone2 = state.clone();
            tauri::async_runtime::spawn(async move {
                start_paper_monitor(app_clone2, state_clone2).await;
            });

            // Auto-start Widgets (respecting Master Switch)
            let app_config_path = get_config_path(&handle, "app_config.json");
            let app_config_str = fs::read_to_string(&app_config_path).unwrap_or_default();
            let app_config: AppConfig = serde_json::from_str(&app_config_str).unwrap_or_default();

            // Ensure Main Window is visible (or hidden based on config)
            if let Some(main_win) = handle.get_webview_window("main") {
                if !app_config.hide_on_startup.unwrap_or(false) {
                    let _ = main_win.show();
                    let _ = main_win.set_focus();
                } else {
                    let _ = main_win.hide();
                }
            }
            
            let handle_gpu = handle.clone();
            let handle_deadline = handle.clone();
            let handle_arxiv = handle.clone();
            
            tauri::async_runtime::spawn(async move {
                if app_config.gpu_enabled.unwrap_or(true) {
                    let _ = create_widget(handle_gpu, "widget-gpu-default".into(), "GPU Monitor".into()).await;
                }
                if app_config.deadline_enabled.unwrap_or(true) {
                    let _ = create_widget(handle_deadline, "widget-deadlines-default".into(), "Deadlines".into()).await;
                }
                if app_config.arxiv_enabled.unwrap_or(true) {
                    let _ = create_widget(handle_arxiv, "widget-arxiv-default".into(), "Arxiv Radar".into()).await;
                }
            });

            let app_clone3 = handle.clone();
            let state_clone3 = state.clone();
            tauri::async_runtime::spawn(async move {
                start_arxiv_monitor(app_clone3, state_clone3).await;
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
