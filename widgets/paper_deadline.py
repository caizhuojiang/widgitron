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
try:
    # Python 3.9+
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except Exception:
    # Fallback - ZoneInfo not available (very old Python). We'll fall back to UTC only.
    ZoneInfo = None
    class ZoneInfoNotFoundError(Exception):
        pass
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


def _parse_deadline_with_timezone(deadline_str, tz_name=None):
    """Parse a deadline string and return a timezone-aware datetime in UTC.

    - deadline_str: 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'
    - tz_name: timezone name like 'UTC' or 'Asia/Shanghai'. If None or invalid, treat as UTC.

    Returns (deadline_dt_utc, original_tz_name)
    """
    # Try ISO formats first (may include timezone offsets)
    dt = None
    tz_used = 'UTC'
    try:
        iso_str = deadline_str
        # Normalize trailing Z to +00:00 for fromisoformat
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + '+00:00'
        # fromisoformat handles 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DDTHH:MM:SS+08:00', etc.
        try:
            dt = datetime.fromisoformat(iso_str)
        except Exception:
            # Try with space separator
            if ' ' in deadline_str and 'T' not in deadline_str:
                try:
                    dt = datetime.fromisoformat(deadline_str)
                except Exception:
                    dt = None
    except Exception:
        dt = None

    # If fromisoformat didn't parse, try common strptime patterns including minute precision
    if dt is None:
        patterns = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']
        for p in patterns:
            try:
                dt = datetime.strptime(deadline_str, p)
                break
            except Exception:
                dt = None

    if dt is None:
        # Could not parse
        raise ValueError(f"Unrecognized deadline format: {deadline_str}")

    # If parsed datetime has tzinfo (from ISO with offset), use it. Otherwise attach tz_name or UTC.
    if dt.tzinfo is not None:
        # Has tzinfo already (offset aware)
        try:
            # Convert to UTC for storage
            dt_utc = dt.astimezone(timezone.utc)
            # Derive a UTC±HH:MM style name from offset
            try:
                offset = dt.utcoffset()
                if offset is None:
                    tz_used = 'UTC'
                else:
                    total_seconds = int(offset.total_seconds())
                    sign = '+' if total_seconds >= 0 else '-'
                    total_seconds = abs(total_seconds)
                    off_h = total_seconds // 3600
                    off_m = (total_seconds % 3600) // 60
                    tz_used = f"UTC{sign}{off_h:02d}:{off_m:02d}"
            except Exception:
                tz_used = 'UTC'
            return dt_utc, tz_used
        except Exception:
            # Fallback to treating as UTC
            return dt.replace(tzinfo=timezone.utc), 'UTC'

    # No tzinfo on parsed dt -> attach tz from tz_name if possible
    tz_obj = None
    # Accept timezone names like 'Asia/Shanghai' via ZoneInfo, or UTC offsets like 'UTC-12', 'AoE'
    if tz_name:
        # Handle 'AoE' (Anywhere on Earth) - treat as UTC-12
        if tz_name.upper() == 'AOE':
            from datetime import timedelta
            tz_obj = timezone(timedelta(hours=-12))
            tz_used = 'UTC-12:00'
        # If tz_name is an explicit UTC offset like 'UTC-12' or 'UTC+08', parse it
        elif isinstance(tz_name, str) and tz_name.upper().startswith('UTC') and (len(tz_name) > 3) and (tz_name[3] in ['+', '-']):
            # parse offset portion (e.g. '-12' or '+08')
            off = tz_name[3:]
            # normalize to +HH:MM or -HH:MM
            if ':' not in off:
                sig = off[0] if off and off[0] in ['+', '-'] else '+'
                digits = off[1:] if sig in off else off
                # ensure two-digit hour
                if digits.isdigit():
                    if len(digits) == 1:
                        hh_part = f"0{digits}"
                        mm_part = '00'
                    elif len(digits) == 2:
                        hh_part = digits
                        mm_part = '00'
                    elif len(digits) == 4:
                        # e.g. 0830 -> 08:30
                        hh_part = digits[0:2]
                        mm_part = digits[2:4]
                    else:
                        # unexpected, fallback to '00'
                        hh_part = digits[:2].zfill(2)
                        mm_part = '00'
                    off = f"{sig}{hh_part}:{mm_part}"
                else:
                    # unexpected format, keep as-is which will likely fail later
                    off = off
            # now off should be like +HH:MM or -HH:MM
            sign = 1 if off[0] == '+' else -1
            hh = int(off[1:3])
            mm = int(off[4:6]) if ':' in off else 0
            from datetime import timedelta
            tz_obj = timezone(timedelta(hours=sign * hh, minutes=sign * mm))
            tz_used = f"UTC{off}"
        # Try ZoneInfo if not already parsed as explicit UTC offset
        elif ZoneInfo is not None:
            try:
                tz_obj = ZoneInfo(tz_name)
                tz_used = tz_name
            except Exception:
                tz_obj = None
                # keep tz_used as whatever was set (likely 'UTC')

    if tz_obj is None:
        tz_obj = timezone.utc
        tz_used = 'UTC'

    try:
        dt_local = dt.replace(tzinfo=tz_obj)
        dt_utc = dt_local.astimezone(timezone.utc)
    except Exception:
        dt_utc = dt.replace(tzinfo=timezone.utc)
        tz_used = 'UTC'

    return dt_utc, tz_used


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
                                # Parse deadline and attach timezone if provided in conf_year
                                tz_name = conf_year.get('timezone', 'UTC')
                                deadline_dt_utc, tz_used = _parse_deadline_with_timezone(deadline_str, tz_name)

                                # Check if deadline is in the future or if we show past deadlines
                                days_until = (deadline_dt_utc - now).days
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
                                        'deadline': deadline_dt_utc,
                                        'days_until': days_until,
                                        'timezone': tz_used,
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
        
        # Display deadline in the data-source timezone as UTC±HH:MM (use original timezone if available)
        orig_tz = deadline.get('timezone', 'UTC')
        deadline_str = None
        try:
            # If orig_tz is like 'UTC+08:00' or 'UTC', use that offset directly
            if isinstance(orig_tz, str) and orig_tz.upper().startswith('UTC') and (orig_tz == 'UTC' or orig_tz[3] in ['+', '-']):
                # Convert UTC datetime to offset-aware display using the offset
                # If orig_tz == 'UTC', offset is +00:00
                if orig_tz == 'UTC':
                    offset_str = '+00:00'
                else:
                    offset_str = orig_tz[3:]
                # Compute local time by applying offset
                sign = 1 if offset_str[0] == '+' else -1
                hh = int(offset_str[1:3])
                mm = int(offset_str[4:6])
                total_minutes = sign * (hh * 60 + mm)
                local_dt = deadline_dt + timezone.utc.utcoffset(deadline_dt)  # keep as UTC base
                # Apply offset
                from datetime import timedelta
                local_dt = (deadline_dt + timedelta(minutes=total_minutes)).replace(tzinfo=None)
                deadline_str = f"{local_dt.strftime('%Y-%m-%d %H:%M:%S')} (UTC{offset_str})"
            else:
                # Try to resolve orig_tz via zoneinfo if available
                if ZoneInfo is not None:
                    try:
                        tz_obj = ZoneInfo(orig_tz)
                        local_dt = deadline_dt.astimezone(tz_obj)
                        # Format offset as +HH:MM
                        offset = local_dt.utcoffset() or timezone.utc.utcoffset(local_dt)
                        total_seconds = int(offset.total_seconds())
                        sign = '+' if total_seconds >= 0 else '-'
                        total_seconds = abs(total_seconds)
                        off_h = total_seconds // 3600
                        off_m = (total_seconds % 3600) // 60
                        offset_str = f"{sign}{off_h:02d}:{off_m:02d}"
                        deadline_str = f"{local_dt.strftime('%Y-%m-%d %H:%M:%S')} (UTC{offset_str})"
                    except Exception:
                        # Fallback
                        deadline_str = deadline_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                else:
                    # zoneinfo unavailable -> show UTC time
                    deadline_str = deadline_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except Exception:
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
                                        # Parse deadline with timezone information if available
                                        tz_name = conf_year.get('timezone', 'UTC')
                                        deadline_dt_utc, tz_used = _parse_deadline_with_timezone(deadline_str, tz_name)

                                        # Check if deadline is in the future or if we show past deadlines
                                        days_until = (deadline_dt_utc - now).days
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
                                                'deadline': deadline_dt_utc,
                                                'days_until': days_until,
                                                'timezone': tz_used,
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