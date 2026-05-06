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

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct AppConfig {
    theme: Option<String>, // "light" or "dark"
    always_on_top: Option<HashMap<String, bool>>,
    embedded: Option<HashMap<String, bool>>,
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
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ServerGpuData {
    host: String,
    is_online: bool,
    gpu_list: Vec<GpuInfo>,
    error: Option<String>,
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
        let parts: Vec<&str> = line.split(',').collect();
        if parts.len() >= 6 {
            list.push(GpuInfo {
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
    interval: u64,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let smi_cmd = "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw --format=csv,noheader,nounits";
        loop {
            let app_inner = app.clone();
            let state_inner = state.clone();
            let s_m = server.clone();
            let j_m = jid.clone();
            
            let res = tokio::task::spawn_blocking(move || -> Option<()> {
                let host_id = format!("{}:{}", s_m.host, s_m.port.unwrap_or(22));
                let tcp = TcpStream::connect(&host_id).ok()?;
                let mut sess = Session::new().ok()?;
                sess.set_tcp_stream(tcp);
                sess.handshake().ok()?;
                
                ssh_authenticate(&mut sess, &s_m).ok()?;
                
                let mut batch = String::new();
                let mut channel = sess.channel_session().ok()?;
                let watch_cmd = match &j_m {
                    Some(id) => format!("srun --jobid {} --overlap --ntasks=1 --job-name=widgitron-gpu sh -c 'while true; do {}; echo \"END_BATCH\"; sleep {}; done'", id, smi_cmd, interval),
                    None => format!("sh -c 'while true; do {}; echo \"END_BATCH\"; sleep {}; done'", smi_cmd, interval),
                };
                
                if channel.exec(&watch_cmd).is_err() { return None; }
                
                let reader = std::io::BufReader::new(channel);
                use std::io::BufRead;
                for line in reader.lines() {
                    if let Ok(l) = line {
                        if l.trim() == "END_BATCH" {
                            let mut parsed = parse_nvidia_smi_output(&batch);
                            if !parsed.is_empty() {
                                for p in &mut parsed { p.job_id = j_m.clone(); }
                                if let Ok(mut state_gpu) = state_inner.gpu_data.lock() {
                                    let data = state_gpu.entry(s_m.host.clone()).or_insert(ServerGpuData {
                                        host: s_m.host.clone(), is_online: true, gpu_list: vec![], error: None,
                                    });
                                    data.gpu_list.retain(|g| g.job_id != j_m);
                                    data.gpu_list.extend(parsed.clone());
                                    let data_clone = data.clone();
                                    let _ = app_inner.emit("gpu_update", data_clone);
                                }
                            }
                            batch.clear();
                        } else {
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
        let config_path = get_config_path(&app, "gpu_monitor.json");
        let config_str = fs::read_to_string(&config_path).unwrap_or_default();
        let config: GpuConfig = serde_json::from_str(&config_str).unwrap_or_else(|_| {
            GpuConfig { servers: vec![], update_interval: Some(5) }
        });

        let mut current_server_ids = Vec::new();
        for server in &config.servers {
            let server_id = format!("{}:{}", server.host, server.port.unwrap_or(22));
            current_server_ids.push(server_id.clone());

            let mut workers = state.active_workers.lock().unwrap();
            if !workers.contains_key(&server_id) {
                let app_inner = app.clone();
                let state_inner = state.clone();
                let server_inner = server.clone();
                let smi_cmd_inner = smi_cmd.to_string();
                let update_interval = config.update_interval.unwrap_or(5);

                let handle = tokio::spawn(async move {
                    println!("Starting persistent worker for {}", server_inner.host);
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
                                            let mut sess = Session::new().map_err(|e| e.to_string())?;
                                            sess.set_tcp_stream(tcp);
                                            sess.handshake().map_err(|e| format!("SSH handshake failed: {}", e))?;
                                            ssh_authenticate(&mut sess, &s)?;
                                            sess
                                        }
                                    };

                                    gpu_data.is_online = true;
                                    let mut desired_monitor_keys = Vec::new();
                                    
                                    if s.use_slurm.unwrap_or(false) {
                                        if squeue_needed {
                                            let user = s.user.as_deref().unwrap_or("root");
                                            if let Ok(mut channel) = sess.channel_session() {
                                                let q_cmd = format!("squeue --me -t RUNNING -h -o %A 2>/dev/null || squeue -t RUNNING -u $(whoami) -h -o %A || squeue -t RUNNING -u {} -h -o %A", user);
                                                if let Ok(_) = channel.exec(&q_cmd) {
                                                    let mut s_q = String::new();
                                                    let _ = channel.read_to_string(&mut s_q);
                                                    job_ids = s_q.lines().map(|l| l.trim().to_string()).filter(|l| !l.is_empty()).collect();
                                                }
                                            }
                                        }
                                        for jid in &job_ids {
                                            desired_monitor_keys.push(format!("{}:{}", s.host, jid));
                                        }
                                    } else {
                                        desired_monitor_keys.push(format!("{}:node", s.host));
                                    }

                                    // Ensure monitor tasks are running
                                    for key in &desired_monitor_keys {
                                        let mut monitors = state_task.active_monitors.lock().unwrap();
                                        if !monitors.contains_key(key) {
                                            let jid = if key.ends_with(":node") { None } else { Some(key.split(':').last().unwrap().to_string()) };
                                            let handle = start_ssh_monitor_task(
                                                app_task.clone(),
                                                state_task.clone(),
                                                s.clone(),
                                                jid,
                                                update_interval,
                                            );
                                            monitors.insert(key.clone(), handle);
                                        }
                                    }
                                    
                                    // Cleanup monitors for THIS host that are no longer needed
                                    {
                                        let mut monitors = state_task.active_monitors.lock().unwrap();
                                        let host_prefix = format!("{}:", s.host);
                                        monitors.retain(|key, handle| {
                                            if key.starts_with(&host_prefix) {
                                                if !desired_monitor_keys.contains(key) {
                                                    handle.abort();
                                                    false
                                                } else {
                                                    true
                                                }
                                            } else {
                                                true
                                            }
                                        });
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
                                        data.insert(s.host.clone(), gpu_data.clone());
                                    }
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

        tokio::time::sleep(Duration::from_secs(10)).await; // Re-check config every 10s
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

        tokio::time::sleep(Duration::from_secs(config.update_interval.unwrap_or(3600))).await;
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
    if !path.exists() { return Ok(AppConfig { theme: Some("dark".into()), always_on_top: None, embedded: None }); }
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
fn create_widget(app: AppHandle, id: String, title: String) {
    println!("Creating widget: {} ({})", title, id);
    if let Some(win) = app.get_webview_window(&id) {
        let _ = win.show();
        let _ = win.set_focus();
        return;
    }
    match WebviewWindowBuilder::new(&app, id, WebviewUrl::App("index.html".into()))
        .title(title)
        .inner_size(320.0, 400.0)
        .decorations(false)
        .resizable(true)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .build() {
            Ok(_) => println!("Widget created successfully"),
            Err(e) => println!("Failed to create widget: {}", e),
        }
}

#[tauri::command]
fn toggle_widget(app: AppHandle, id: String, title: String) {
    if let Some(win) = app.get_webview_window(&id) {
        if win.is_visible().unwrap_or(false) {
            let _ = win.hide();
        } else {
            let _ = win.show();
            let _ = win.set_focus();
        }
    } else {
        create_widget(app.clone(), id, title);
    }
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
                    use windows::Win32::Graphics::Gdi::ScreenToClient;
                    let mut pt = POINT { x: rect.left, y: rect.top };
                    
                    unsafe {
                        // 1. Map screen coordinates to target parent's client coordinates
                        let _ = ScreenToClient(parent, &mut pt);

                        // 2. Adjust Styles BEFORE SetParent
                        // WS_CLIPSIBLINGS (0x04000000), WS_CLIPCHILDREN (0x02000000), WS_VISIBLE (0x10000000)
                        let style = GetWindowLongW(hwnd, GWL_STYLE);
                        let clean_style = (style | WS_CHILD.0 as i32 | 0x04000000 | 0x02000000 | 0x10000000) & !(WS_POPUP.0 as i32);
                        let _ = SetWindowLongW(hwnd, GWL_STYLE, clean_style);
                        
                        let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE);
                        // Explicitly remove WS_EX_TOPMOST and WS_EX_TRANSPARENT (0x00000020)
                        let _ = SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style & !(WS_EX_TOPMOST.0 as i32 | 0x00000020));

                        // 3. Parent to desktop
                        let _ = SetParent(hwnd, Some(parent));
                        
                        // 4. Update position and show
                        let _ = SetWindowPos(hwnd, Some(HWND_TOP), pt.x, pt.y, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW | SWP_FRAMECHANGED);
                        
                        use windows::Win32::UI::WindowsAndMessaging::{ShowWindow, SW_SHOW};
                        let _ = ShowWindow(hwnd, SW_SHOW);
                        
                        use windows::Win32::UI::Input::KeyboardAndMouse::SetFocus;
                        let _ = SetFocus(Some(hwnd));
                    }
                    println!("Desktop mode set successfully at local ({}, {})", pt.x, pt.y);
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
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, Some(vec!["--minimized"])))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            create_widget,
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
            exit_app
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
            });
            app.manage(GlobalState {
                deadlines: state.deadlines.clone(),
                gpu_data: state.gpu_data.clone(),
                last_yaml: state.last_yaml.clone(),
                active_monitors: state.active_monitors.clone(),
                active_workers: state.active_workers.clone(),
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

            // Ensure Main Window is visible
            if let Some(main_win) = handle.get_webview_window("main") {
                let _ = main_win.show();
                let _ = main_win.set_focus();
            }

            // Auto-start Widgets
            create_widget(handle.clone(), "widget-gpu-default".into(), "GPU Monitor".into());
            create_widget(handle.clone(), "widget-deadlines-default".into(), "Deadlines".into());

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
