"""
GPU Monitor Widget
A desktop widget for monitoring GPU usage on remote servers via SSH
"""

import paramiko
import os
import json
import time
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QFont
from plyer import notification

from core.desktop_widget import DesktopWidget


def load_gpu_config():
    """Load GPU Monitor configuration"""
    config_path = 'configs/gpu_monitor.json'
    if not os.path.exists(config_path):
        return {
            'servers': [],
            'update_interval': 1,
            'idle_threshold': 300,
            'widget_size': [400, 600]
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Load configuration
GPU_CONFIG = load_gpu_config()
SERVERS = GPU_CONFIG.get('servers', [])
WIDGET_SIZE = tuple(GPU_CONFIG.get('widget_size', [400, 600]))
UPDATE_INTERVAL = GPU_CONFIG.get('update_interval', 1)
IDLE_THRESHOLD = GPU_CONFIG.get('idle_threshold', 300)


def get_server_id(server):
    """Generate unique server identifier using host:port format"""
    port = server.get('port', 22)
    return f"{server['host']}:{port}"


class GPUWorker(QThread):
    """Background thread for fetching GPU information from servers"""
    data_ready = pyqtSignal(dict)  # Signal to emit GPU data
    
    def __init__(self, servers):
        super().__init__()
        self.servers = servers
        self.running = True
    
    def run(self):
        while self.running:
            gpu_data = {}
            for server in self.servers:
                info = self.get_gpu_info(server)
                gpu_data[get_server_id(server)] = info
            self.data_ready.emit(gpu_data)
            time.sleep(UPDATE_INTERVAL)
    
    def get_gpu_info(self, server):
        try:
            # Handle localhost directly without SSH
            if server['host'] in ['localhost', '127.0.0.1']:
                import subprocess
                result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True)
                output = result.stdout.strip()
            elif server.get('proxy'):
                # Use subprocess for proxy connections to avoid Windows paramiko issues
                import subprocess
                proxy = server['proxy']
                proxy_host = proxy['host']
                proxy_port = proxy.get('port', 22)
                proxy_user = proxy['user']
                proxy_command = f"ssh -W %h:%p {proxy_user}@{proxy_host} -p {proxy_port}"
                if proxy.get('key_file'):
                    proxy_command += f" -i {proxy['key_file']}"
                port = server.get('port', 22)
                cmd = ['ssh', '-o', f'ProxyCommand={proxy_command}', f"{server['user']}@{server['host']}", '-p', str(port), 'nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits']
                result = subprocess.run(cmd, capture_output=True, text=True)
                output = result.stdout.strip()
            else:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect with password or key
                port = server.get('port', 22)
                if server.get('key_file') and os.path.exists(server['key_file']):
                    ssh.connect(server['host'], port=port, username=server['user'], key_filename=server['key_file'])
                else:
                    default_key = os.path.expanduser('~/.ssh/id_rsa')
                    if os.path.exists(default_key):
                        ssh.connect(server['host'], port=port, username=server['user'], key_filename=default_key)
                    else:
                        ssh.connect(server['host'], port=port, username=server['user'], password=server['password'])
                
                stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits')
                output = stdout.read().decode('utf-8').strip()
                ssh.close()
            
            if output:
                lines = output.split('\n')
                gpu_info = ""
                for line in lines:
                    parts = line.split(',')
                    if len(parts) >= 4:
                        name = parts[0].strip()
                        mem_used = parts[1].strip()
                        mem_total = parts[2].strip()
                        util = parts[3].strip()
                        
                        try:
                            util_float = float(util)
                            # Update last active time in main thread
                        except ValueError:
                            pass
                        
                        gpu_info += f"GPU: {name}\nMemory: {mem_used}/{mem_total} MB\nUtilization: {util}%\n"
                    else:
                        gpu_info += f"Invalid GPU data: {line}\n"
                
                return gpu_info.strip()
            else:
                return "No GPU data"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def stop(self):
        self.running = False


class GPUMonitor(DesktopWidget):
    """GPU Monitoring Widget"""
    
    def __init__(self):
        # Use config path for GPU monitor
        config_path = 'configs/gpu_monitor.json'
        super().__init__(WIDGET_SIZE, config_path=config_path)
        self.setWindowTitle("GPU Monitor")
        
        # Remove the manual position setting since base class handles it
        # Get screen geometry for positioning is now handled in base class
        
        # Layout for server info - set on content container
        self.layout = QVBoxLayout(self.content_container)
        self.server_labels = {}
        
        for server in SERVERS:
            server_id = get_server_id(server)
            server_label = QLabel(f"{server_id}: Initializing...")
            server_label.setFont(QFont("Arial", 10))
            server_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 5px;")
            self.layout.addWidget(server_label)
            self.server_labels[server_id] = server_label
        
        self.content_container.setLayout(self.layout)
        self.content_container.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        
        self.last_active_times = {get_server_id(server): time.time() for server in SERVERS}
        self.monitoring = True
        self.is_topmost = False  # Start not topmost
        self.is_locked = True  # Start locked
        self.drag_position = None  # For window dragging
        self.resize_edge = None  # For resizing
        
        # Create GPU worker thread
        self.worker = GPUWorker(SERVERS)
        self.worker.data_ready.connect(self.update_gpu_display)
        self.worker.start()
        
        # Idle check timer
        self.idle_timer = QTimer()
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start(10000)  # Check every 10 seconds
    
    def check_idle(self):
        """Check for idle GPUs and send notifications"""
        current_time = time.time()
        idle_servers = [host for host, last_time in self.last_active_times.items() if current_time - last_time > IDLE_THRESHOLD]
        if idle_servers:
            notification.notify(
                title="GPU Idle Alert",
                message=f"GPUs on servers {', '.join(idle_servers)} have been idle for more than {IDLE_THRESHOLD//60} minutes.",
                timeout=10
            )
    
    def update_gpu_display(self, gpu_data):
        """Update GPU display with new data"""
        for host, info in gpu_data.items():
            if host in self.server_labels:
                # Highlight idle GPUs using HTML
                highlighted_info = info.replace('\n', '<br>').replace('Utilization: 0%', '<span style="background-color: lightgreen;">Utilization: 0%</span>')
                
                label = self.server_labels[host]
                label.setTextFormat(Qt.RichText)
                label.setText(f"{host}:<br>{highlighted_info}")
                label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 5px;")
                
                # Update last active time
                if 'Utilization:' in info and any(f'Utilization: {i}%' in info for i in range(1, 101)):
                    self.last_active_times[host] = time.time()
    
    def close_widget(self):
        """Override parent close method to execute GPU monitor specific cleanup"""
        self.monitoring = False
        self.worker.stop()
        # Remove wait() to avoid blocking the UI thread
        super().close_widget()
