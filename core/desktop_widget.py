"""
DesktopWidget - Base class for all desktop widgets
Universal desktop floating widget parent class, providing mouse hover function buttons and basic window functions
"""

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QCursor
import time
import json
import os


class DesktopWidget(QWidget):
    """Universal desktop floating widget parent class, providing mouse hover function buttons and basic window functions"""
    
    def load_config(self):
        """Load configuration from JSON file"""
        if not self.config_path or not os.path.exists(self.config_path):
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config from {self.config_path}: {e}")
            return {}
    
    def save_config(self):
        """Save current configuration to JSON file"""
        if not self.config_path:
            return
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config to {self.config_path}: {e}")
    
    def set_position_from_config(self):
        """Set window position from configuration"""
        if 'widget_position' in self.config:
            pos = self.config['widget_position']
            if isinstance(pos, list) and len(pos) == 2:
                x, y = pos
                # Ensure position is within screen bounds
                screen = QApplication.desktop().screenGeometry()
                x = max(0, min(x, screen.width() - self.width()))
                y = max(0, min(y, screen.height() - self.height()))
                self.move(x, y)
        else:
            # Default position if not configured
            screen = QApplication.desktop().screenGeometry()
            x = screen.width() - self.width() - 50
            y = (screen.height() - self.height()) // 2
            self.move(x, y)
    
    def reload_font_size(self):
        """Reload font size from config and refresh UI"""
        # Reload config to get latest font_size
        self.config = self.load_config()
        self.font_size = self.config.get('font_size', 10)
        # Subclasses should override this method to apply font changes
        self.on_font_size_changed()
    
    def on_font_size_changed(self):
        """Called when font size changes - subclasses should override this"""
        pass
    
    def __init__(self, size=(300, 200), config_path=None, debug=False):
        super().__init__()
        
        # Configuration
        self.config_path = config_path
        self.config = self.load_config()
        
        # Basic window settings
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        
        # Set transparent background for the entire window
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Enable mouse tracking for the entire window to handle events in transparent areas
        self.setMouseTracking(True)
        
        # Content size (the actual visible area)
        default_size = size
        config_size = self.config.get('widget_size', default_size)
        if isinstance(config_size, list) and len(config_size) == 2:
            self.content_width, self.content_height = config_size
        else:
            self.content_width, self.content_height = default_size
        
        # Font size configuration
        self.font_size = self.config.get('font_size', 10)
        
        # Add margin around content for button area (transparent region)
        self.margin = 60  # Margin for buttons and transparent area
        
        # Total window size = content size + 2 * margin
        total_width = self.content_width + 2 * self.margin
        total_height = self.content_height + 2 * self.margin
        self.resize(total_width, total_height)
        
        # Set position from config or default
        self.set_position_from_config()
        
        # Create content container (centered in the window)
        self.content_container = QWidget(self)
        self.content_container.setGeometry(self.margin, self.margin, self.content_width, self.content_height)
        self.content_container.setMouseTracking(True)
        
        # State variables
        self.is_topmost = False
        self.is_locked = True
        self.drag_position = None
        self.resize_edge = None
        
        # Position save debouncing
        self.last_save_time = 0
        self.save_debounce_ms = 500  # Save at most once per 500ms
        
        # Mouse hover related
        self.mouse_inside = False
        self.hover_start_time = 0
        self.hover_threshold = 200  # 0.2 second
        self.buttons_visible = False
        self.hide_delay_time = 0  # Track when mouse left the area
        self.hide_delay_threshold = 500  # Wait 0.5 second before hiding
        
        # Create function buttons but initially hidden
        self.create_function_buttons()
        
        # Create opacity animation effect
        self.opacity_effect = QGraphicsOpacityEffect()
        self.function_buttons.setGraphicsEffect(self.opacity_effect)
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(300)  # Animation duration 300ms
        self.opacity_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Hover detection timer
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.check_hover_timeout)
        self.hover_timer.start(100)  # Check every 100ms
        
        # Enable mouse tracking for the content container
        self.content_container.setMouseTracking(True)

        # Debug mode
        self.debug = debug
    
    def create_function_buttons(self):
        """Create function buttons"""
        self.function_buttons = QWidget(self)
        # Make container completely transparent
        self.function_buttons.setAttribute(Qt.WA_TranslucentBackground)
        self.function_buttons.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(255, 255, 255, 200);
                color: #333333;
                padding: 6px;
                margin: 0px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                min-width: 28px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 230);
                border: 1px solid rgba(255, 255, 255, 255);
            }
            QPushButton:pressed {
                background-color: rgba(200, 200, 200, 200);
                border: 1px solid rgba(255, 255, 255, 200);
            }
        """)
        
        button_layout = QHBoxLayout(self.function_buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        
        # Lock/Unlock button
        self.lock_button = QPushButton("🔒")
        self.lock_button.setToolTip("Click to toggle lock/unlock window")
        self.lock_button.clicked.connect(self.toggle_lock)
        button_layout.addWidget(self.lock_button)
        
        # Topmost/Not topmost button
        self.topmost_button = QPushButton("📌")
        self.topmost_button.setToolTip("Click to toggle always on top")
        self.topmost_button.clicked.connect(self.toggle_topmost)
        button_layout.addWidget(self.topmost_button)
        
        # Close button
        self.close_button = QPushButton("✖")
        self.close_button.setToolTip("Close application")
        self.close_button.clicked.connect(self.close_widget)
        button_layout.addWidget(self.close_button)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 100, 100, 200);
                color: white;
                border: 1px solid rgba(255, 120, 120, 220);
            }
            QPushButton:hover {
                background-color: rgba(255, 120, 120, 240);
                border: 1px solid rgba(255, 150, 150, 255);
            }
            QPushButton:pressed {
                background-color: rgba(220, 80, 80, 220);
                border: 1px solid rgba(255, 100, 100, 200);
            }
        """)
        
        self.function_buttons.hide()
        self.update_button_states()
    
    def update_button_states(self):
        """Update button state display"""
        base_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(255, 255, 255, 200);
                color: #333333;
                padding: 6px;
                margin: 0px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                min-width: 28px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 230);
                border: 1px solid rgba(255, 255, 255, 255);
            }
            QPushButton:pressed {
                background-color: rgba(200, 200, 200, 200);
                border: 1px solid rgba(255, 255, 255, 200);
            }
        """
        
        if self.is_locked:
            self.lock_button.setText("🔒")
            self.lock_button.setToolTip("Window is locked - click to unlock")
            self.lock_button.setStyleSheet(base_style + """
                QPushButton {
                    background-color: rgba(255, 200, 200, 200);
                    border: 1px solid rgba(255, 180, 180, 220);
                }
            """)
        else:
            self.lock_button.setText("🔓")
            self.lock_button.setToolTip("Window is unlocked - click to lock")
            self.lock_button.setStyleSheet(base_style)
            
        if self.is_topmost:
            self.topmost_button.setText("📌")
            self.topmost_button.setToolTip("Window is always on top - click to disable")
            self.topmost_button.setStyleSheet(base_style + """
                QPushButton {
                    background-color: rgba(200, 255, 200, 200);
                    border: 1px solid rgba(180, 255, 180, 220);
                }
            """)
        else:
            self.topmost_button.setText("📍")
            self.topmost_button.setToolTip("Window is not always on top - click to enable")
            self.topmost_button.setStyleSheet(base_style)
    
    def position_function_buttons(self):
        """Position function buttons outside the content area in the transparent margin"""
        button_width = self.function_buttons.sizeHint().width()
        button_height = self.function_buttons.sizeHint().height()
        
        # Position buttons in the top-right margin area, outside and aligned with content right edge
        # Content container right edge is at: self.margin + self.content_width
        content_right_edge = self.margin + self.content_width
        x = content_right_edge - button_width  # Align right edge of buttons with content right edge
        y = self.margin - button_height - 8  # 8 pixels above the content area
        
        self.function_buttons.move(x, y)
        self.function_buttons.resize(button_width, button_height)
    
    def check_hover_timeout(self):
        """Check hover timeout"""
        is_hovering = self.mouse_inside or self.is_mouse_over_buttons()
        
        if is_hovering:
            if not self.buttons_visible:
                self._set_function_buttons_visible()
                
        else:
            # Mouse left the area, start hide delay
            if self.buttons_visible:
                self._set_function_buttons_invisible()
    
    def is_mouse_over_buttons(self):
        """Check if mouse is over function buttons"""
        if not self.buttons_visible:
            return False
        
        # Get global mouse position
        global_pos = QCursor.pos()
        # Get button widget geometry in global coordinates
        button_rect = self.function_buttons.geometry()
        button_global_rect = button_rect.translated(self.pos())
        
        return button_global_rect.contains(global_pos)
    
    def _set_function_buttons_visible(self):
        self.buttons_visible = True
        if self.debug:
            print("self.buttons_visible = True")
        self.position_function_buttons()
        self.function_buttons.show()
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.finished.connect(lambda: self.function_buttons.show())
        self.opacity_animation.start()
        
    def _set_function_buttons_invisible(self):
        self.buttons_visible = False
        if self.debug:
            print("self.buttons_visible = False")        
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.finished.connect(lambda: self.function_buttons.hide())
        self.opacity_animation.start()
    
    def enterEvent(self, event):
        """Mouse enter event - triggered when mouse enters the window"""
        # When mouse enters the window, start hover detection
        self.mouse_inside = True
        self.hover_start_time = time.time() * 1000
        if self.debug:
            print("Mouse entered the window")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Mouse leave event - triggered when mouse leaves the window"""
        # When mouse leaves the window, it's no longer inside
        self.mouse_inside = False
        if self.debug:
            print("Mouse left the window")
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Mouse press event"""
        if not self.is_locked and event.button() == Qt.LeftButton:
            if self.resize_edge:
                pass  # Start resizing
            else:
                # Only allow dragging within content area
                if event.pos().x() >= self.margin and event.pos().x() < self.margin + self.content_width and \
                   event.pos().y() >= self.margin and event.pos().y() < self.margin + self.content_height:
                    self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Mouse move event"""
        # Update mouse_inside status based on current position with some tolerance
        # Add a small tolerance to avoid flickering at boundaries
        tolerance = 2
        is_in_content_area = (event.pos().x() >= self.margin - tolerance and 
                             event.pos().x() < self.margin + self.content_width + tolerance and \
                             event.pos().y() >= self.margin - tolerance and 
                             event.pos().y() < self.margin + self.content_height + tolerance)
        
        # Only update state if there's a significant change to avoid rapid toggling
        if is_in_content_area and not self.mouse_inside:
            # Mouse entered content area
            self.mouse_inside = True
            self.hover_start_time = time.time() * 1000
        elif not is_in_content_area and self.mouse_inside:
            # Mouse left content area
            self.mouse_inside = False
        
        if not self.is_locked:
            if self.drag_position is not None and event.buttons() == Qt.LeftButton and not self.resize_edge:
                self.move(event.globalPos() - self.drag_position)
            elif self.resize_edge and event.buttons() == Qt.LeftButton:
                self.handle_resize(event.globalPos())
            elif not event.buttons():
                content_local_pos = event.pos() - QPoint(self.margin, self.margin)
                self.update_cursor_for_resize(content_local_pos)
        else:
            # Outside content area, reset cursor
            self.setCursor(Qt.ArrowCursor)
            self.resize_edge = None
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Mouse release event"""
        if event.button() == Qt.LeftButton:
            self.drag_position = None
            self.resize_edge = None
            self.setCursor(Qt.ArrowCursor)
            if hasattr(self, 'initial_geom'):
                delattr(self, 'initial_geom')
                delattr(self, 'initial_pos')
        super().mouseReleaseEvent(event)
    
    def handle_resize(self, global_pos):
        """Handle window resizing"""
        if not hasattr(self, 'initial_geom'):
            self.initial_geom = self.geometry()
            self.initial_pos = global_pos
            return
        
        delta_x = global_pos.x() - self.initial_pos.x()
        delta_y = global_pos.y() - self.initial_pos.y()
        
        if self.resize_edge == 'right':
            new_width = self.initial_geom.width() + delta_x
            self.setGeometry(self.initial_geom.x(), self.initial_geom.y(), max(200, new_width), self.initial_geom.height())
        elif self.resize_edge == 'bottom':
            new_height = self.initial_geom.height() + delta_y
            self.setGeometry(self.initial_geom.x(), self.initial_geom.y(), self.initial_geom.width(), max(100, new_height))
        elif self.resize_edge == 'bottom-right':
            new_width = self.initial_geom.width() + delta_x
            new_height = self.initial_geom.height() + delta_y
            self.setGeometry(self.initial_geom.x(), self.initial_geom.y(), max(200, new_width), max(100, new_height))
        elif self.resize_edge == 'left':
            new_width = self.initial_geom.width() - delta_x
            self.setGeometry(self.initial_geom.x() + delta_x, self.initial_geom.y(), max(200, new_width), self.initial_geom.height())
        elif self.resize_edge == 'top':
            new_height = self.initial_geom.height() - delta_y
            self.setGeometry(self.initial_geom.x(), self.initial_geom.y() + delta_y, self.initial_geom.width(), max(100, new_height))
        elif self.resize_edge == 'top-left':
            new_width = self.initial_geom.width() - delta_x
            new_height = self.initial_geom.height() - delta_y
            self.setGeometry(self.initial_geom.x() + delta_x, self.initial_geom.y() + delta_y, max(200, new_width), max(100, new_height))
        elif self.resize_edge == 'top-right':
            new_width = self.initial_geom.width() + delta_x
            new_height = self.initial_geom.height() - delta_y
            self.setGeometry(self.initial_geom.x(), self.initial_geom.y() + delta_y, max(200, new_width), max(100, new_height))
        elif self.resize_edge == 'bottom-left':
            new_width = self.initial_geom.width() - delta_x
            new_height = self.initial_geom.height() + delta_y
            self.setGeometry(self.initial_geom.x() + delta_x, self.initial_geom.y(), max(200, new_width), max(100, new_height))
    
    def update_cursor_for_resize(self, pos):
        """Update cursor for resizing based on mouse position within content area"""
        margin = 10
        rect = self.content_container.rect()
        
        if pos.x() <= margin and pos.y() <= margin:
            self.setCursor(Qt.SizeFDiagCursor)
            self.resize_edge = 'top-left'
        elif pos.x() >= rect.width() - margin and pos.y() <= margin:
            self.setCursor(Qt.SizeBDiagCursor)
            self.resize_edge = 'top-right'
        elif pos.x() <= margin and pos.y() >= rect.height() - margin:
            self.setCursor(Qt.SizeBDiagCursor)
            self.resize_edge = 'bottom-left'
        elif pos.x() >= rect.width() - margin and pos.y() >= rect.height() - margin:
            self.setCursor(Qt.SizeFDiagCursor)
            self.resize_edge = 'bottom-right'
        elif pos.x() <= margin:
            self.setCursor(Qt.SizeHorCursor)
            self.resize_edge = 'left'
        elif pos.x() >= rect.width() - margin:
            self.setCursor(Qt.SizeHorCursor)
            self.resize_edge = 'right'
        elif pos.y() <= margin:
            self.setCursor(Qt.SizeVerCursor)
            self.resize_edge = 'top'
        elif pos.y() >= rect.height() - margin:
            self.setCursor(Qt.SizeVerCursor)
            self.resize_edge = 'bottom'
        else:
            self.setCursor(Qt.ArrowCursor)
            self.resize_edge = None
    
    def toggle_lock(self):
        """Toggle lock state"""
        self.is_locked = not self.is_locked
        self.update_button_states()
    
    def toggle_topmost(self):
        """Toggle topmost state"""
        self.is_topmost = not self.is_topmost
        flags = self.windowFlags()
        if self.is_topmost:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()
        self.update_button_states()
    
    def close_widget(self):
        """Close widget"""
        self.hide()
    
    def resizeEvent(self, event):
        """Window resize event"""
        super().resizeEvent(event)
        
        # Update content container size and position
        new_total_width = self.width()
        new_total_height = self.height()
        
        # Content size is total size minus margins
        self.content_width = new_total_width - 2 * self.margin
        self.content_height = new_total_height - 2 * self.margin
        
        # Ensure minimum content size
        self.content_width = max(200, self.content_width)
        self.content_height = max(100, self.content_height)
        
        # Update content container geometry
        self.content_container.setGeometry(self.margin, self.margin, self.content_width, self.content_height)
        
        # Reposition function buttons if visible
        if hasattr(self, 'function_buttons') and self.buttons_visible:
            self.position_function_buttons()
        
        # Save current size to config
        if hasattr(self, 'config'):
            self.config['widget_size'] = [self.content_width, self.content_height]
            self.save_config()
    
    def moveEvent(self, event):
        """Window move event - save position to config with debouncing"""
        super().moveEvent(event)
        
        # Debounce saves to avoid too frequent file writes
        current_time = time.time() * 1000  # milliseconds
        if current_time - self.last_save_time > self.save_debounce_ms:
            # Save current position to config
            if hasattr(self, 'config'):
                pos = self.pos()
                self.config['widget_position'] = [pos.x(), pos.y()]
                self.save_config()
                self.last_save_time = current_time
