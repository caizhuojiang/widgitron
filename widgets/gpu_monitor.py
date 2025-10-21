"""
GPU Monitor Widget
A desktop widget for monitoring GPU usage on remote servers via SSH
"""

from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QFont
from plyer import notification
import paramiko
import os
import json
import time

from core.desktop_widget import DesktopWidget


def load_gpu_config():
    """Load GPU Monitor configuration"""
    config_path = 'configs/gpu_monitor.json'
    if not os.path.exists(config_path):
        return {
            'servers': [],
            'update_interval': 1,
            'idle_threshold': 300,
            'widget_size': [400, 600],
            'display_style': 'list'  # 'list' or 'compact'
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Load configuration
GPU_CONFIG = load_gpu_config()
SERVERS = GPU_CONFIG.get('servers', [])
WIDGET_SIZE = tuple(GPU_CONFIG.get('widget_size', [400, 600]))
UPDATE_INTERVAL = GPU_CONFIG.get('update_interval', 1)
IDLE_THRESHOLD = GPU_CONFIG.get('idle_threshold', 300)
DISPLAY_STYLE = GPU_CONFIG.get('display_style', 'list')


def get_server_id(server):
    """Generate unique server identifier using host:port format"""
    port = server.get('port', 22)
    return f"{server['host']}:{port}"


def simplify_gpu_name(name):
    """Simplify GPU name to short form using intelligent mapping"""
    name = name.strip()
    
    # Comprehensive GPU name mapping table
    gpu_mappings = {
        # NVIDIA Data Center GPUs
        'A100': 'A100',
        'A800': 'A800',
        'A6000': 'A6000',
        'A40': 'A40',
        'H100': 'H100',
        'H200': 'H200',
        'L40': 'L40',
        'L40S': 'L40S',
        'L4': 'L4',
        'T4': 'T4',
        'V100': 'V100',
        'P100': 'P100',
        'P40': 'P40',
        
        # NVIDIA RTX GPUs
        'RTX 6000': 'RTX 6000',
        'RTX 5880': 'RTX 5880',
        'RTX 5000': 'RTX 5000',
        'RTX 4880': 'RTX 4880',
        'RTX 4000': 'RTX 4000',
        'RTX 5070 Ti': 'RTX 5070Ti',
        'RTX 5070': 'RTX 5070',
        'RTX 5000 Ada': 'RTX 5000A',
        'RTX 4000 SFF Ada': 'RTX 4000A',
        'RTX 4500': 'RTX 4500',
        'RTX 4500 Ada': 'RTX 4500A',
        'RTX 4090': 'RTX 4090',
        'RTX 4080': 'RTX 4080',
        'RTX 4070 Ti': 'RTX 4070Ti',
        'RTX 4070': 'RTX 4070',
        'RTX 4060 Ti': 'RTX 4060Ti',
        'RTX 4060': 'RTX 4060',
        'RTX 3090 Ti': 'RTX 3090Ti',
        'RTX 3090': 'RTX 3090',
        'RTX 3080 Ti': 'RTX 3080Ti',
        'RTX 3080': 'RTX 3080',
        'RTX 3070 Ti': 'RTX 3070Ti',
        'RTX 3070': 'RTX 3070',
        'RTX 3060 Ti': 'RTX 3060Ti',
        'RTX 3060': 'RTX 3060',
        'RTX 2080 Ti': 'RTX 2080Ti',
        'RTX 2080': 'RTX 2080',
        'RTX 2070': 'RTX 2070',
        
        # AMD GPUs
        'MI300X': 'MI300X',
        'MI300': 'MI300',
        'MI250X': 'MI250X',
        'MI250': 'MI250',
        'MI210': 'MI210',
        'MI100': 'MI100',
        'MI50': 'MI50',
        'MI25': 'MI25',
        'RX 7900 XTX': 'RX 7900XTX',
        'RX 7900 XT': 'RX 7900XT',
        'RX 7900': 'RX 7900',
        'RX 6900 XT': 'RX 6900XT',
        'RX 6800 XT': 'RX 6800XT',
        'RX 6700 XT': 'RX 6700XT',
        
        # Intel GPUs
        'Arc A770': 'Arc A770',
        'Arc A750': 'Arc A750',
        'Arc A380': 'Arc A380',
        'Data Center GPU Flex 170': 'GPU Flex170',
        'Data Center GPU Flex 140': 'GPU Flex140',
        
        # Tesla GPUs
        'Tesla M40': 'M40',
        'Tesla M10': 'M10',
        'Tesla K40': 'K40',
        'Tesla K20': 'K20',
    }
    
    # First try exact match
    for key, value in gpu_mappings.items():
        if key in name:
            return value
    
    # Fallback: try to extract model number
    # Remove common prefixes
    for prefix in ['NVIDIA ', 'Tesla ', 'AMD ', 'Intel ']:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
            break
    
    # Return first two meaningful parts (handles cases like "GeForce RTX 3080")
    parts = name.split()
    if len(parts) >= 2 and parts[0].lower() in ['geforce', 'radeon']:
        return ' '.join(parts[1:3]) if len(parts) > 1 else parts[0]
    
    # Return first two parts or just the first part
    return ' '.join(parts[:2]) if len(parts) > 1 else (parts[0] if parts else "Unknown")


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
                result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'], 
                                      capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
                result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
                gpu_list = []
                gpu_info = ""
                for line in lines:
                    parts = line.split(',')
                    if len(parts) >= 4:
                        name = parts[0].strip()
                        mem_used = float(parts[1].strip())
                        mem_total = float(parts[2].strip())
                        util = float(parts[3].strip())
                        
                        gpu_list.append({
                            'name': name,
                            'mem_used': mem_used,
                            'mem_total': mem_total,
                            'util': util
                        })
                        
                        gpu_info += f"GPU: {name}\nMemory: {mem_used:.0f}/{mem_total:.0f} MB\nUtilization: {util:.0f}%\n"
                    else:
                        gpu_info += f"Invalid GPU data: {line}\n"
                
                return {
                    'gpu_list': gpu_list,
                    'gpu_info': gpu_info.strip()
                }
            else:
                return {
                    'gpu_list': [],
                    'gpu_info': "No GPU data"
                }
        except Exception as e:
            return {
                'gpu_list': [],
                'gpu_info': f"Error: {str(e)}"
            }
    
    def stop(self):
        self.running = False


class GPUMonitor(DesktopWidget):
    """GPU Monitoring Widget"""
    
    # Class-level list to track active instances
    active_instances = []
    
    def __init__(self):
        # Use config path for GPU monitor
        config_path = 'configs/gpu_monitor.json'
        super().__init__(WIDGET_SIZE, config_path=config_path)
        self.setWindowTitle("GPU Monitor")
        
        # Add this instance to active instances
        GPUMonitor.active_instances.append(self)
        
        # Remove the manual position setting since base class handles it
        # Get screen geometry for positioning is now handled in base class
        
        # Layout for server info - set on content container
        self.layout = QVBoxLayout(self.content_container)
        self.server_labels = {}
        self.server_grid_containers = {}  # For compact style
        
        # Store display style
        self.display_style = DISPLAY_STYLE
        
        # Create UI based on display style
        self._create_display_ui()
        
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
    
    def _create_display_ui(self):
        """Create UI based on display style"""
        # Clear existing layout
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        
        self.server_labels = {}
        self.server_grid_containers = {}
        
        if self.display_style == 'compact':
            # Compact grid style
            for server in SERVERS:
                server_id = get_server_id(server)
                
                # Create container for this server's GPUs
                from PyQt5.QtWidgets import QWidget, QGridLayout
                container = QWidget()
                grid = QGridLayout(container)
                grid.setSpacing(5)
                grid.setContentsMargins(5, 5, 5, 5)
                
                # Server name label
                server_name = QLabel(server_id)
                server_name.setFont(QFont("Arial", self.font_size))
                server_name.setStyleSheet("color: white; font-weight: bold;")
                grid.addWidget(server_name, 0, 0, 1, 4)
                
                # GPU cards (4 per row)
                self.server_grid_containers[server_id] = {
                    'container': container,
                    'grid': grid,
                    'gpu_cards': []
                }
                
                # Create placeholder GPU cards
                for i in range(8):  # Support up to 8 GPUs
                    gpu_card = QLabel()
                    gpu_card.setMinimumHeight(80)
                    gpu_card.setAlignment(Qt.AlignCenter)
                    gpu_card.setStyleSheet(
                        "background-color: rgba(100, 100, 100, 200); "
                        "border: 1px solid gray; "
                        "color: white; "
                        "font-size: 10px;"
                    )
                    gpu_card.hide()
                    row = (i // 4) + 1
                    col = i % 4
                    grid.addWidget(gpu_card, row, col)
                    self.server_grid_containers[server_id]['gpu_cards'].append(gpu_card)
                
                # Add stretch rows/columns
                grid.setRowStretch(3, 1)  # Add stretch to the last row
                container.setLayout(grid)
                self.layout.addWidget(container)
        else:
            # List style (original)
            for server in SERVERS:
                server_id = get_server_id(server)
                server_label = QLabel(f"{server_id}: Initializing...")
                server_label.setFont(QFont("Arial", self.font_size))
                server_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 5px;")
                self.layout.addWidget(server_label)
                self.server_labels[server_id] = server_label
        
        self.layout.addStretch()
    
    def on_font_size_changed(self):
        """Called when font size changes - reapply fonts to all widgets"""
        if self.display_style == 'compact':
            if hasattr(self, 'server_grid_containers'):
                for server_id, container_data in self.server_grid_containers.items():
                    # Update all labels in the grid
                    for i in range(container_data['grid'].count()):
                        widget = container_data['grid'].itemAt(i).widget()
                        if widget:
                            widget.setFont(QFont("Arial", self.font_size))
                    
                    # Update GPU cards with new font size
                    card_font_size = self.font_size + 6
                    for gpu_card in container_data['gpu_cards']:
                        current_style = gpu_card.styleSheet()
                        # Replace old font-size with new one
                        import re
                        new_style = re.sub(r'font-size:\s*\d+px;', f'font-size: {card_font_size}px;', current_style)
                        gpu_card.setStyleSheet(new_style)
        else:
            if hasattr(self, 'server_labels'):
                for server_id, label in self.server_labels.items():
                    label.setFont(QFont("Arial", self.font_size))
    
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
        if self.display_style == 'compact':
            self._update_compact_display(gpu_data)
        else:
            self._update_list_display(gpu_data)
    
    def _update_list_display(self, gpu_data):
        """Update list style display"""
        for host, data in gpu_data.items():
            if host in self.server_labels:
                gpu_info = data.get('gpu_info', '')
                
                # Highlight idle GPUs using HTML
                highlighted_info = gpu_info.replace('\n', '<br>').replace('Utilization: 0%', '<span style="background-color: lightgreen;">Utilization: 0%</span>')
                
                label = self.server_labels[host]
                label.setTextFormat(Qt.RichText)
                label.setText(f"{host}:<br>{highlighted_info}")
                label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 5px;")
                
                # Update last active time
                if 'Utilization:' in gpu_info and any(f'Utilization: {i}%' in gpu_info for i in range(1, 101)):
                    self.last_active_times[host] = time.time()
    
    def _update_compact_display(self, gpu_data):
        """Update compact grid style display"""
        for host, data in gpu_data.items():
            if host in self.server_grid_containers:
                gpu_list = data.get('gpu_list', [])
                gpu_cards = self.server_grid_containers[host]['gpu_cards']
                
                # Update GPU cards
                for i, gpu in enumerate(gpu_list):
                    if i < len(gpu_cards):
                        card = gpu_cards[i]
                        
                        # Calculate memory in GB
                        mem_used_gb = gpu['mem_used'] / 1024
                        mem_total_gb = gpu['mem_total'] / 1024
                        util = gpu['util']
                        
                        # Determine color based on utilization
                        if util < 10:
                            bg_color = "rgba(34, 139, 34, 200)"  # Green
                        elif util < 50:
                            bg_color = "rgba(255, 165, 0, 200)"  # Orange
                        else:
                            bg_color = "rgba(220, 20, 60, 200)"  # Red
                        
                        # Get simplified GPU name
                        gpu_name = simplify_gpu_name(gpu['name'])
                        
                        # Format text
                        text = f"<b>{gpu_name}</b><br>"
                        text += f"{mem_used_gb:.1f}G/{mem_total_gb:.1f}G<br>"
                        text += f"{util:.0f}%"
                        
                        # Calculate dynamic font size based on widget font size
                        # Use a slightly smaller size than the base for compact display
                        card_font_size = self.font_size + 6
                        
                        card.setTextFormat(Qt.RichText)
                        card.setText(text)
                        card.setStyleSheet(
                            f"background-color: {bg_color}; "
                            "border: 1px solid gray; "
                            "color: white; "
                            f"font-size: {card_font_size}px; "
                            "font-weight: bold;"
                        )
                        card.show()
                
                # Hide unused cards
                for i in range(len(gpu_list), len(gpu_cards)):
                    gpu_cards[i].hide()
                
                # Update last active time
                if gpu_list and any(gpu['util'] > 0 for gpu in gpu_list):
                    self.last_active_times[host] = time.time()
    
    def close_widget(self):
        """Override parent close method to execute GPU monitor specific cleanup"""
        self.monitoring = False
        self.worker.stop()
        # Remove wait() to avoid blocking the UI thread
        super().close_widget()
    
    @staticmethod
    def get_settings_ui(settings_page):
        """Return settings UI for GPU Monitor widget"""
        from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Display style setting
        style_layout = QHBoxLayout()
        style_label = QLabel("Display Style:")
        style_combo = QComboBox()
        style_combo.addItems(["List", "Compact"])
        current_style = GPU_CONFIG.get('display_style', 'list')
        style_combo.setCurrentText("Compact" if current_style == 'compact' else "List")
        style_combo.setObjectName("settingsComboBox")
        # Connect to auto-save
        style_combo.currentTextChanged.connect(lambda: GPUMonitor.auto_save_settings(style_combo=style_combo, interval_combo=None, idle_combo=None, auto_start_checkbox=None, font_size_combo=None))
        style_layout.addWidget(style_label)
        style_layout.addWidget(style_combo)
        style_layout.addStretch()
        layout.addLayout(style_layout)
        
        # Auto-start setting
        auto_start_checkbox = QCheckBox("Auto-start widget on application launch")
        auto_start_checkbox.setChecked(GPU_CONFIG.get('auto_start', True))
        auto_start_checkbox.setObjectName("settingsCheckBox")
        # Connect to auto-save
        auto_start_checkbox.stateChanged.connect(lambda: GPUMonitor.auto_save_settings(style_combo=None, interval_combo=None, idle_combo=None, auto_start_checkbox=auto_start_checkbox, font_size_combo=None))
        layout.addWidget(auto_start_checkbox)
        
        # Font size setting
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        font_combo = QComboBox()
        font_combo.addItems(["8", "9", "10", "11", "12", "14", "16", "18", "20"])
        font_combo.setCurrentText(str(GPU_CONFIG.get('font_size', 10)))
        font_combo.setObjectName("settingsComboBox")
        # Connect to auto-save
        font_combo.currentTextChanged.connect(lambda: GPUMonitor.auto_save_settings(style_combo=None, interval_combo=None, idle_combo=None, auto_start_checkbox=None, font_size_combo=font_combo))
        font_layout.addWidget(font_label)
        font_layout.addWidget(font_combo)
        font_layout.addStretch()
        layout.addLayout(font_layout)
        
        # Update interval setting
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Update Interval:")
        interval_combo = QComboBox()
        interval_combo.addItems(["1 second", "5 seconds", "10 seconds", "30 seconds", "1 minute"])
        
        # Convert current interval to text
        current_interval = GPU_CONFIG.get('update_interval', 1)
        if current_interval == 1:
            interval_text = "1 second"
        elif current_interval == 5:
            interval_text = "5 seconds"
        elif current_interval == 10:
            interval_text = "10 seconds"
        elif current_interval == 30:
            interval_text = "30 seconds"
        elif current_interval == 60:
            interval_text = "1 minute"
        else:
            interval_text = "5 seconds"
        
        interval_combo.setCurrentText(interval_text)
        interval_combo.setObjectName("settingsComboBox")
        # Connect to auto-save
        interval_combo.currentTextChanged.connect(lambda: GPUMonitor.auto_save_settings(style_combo=None, interval_combo=interval_combo, idle_combo=None, auto_start_checkbox=None, font_size_combo=None))
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(interval_combo)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)
        
        # Idle threshold setting
        idle_layout = QHBoxLayout()
        idle_label = QLabel("Idle Threshold (minutes):")
        idle_combo = QComboBox()
        idle_combo.addItems(["5", "10", "15", "30", "60"])
        
        # Convert current threshold to text
        current_threshold = GPU_CONFIG.get('idle_threshold', 300) // 60
        idle_combo.setCurrentText(str(current_threshold))
        idle_combo.setObjectName("settingsComboBox")
        # Connect to auto-save
        idle_combo.currentTextChanged.connect(lambda: GPUMonitor.auto_save_settings(style_combo=None, interval_combo=None, idle_combo=idle_combo, auto_start_checkbox=None, font_size_combo=None))
        idle_layout.addWidget(idle_label)
        idle_layout.addWidget(idle_combo)
        idle_layout.addStretch()
        layout.addLayout(idle_layout)
        
        return widget
    
    @staticmethod
    def auto_save_settings(style_combo=None, interval_combo=None, idle_combo=None, auto_start_checkbox=None, font_size_combo=None):
        """Auto-save GPU Monitor settings when changed"""
        global GPU_CONFIG
        
        # Get current values from combos if provided, otherwise use current config
        if style_combo:
            style_text = style_combo.currentText()
            display_style = 'compact' if style_text == 'Compact' else 'list'
        else:
            display_style = GPU_CONFIG.get('display_style', 'list')
        
        if interval_combo:
            interval_text = interval_combo.currentText()
        else:
            current_interval = GPU_CONFIG.get('update_interval', 1)
            if current_interval == 1:
                interval_text = "1 second"
            elif current_interval == 5:
                interval_text = "5 seconds"
            elif current_interval == 10:
                interval_text = "10 seconds"
            elif current_interval == 30:
                interval_text = "30 seconds"
            elif current_interval == 60:
                interval_text = "1 minute"
            else:
                interval_text = "5 seconds"
        
        if idle_combo:
            idle_minutes_text = idle_combo.currentText()
        else:
            current_threshold = GPU_CONFIG.get('idle_threshold', 300) // 60
            idle_minutes_text = str(current_threshold)
        
        if auto_start_checkbox:
            auto_start = auto_start_checkbox.isChecked()
        else:
            auto_start = GPU_CONFIG.get('auto_start', True)
        
        if font_size_combo:
            font_size = int(font_size_combo.currentText())
        else:
            font_size = GPU_CONFIG.get('font_size', 10)
        
        # Convert interval text to seconds
        if interval_text == "1 second":
            update_interval = 1
        elif interval_text == "5 seconds":
            update_interval = 5
        elif interval_text == "10 seconds":
            update_interval = 10
        elif interval_text == "30 seconds":
            update_interval = 30
        elif interval_text == "1 minute":
            update_interval = 60
        else:
            update_interval = 5
        
        # Convert idle threshold to seconds
        idle_minutes = int(idle_minutes_text)
        idle_threshold = idle_minutes * 60
        
        # Update config
        config_path = 'configs/gpu_monitor.json'
        config = GPU_CONFIG.copy()
        config['display_style'] = display_style
        config['update_interval'] = update_interval
        config['idle_threshold'] = idle_threshold
        config['auto_start'] = auto_start
        config['font_size'] = font_size
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        
        # Update global config (use globals() to properly update the global variable)
        GPU_CONFIG.update(config)
        
        # Refresh any active GPU Monitor widgets
        if style_combo:
            # Style changed, need to recreate UI
            for instance in GPUMonitor.active_instances:
                instance.display_style = display_style
                instance._create_display_ui()
        
        # Refresh with new font size if it changed
        if font_size_combo:
            for instance in GPUMonitor.active_instances:
                instance.reload_font_size()
