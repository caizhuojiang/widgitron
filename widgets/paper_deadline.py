"""
Paper Deadline Widget
A desktop widget for monitoring upcoming paper submission deadlines from CCF DDL
"""

import os
import json
import time
import requests
import yaml
from datetime import datetime, timezone
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QFont
from plyer import notification

from core.desktop_widget import DesktopWidget


def load_paper_config():
    """Load Paper Deadline configuration"""
    config_path = 'configs/paper_deadline.json'
    if not os.path.exists(config_path):
        return {
            'update_interval': 3600,  # Update every hour
            'max_deadlines': 5,  # Show top 5 upcoming deadlines
            'widget_size': [500, 400],
            'show_past_deadlines': False,  # Whether to show past deadlines
            'filter_by_rank': ['A', 'B', 'C', 'N'],  # Filter by CCF rank (A, B, C, N) - default all
            'filter_by_sub': ['AI', 'CG', 'CT', 'DB', 'DS', 'HI', 'MX', 'NW', 'SC', 'SE']  # Filter by conference category - default all
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Load configuration
PAPER_CONFIG = load_paper_config()
WIDGET_SIZE = tuple(PAPER_CONFIG.get('widget_size', [500, 400]))
UPDATE_INTERVAL = PAPER_CONFIG.get('update_interval', 3600)
MAX_DEADLINES = PAPER_CONFIG.get('max_deadlines', 5)
SHOW_PAST_DEADLINES = PAPER_CONFIG.get('show_past_deadlines', False)
FILTER_BY_RANK = PAPER_CONFIG.get('filter_by_rank', [])
FILTER_BY_SUB = PAPER_CONFIG.get('filter_by_sub', [])


def format_ccf_rank(rank):
    """Format CCF rank for display"""
    rank_map = {
        'A': 'CCF-A',
        'B': 'CCF-B',
        'C': 'CCF-C',
        'N': 'Non CCF'
    }
    return rank_map.get(rank, rank)


class PaperWorker(QThread):
    """Background thread for fetching paper deadline information"""
    data_ready = pyqtSignal(list)  # Signal to emit deadline data
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        while self.running:
            deadlines = self.get_paper_deadlines()
            self.data_ready.emit(deadlines)
            time.sleep(UPDATE_INTERVAL)
    
    def get_paper_deadlines(self):
        """Fetch and parse paper deadlines from CCF DDL using cached data"""
        try:
            # Get conferences from cache
            conferences = PaperDeadline._get_cached_conferences()
            
            if not conferences:
                print("No conference data available")
                return []
            
            # Process deadlines
            upcoming_deadlines = []
            now = datetime.now(timezone.utc)
            
            for conf in conferences:
                for conf_year in conf.get('confs', []):
                    for timeline_item in conf_year.get('timeline', []):
                        deadline_str = timeline_item.get('deadline')
                        if deadline_str and deadline_str != 'TBD':
                            try:
                                # Parse deadline
                                if ' ' in deadline_str:
                                    deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M:%S')
                                else:
                                    deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d')
                                
                                # Convert to UTC (assuming deadlines are in their timezone)
                                # For simplicity, treat as UTC for now
                                deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
                                
                                # Check if deadline is in the future or if we show past deadlines
                                days_until = (deadline_dt - now).days
                                include_deadline = (days_until >= 0) or SHOW_PAST_DEADLINES
                                
                                if include_deadline:
                                    # Apply rank filter
                                    conf_rank = conf.get('rank', {}).get('ccf', 'N')
                                    if FILTER_BY_RANK and conf_rank not in FILTER_BY_RANK:
                                        continue
                                    
                                    # Apply sub filter
                                    conf_sub = conf.get('sub', '')
                                    if FILTER_BY_SUB and conf_sub not in FILTER_BY_SUB:
                                        continue
                                    
                                    deadline_info = {
                                        'title': conf['title'],
                                        'year': conf_year['year'],
                                        'deadline': deadline_dt,
                                        'days_until': days_until,
                                        'timezone': conf_year.get('timezone', 'UTC'),
                                        'place': conf_year.get('place', ''),
                                        'link': conf_year.get('link', ''),
                                        'rank': conf_rank,
                                        'sub': conf_sub,
                                        'comment': timeline_item.get('comment', '')
                                    }
                                    upcoming_deadlines.append(deadline_info)
                            
                            except ValueError as e:
                                print(f"Error parsing deadline {deadline_str}: {e}")
                                continue
            
            # Sort by deadline (soonest first)
            upcoming_deadlines.sort(key=lambda x: x['deadline'])
            
            # Limit to max deadlines
            return upcoming_deadlines[:MAX_DEADLINES]
            
        except Exception as e:
            print(f"Error fetching paper deadlines: {e}")
            return []
    
    def stop(self):
        self.running = False


class PaperDeadline(DesktopWidget):
    """Paper Deadline Monitoring Widget"""
    
    # Class variable to track active instances
    active_instances = []
    
    # Cache for conference data
    _conference_cache = None
    _cache_timestamp = 0
    _cache_lock = None
    
    @classmethod
    def _init_cache(cls):
        """Initialize cache if not already done"""
        if cls._cache_lock is None:
            from threading import Lock
            cls._cache_lock = Lock()
    
    @classmethod
    def _get_cached_conferences(cls):
        """Get conferences from cache, fetching if necessary"""
        cls._init_cache()
        
        with cls._cache_lock:
            # Check if cache is valid (cache for 1 hour)
            current_time = time.time()
            if cls._conference_cache is None or (current_time - cls._cache_timestamp) > 3600:
                try:
                    print("Fetching conference data from network...")
                    # Fetch data from CCF DDL
                    url = "https://ccfddl.github.io/conference/allconf.yml"
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    
                    # Force UTF-8 encoding to handle special characters correctly
                    response.encoding = 'utf-8'
                    
                    # Parse YAML data
                    conferences = yaml.safe_load(response.text)
                    
                    # Update cache
                    cls._conference_cache = conferences
                    cls._cache_timestamp = current_time
                    print(f"Cached {len(conferences)} conferences")
                    
                except Exception as e:
                    print(f"Error fetching conference data: {e}")
                    # Return cached data if available, even if expired
                    if cls._conference_cache is not None:
                        print("Using expired cache data")
                        return cls._conference_cache
                    return []
            
            return cls._conference_cache
    
    def __init__(self):
        # Use config path for paper deadline
        config_path = 'configs/paper_deadline.json'
        super().__init__(WIDGET_SIZE, config_path=config_path)
        self.setWindowTitle("Paper Deadlines")
        
        # Initialize cache on first instance creation
        PaperDeadline._init_cache()
        
        # Add this instance to active instances
        PaperDeadline.active_instances.append(self)
        
        # Layout for deadline info
        self.layout = QVBoxLayout(self.content_container)
        self.deadline_labels = []
        
        # Store current deadlines for countdown updates
        self.current_deadlines = []
        
        # Create initial deadline labels (no title label)
        for i in range(MAX_DEADLINES):
            label = QLabel(f"Loading deadline {i+1}...")
            label.setFont(QFont("Arial", self.font_size))
            label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 5px;")
            self.layout.addWidget(label)
            self.deadline_labels.append(label)
        
        self.content_container.setLayout(self.layout)
        self.content_container.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        
        self.monitoring = True
        self.is_topmost = False
        self.is_locked = True
        self.drag_position = None
        self.resize_edge = None
        
        # Create paper worker thread
        self.worker = PaperWorker()
        self.worker.data_ready.connect(self.update_deadline_display)
        self.worker.start()
        
        # Update timer for countdown - update every second for precise timing
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_countdown)
        self.update_timer.start(1000)  # Update every second for precise countdown
    
    def on_font_size_changed(self):
        """Called when font size changes - reapply fonts to all widgets"""
        # Update all deadline labels with new font size
        if hasattr(self, 'deadline_labels'):
            for label in self.deadline_labels:
                label.setFont(QFont("Arial", self.font_size))
    
    def update_deadline_display(self, deadlines):
        """Update deadline display with new data"""
        # Store deadlines for countdown updates
        self.current_deadlines = deadlines
        
        # Clear existing labels
        for label in self.deadline_labels:
            label.hide()
        
        # Update with new data
        for i, deadline in enumerate(deadlines):
            if i >= len(self.deadline_labels):
                break
                
            label = self.deadline_labels[i]
            self._update_single_deadline_label(label, deadline)
            label.show()
        
        # Show "No upcoming deadlines" if empty
        if not deadlines:
            if self.deadline_labels:
                self.deadline_labels[0].setText("No upcoming deadlines found")
                self.deadline_labels[0].setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 5px;")
                self.deadline_labels[0].show()
    
    def _update_single_deadline_label(self, label, deadline):
        """Update a single deadline label with current countdown info"""
        title = f"{deadline['title']} {deadline['year']}"
        
        # Calculate remaining time precisely
        now = datetime.now(timezone.utc)
        deadline_dt = deadline['deadline']
        time_remaining = deadline_dt - now
        
        # Calculate days, hours, minutes, seconds
        total_seconds = int(time_remaining.total_seconds())
        
        if total_seconds <= 0:
            days = 0
            hours = 0
            minutes = 0
            seconds = 0
            color = "red"
            time_str = "Expired"
        else:
            days = total_seconds // (24 * 3600)
            remaining = total_seconds % (24 * 3600)
            hours = remaining // 3600
            remaining = remaining % 3600
            minutes = remaining // 60
            seconds = remaining % 60
            
            # Color coding based on urgency
            if days == 0:
                color = "red"
            elif days <= 3:
                color = "orange"
            elif days <= 7:
                color = "yellow"
            else:
                color = "white"
            
            time_str = f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        
        deadline_str = deadline_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        rank = format_ccf_rank(deadline['rank'])
        place = deadline['place']
        
        info = f"<b style='color: {color};'>{title} ({rank})</b><br>"
        info += f"Deadline: {deadline_str}<br>"
        info += f"Time Remaining: <b style='color: {color};'>{time_str}</b><br>"
        if place:
            info += f"Location: {place}<br>"
        if deadline.get('comment'):
            info += f"Note: {deadline['comment']}"
        
        label.setTextFormat(Qt.RichText)
        label.setText(info)
        label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 5px;")
    
    def update_countdown(self):
        """Update countdown timers in real-time"""
        if self.current_deadlines:
            for i, deadline in enumerate(self.current_deadlines):
                if i >= len(self.deadline_labels):
                    break
                label = self.deadline_labels[i]
                self._update_single_deadline_label(label, deadline)
    
    def refresh_data(self):
        """Manually refresh deadline data asynchronously"""
        from PyQt5.QtCore import QThread, pyqtSignal
        
        class RefreshThread(QThread):
            data_ready = pyqtSignal(list)
            
            def __init__(self, parent_instance):
                super().__init__()
                self.parent_instance = parent_instance
            
            def run(self):
                try:
                    # Use cached conference data for fast processing
                    conferences = PaperDeadline._get_cached_conferences()
                    
                    if not conferences:
                        self.data_ready.emit([])
                        return
                    
                    # Process deadlines using current filter settings
                    upcoming_deadlines = []
                    now = datetime.now(timezone.utc)
                    
                    for conf in conferences:
                        for conf_year in conf.get('confs', []):
                            for timeline_item in conf_year.get('timeline', []):
                                deadline_str = timeline_item.get('deadline')
                                if deadline_str and deadline_str != 'TBD':
                                    try:
                                        # Parse deadline
                                        if ' ' in deadline_str:
                                            deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M:%S')
                                        else:
                                            deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d')
                                        
                                        # Convert to UTC (assuming deadlines are in their timezone)
                                        deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
                                        
                                        # Check if deadline is in the future or if we show past deadlines
                                        days_until = (deadline_dt - now).days
                                        include_deadline = (days_until >= 0) or SHOW_PAST_DEADLINES
                                        
                                        if include_deadline:
                                            # Apply rank filter
                                            conf_rank = conf.get('rank', {}).get('ccf', 'N')
                                            if FILTER_BY_RANK and conf_rank not in FILTER_BY_RANK:
                                                continue
                                            
                                            # Apply sub filter
                                            conf_sub = conf.get('sub', '')
                                            if FILTER_BY_SUB and conf_sub not in FILTER_BY_SUB:
                                                continue
                                            
                                            deadline_info = {
                                                'title': conf['title'],
                                                'year': conf_year['year'],
                                                'deadline': deadline_dt,
                                                'days_until': days_until,
                                                'timezone': conf_year.get('timezone', 'UTC'),
                                                'place': conf_year.get('place', ''),
                                                'link': conf_year.get('link', ''),
                                                'rank': conf_rank,
                                                'sub': conf_sub,
                                                'comment': timeline_item.get('comment', '')
                                            }
                                            upcoming_deadlines.append(deadline_info)
                                    
                                    except ValueError as e:
                                        print(f"Error parsing deadline {deadline_str}: {e}")
                                        continue
                    
                    # Sort by deadline (soonest first)
                    upcoming_deadlines.sort(key=lambda x: x['deadline'])
                    
                    # Limit to max deadlines
                    self.data_ready.emit(upcoming_deadlines[:MAX_DEADLINES])
                    
                except Exception as e:
                    print(f"Error refreshing data: {e}")
                    # Emit empty list on error
                    self.data_ready.emit([])
        
        # Create and start thread
        self.refresh_thread = RefreshThread(self)
        self.refresh_thread.data_ready.connect(self.update_deadline_display)
        self.refresh_thread.finished.connect(self.refresh_thread.deleteLater)
        self.refresh_thread.start()
    
    def close_widget(self):
        """Override parent close method to execute paper deadline specific cleanup"""
        self.monitoring = False
        
        # Stop background worker
        self.worker.stop()
        
        # Stop any active refresh thread
        if hasattr(self, 'refresh_thread') and self.refresh_thread.isRunning():
            self.refresh_thread.quit()
            self.refresh_thread.wait(1000)  # Wait up to 1 second
        
        # Remove wait() to avoid blocking the UI thread
        super().close_widget()
        
        # Remove instance from active instances
        if self in PaperDeadline.active_instances:
            PaperDeadline.active_instances.remove(self)
    
    @staticmethod
    def refresh_active_widgets():
        """Refresh all active PaperDeadline widget instances"""
        for instance in PaperDeadline.active_instances:
            # Check if instance still has an active refresh thread
            if not hasattr(instance, 'refresh_thread') or instance.refresh_thread is None or not instance.refresh_thread.isRunning():
                instance.refresh_data()
    
    @staticmethod
    def get_settings_ui(settings_page):
        """Return settings UI for Paper Deadline widget"""
        from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QGridLayout
        from functools import partial
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Auto-start setting
        auto_start_checkbox = QCheckBox("Auto-start widget on application launch")
        auto_start_checkbox.setChecked(PAPER_CONFIG.get('auto_start', True))
        auto_start_checkbox.setObjectName("settingsCheckBox")
        # Connect to auto-save
        auto_start_checkbox.stateChanged.connect(lambda: PaperDeadline.auto_save_settings(None, None, None, None, None, auto_start_checkbox, None))
        layout.addWidget(auto_start_checkbox)
        
        # Font size setting
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        font_combo = QComboBox()
        font_combo.addItems(["8", "9", "10", "11", "12", "14", "16", "18", "20"])
        font_combo.setCurrentText(str(PAPER_CONFIG.get('font_size', 10)))
        font_combo.setObjectName("settingsComboBox")
        # Connect to auto-save
        font_combo.currentTextChanged.connect(lambda: PaperDeadline.auto_save_settings(None, None, None, None, None, None, font_combo))
        font_layout.addWidget(font_label)
        font_layout.addWidget(font_combo)
        font_layout.addStretch()
        layout.addLayout(font_layout)
        
        # Max deadlines setting
        max_layout = QHBoxLayout()
        max_label = QLabel("Maximum Deadlines to Show:")
        max_combo = QComboBox()
        max_combo.addItems(["3", "5", "10", "15", "20"])
        max_combo.setCurrentText(str(PAPER_CONFIG.get('max_deadlines', 5)))
        max_combo.setObjectName("settingsComboBox")
        # Connect to auto-save
        max_combo.currentTextChanged.connect(lambda: PaperDeadline.auto_save_settings(max_combo, None, None, None, None, None, None))
        max_layout.addWidget(max_label)
        max_layout.addWidget(max_combo)
        max_layout.addStretch()
        layout.addLayout(max_layout)
        
        # Show past deadlines
        show_past_checkbox = QCheckBox("Show past deadlines")
        show_past_checkbox.setChecked(PAPER_CONFIG.get('show_past_deadlines', False))
        show_past_checkbox.setObjectName("settingsCheckBox")
        # Connect to auto-save
        show_past_checkbox.stateChanged.connect(lambda: PaperDeadline.auto_save_settings(None, show_past_checkbox, None, None, None, None, None))
        layout.addWidget(show_past_checkbox)
        
        # Rank filter setting
        rank_layout = QVBoxLayout()
        rank_label = QLabel("Filter by CCF Rank:")
        rank_layout.addWidget(rank_label)
        
        rank_checkboxes_layout = QHBoxLayout()
        rank_checkboxes = {}
        rank_options = ["A", "B", "C", "N"]
        current_rank = PAPER_CONFIG.get('filter_by_rank', [])
        # If no rank filter is set, default to all selected
        if not current_rank:
            current_rank = rank_options
        
        for rank in rank_options:
            checkbox = QCheckBox(rank)
            checkbox.setChecked(rank in current_rank)
            checkbox.setObjectName("settingsCheckBox")
            rank_checkboxes[rank] = checkbox
            rank_checkboxes_layout.addWidget(checkbox)
            # Use partial to avoid closure issues
            checkbox.stateChanged.connect(partial(PaperDeadline.on_rank_checkbox_changed, rank_checkboxes))
        
        rank_layout.addLayout(rank_checkboxes_layout)
        layout.addLayout(rank_layout)
        
        # Sub category filter setting
        sub_layout = QVBoxLayout()
        sub_label = QLabel("Filter by Category:")
        sub_layout.addWidget(sub_label)
        
        sub_checkboxes_layout = QGridLayout()
        sub_checkboxes = {}
        sub_options = ["AI", "CG", "CT", "DB", "DS", "HI", "MX", "NW", "SC", "SE"]
        current_sub = PAPER_CONFIG.get('filter_by_sub', [])
        # If no sub filter is set, default to all selected
        if not current_sub:
            current_sub = sub_options
        
        for i, sub in enumerate(sub_options):
            checkbox = QCheckBox(sub)
            checkbox.setChecked(sub in current_sub)
            checkbox.setObjectName("settingsCheckBox")
            sub_checkboxes[sub] = checkbox
            row = i // 5
            col = i % 5
            sub_checkboxes_layout.addWidget(checkbox, row, col)
            # Use partial to avoid closure issues
            checkbox.stateChanged.connect(partial(PaperDeadline.on_sub_checkbox_changed, sub_checkboxes))
        
        sub_layout.addLayout(sub_checkboxes_layout)
        layout.addLayout(sub_layout)
        
        # Update interval setting
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Update Interval:")
        interval_combo = QComboBox()
        interval_combo.addItems(["15 minutes", "30 minutes", "1 hour", "2 hours", "6 hours"])
        
        # Convert current interval to text
        current_interval = PAPER_CONFIG.get('update_interval', 3600)
        if current_interval == 900:
            interval_text = "15 minutes"
        elif current_interval == 1800:
            interval_text = "30 minutes"
        elif current_interval == 3600:
            interval_text = "1 hour"
        elif current_interval == 7200:
            interval_text = "2 hours"
        elif current_interval == 21600:
            interval_text = "6 hours"
        else:
            interval_text = "1 hour"
        
        interval_combo.setCurrentText(interval_text)
        interval_combo.setObjectName("settingsComboBox")
        # Connect to auto-save
        interval_combo.currentTextChanged.connect(lambda: PaperDeadline.auto_save_settings(None, None, None, None, interval_combo, None, None))
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(interval_combo)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)
        
        return widget
    
    @staticmethod
    def on_rank_checkbox_changed(rank_checkboxes):
        """Handle rank checkbox state changes"""
        PaperDeadline.auto_save_settings(None, None, rank_checkboxes, None, None)
    
    @staticmethod
    def on_sub_checkbox_changed(sub_checkboxes):
        """Handle sub checkbox state changes"""
        PaperDeadline.auto_save_settings(None, None, None, sub_checkboxes, None)
    
    @staticmethod
    def auto_save_settings(max_combo=None, show_past_checkbox=None, rank_checkboxes=None, sub_checkboxes=None, interval_combo=None, auto_start_checkbox=None, font_size_combo=None):
        """Auto-save Paper Deadline settings when changed"""
        global PAPER_CONFIG
        
        # Get current values from controls if provided, otherwise use current config
        if max_combo:
            max_deadlines = int(max_combo.currentText())
        else:
            max_deadlines = PAPER_CONFIG.get('max_deadlines', 5)
        
        if show_past_checkbox:
            show_past = show_past_checkbox.isChecked()
        else:
            show_past = PAPER_CONFIG.get('show_past_deadlines', False)
        
        if rank_checkboxes:
            rank_filter = [rank for rank, checkbox in rank_checkboxes.items() if checkbox.isChecked()]
        else:
            rank_filter = PAPER_CONFIG.get('filter_by_rank', [])
        
        if sub_checkboxes:
            sub_filter = [sub for sub, checkbox in sub_checkboxes.items() if checkbox.isChecked()]
        else:
            sub_filter = PAPER_CONFIG.get('filter_by_sub', [])
        
        if interval_combo:
            interval_text = interval_combo.currentText()
        else:
            current_interval = PAPER_CONFIG.get('update_interval', 3600)
            if current_interval == 900:
                interval_text = "15 minutes"
            elif current_interval == 1800:
                interval_text = "30 minutes"
            elif current_interval == 3600:
                interval_text = "1 hour"
            elif current_interval == 7200:
                interval_text = "2 hours"
            elif current_interval == 21600:
                interval_text = "6 hours"
            else:
                interval_text = "1 hour"
        
        if auto_start_checkbox:
            auto_start = auto_start_checkbox.isChecked()
        else:
            auto_start = PAPER_CONFIG.get('auto_start', True)
        
        if font_size_combo:
            font_size = int(font_size_combo.currentText())
        else:
            font_size = PAPER_CONFIG.get('font_size', 10)
        
        # Convert interval text to seconds
        if interval_text == "15 minutes":
            update_interval = 900
        elif interval_text == "30 minutes":
            update_interval = 1800
        elif interval_text == "1 hour":
            update_interval = 3600
        elif interval_text == "2 hours":
            update_interval = 7200
        elif interval_text == "6 hours":
            update_interval = 21600
        else:
            update_interval = 3600
        
        # Update config
        config_path = 'configs/paper_deadline.json'
        config = PAPER_CONFIG.copy()
        config['max_deadlines'] = max_deadlines
        config['show_past_deadlines'] = show_past
        config['filter_by_rank'] = rank_filter
        config['filter_by_sub'] = sub_filter
        config['update_interval'] = update_interval
        config['auto_start'] = auto_start
        config['font_size'] = font_size
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        
        # Update global config
        PAPER_CONFIG = config
        
        # Update global filter variables
        global MAX_DEADLINES, SHOW_PAST_DEADLINES, FILTER_BY_RANK, FILTER_BY_SUB, UPDATE_INTERVAL
        MAX_DEADLINES = max_deadlines
        SHOW_PAST_DEADLINES = show_past
        FILTER_BY_RANK = rank_filter
        FILTER_BY_SUB = sub_filter
        UPDATE_INTERVAL = update_interval
        
        # Refresh active widgets immediately (asynchronously)
        for instance in PaperDeadline.active_instances:
            # Reload font size if it changed
            if font_size_combo:
                instance.reload_font_size()
            # Refresh data
            instance.refresh_data()