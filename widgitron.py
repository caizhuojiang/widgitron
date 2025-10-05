"""
Widgitron - A modular desktop widget framework for researchers and developers
Main application entry point with control panel and system tray integration
"""

import sys
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QLabel, QListWidget, QHBoxLayout, QMessageBox,
                             QGraphicsDropShadowEffect, QGridLayout, QFrame, QStackedWidget)
from PyQt5.QtCore import Qt, QTimer, QSize, QPoint, QEvent
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

from core.ui_manager import UIManager
from core.window_manager import WindowManager
from core.system_tray import SystemTrayManager
from core.widget_manager import WidgetManager


def load_config(config_path):
    """Load configuration from JSON file"""
    if not os.path.exists(config_path):
        return {}
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Load main configuration
WIDGITRON_CONFIG = load_config('configs/widgitron.json')


class WidgitronMainWindow(QMainWindow):
    """Main control panel for Widgitron"""
    
    def __init__(self):
        super().__init__()
        
        # Load configuration
        self.config = WIDGITRON_CONFIG
        
        # Initialize managers
        self.ui_manager = UIManager(self)
        self.window_manager = WindowManager(self)
        self.system_tray_manager = SystemTrayManager(self)
        self.widget_manager = WidgetManager(self)
        
        # Setup window from config
        window_config = self.config.get('main_window', {})
        self.setWindowTitle(window_config.get('title', 'Widgitron Control Panel'))
        
        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'widgitron.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        width = window_config.get('width', 1200)
        height = window_config.get('height', 800)
        
        # Center the window on screen
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        
        # Set minimum size to allow resizing
        self.setMinimumSize(600, 400)
        
        # Remove default window frame for custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Enable mouse tracking for cursor changes
        self.setMouseTracking(True)
        
        # Store active widgets
        self.active_widgets = {}
        
        # Tab management
        self.current_tab = "applications"  # Default tab
        self.tab_buttons = {}  # Store tab buttons for state management
        
        # Setup UI
        self.ui_manager.setup_ui()
        
        # Create system tray icon
        self.system_tray_manager.create_tray_icon()
        
        # Auto-start widgets if configured
        self.widget_manager.auto_start_widgets()
        
        # Re-set window icon after UI setup (in case it was overridden)
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'widgitron.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Hide on start if configured
        if self.config.get('startup', {}).get('show_main_window', False) is False:
            self.hide()
    
    def shadow_effect(self):
        """Create shadow effect for the window"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 80))
        return shadow
    
    def switch_tab(self, tab_id):
        """Switch to the specified tab"""
        if tab_id == self.current_tab:
            return  # Already on this tab
        
        # Update button states
        if self.current_tab in self.tab_buttons:
            self.tab_buttons[self.current_tab].setObjectName("sidebarButton")
            self.tab_buttons[self.current_tab].setStyle(self.tab_buttons[self.current_tab].style())
        
        if tab_id in self.tab_buttons:
            self.tab_buttons[tab_id].setObjectName("sidebarButtonActive")
            self.tab_buttons[tab_id].setStyle(self.tab_buttons[tab_id].style())
        
        # Update current tab
        self.current_tab = tab_id
        
        # Switch stacked widget page
        if tab_id == "applications":
            self.stacked_widget.setCurrentIndex(0)
        elif tab_id == "settings":
            self.stacked_widget.setCurrentIndex(1)
    
    def toggle_widget(self, widget_id, button):
        """Toggle widget on/off"""
        self.widget_manager.toggle_widget(widget_id, button)
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging and resizing"""
        self.window_manager.mouse_press_event(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging, resizing, and cursor changes"""
        self.window_manager.mouse_move_event(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.window_manager.mouse_release_event(event)
    
    def mouseDoubleClickEvent(self, event):
        """Handle mouse double click on title bar"""
        self.window_manager.mouse_double_click_event(event)
    
    def get_resize_edge(self, pos):
        """Determine which edge of the window is under the mouse"""
        rect = self.rect()
        margin = self.resize_margin
        
        x = pos.x()
        y = pos.y()
        
        # Adjust for the shadow margin (10px on each side)
        shadow_margin = 10
        
        on_left = x >= shadow_margin and x <= shadow_margin + margin
        on_right = x >= rect.width() - shadow_margin - margin and x <= rect.width() - shadow_margin
        on_top = y >= shadow_margin and y <= shadow_margin + margin
        on_bottom = y >= rect.height() - shadow_margin - margin and y <= rect.height() - shadow_margin
        
        if on_top and on_left:
            return 'top-left'
        elif on_top and on_right:
            return 'top-right'
        elif on_bottom and on_left:
            return 'bottom-left'
        elif on_bottom and on_right:
            return 'bottom-right'
        elif on_top:
            return 'top'
        elif on_bottom:
            return 'bottom'
        elif on_left:
            return 'left'
        elif on_right:
            return 'right'
        
        return None
    
    def toggle_maximize(self):
        """Toggle between maximized and normal window state"""
        if self.isMaximized():
            self.showNormal()
            # Process events to ensure window state change is complete
            QApplication.processEvents()
            self.max_btn.setText("□")
            self.max_btn.setToolTip("Maximize")
            # Restore margins for shadow
            container = self.centralWidget()
            container.layout().setContentsMargins(10, 10, 10, 10)
            # Restore rounded corners
            self.content_frame.setObjectName("contentFrame")
            self.title_bar.setObjectName("titleBar")
            self.sidebar.setObjectName("sidebar")
            # Force style refresh immediately and with delay
            self.content_frame.setStyle(self.content_frame.style())
            self.title_bar.setStyle(self.title_bar.style())
            self.sidebar.setStyle(self.sidebar.style())
            # Force repaint to ensure visual update
            self.content_frame.repaint()
            self.title_bar.repaint()
            self.sidebar.repaint()
            # Force container update to refresh shadow effect
            container.update()
            # Additional delayed refresh for safety
            QTimer.singleShot(10, lambda: self.content_frame.setStyle(self.content_frame.style()))
            QTimer.singleShot(10, lambda: self.title_bar.setStyle(self.title_bar.style()))
            QTimer.singleShot(10, lambda: self.sidebar.setStyle(self.sidebar.style()))
            QTimer.singleShot(10, lambda: container.repaint())
        else:
            self.showMaximized()
            self.max_btn.setText("❐")
            self.max_btn.setToolTip("Restore")
            # Remove margins when maximized to eliminate transparent border
            container = self.centralWidget()
            container.layout().setContentsMargins(0, 0, 0, 0)
            # Remove rounded corners when maximized
            self.content_frame.setObjectName("contentFrameMaximized")
            self.title_bar.setObjectName("titleBarMaximized")
            self.sidebar.setObjectName("sidebarMaximized")
            # Force style refresh
            self.content_frame.setStyle(self.content_frame.style())
            self.title_bar.setStyle(self.title_bar.style())
            self.sidebar.setStyle(self.sidebar.style())
    
    def auto_start_widgets(self):
        """Auto-start widgets configured in widgitron.json"""
        self.widget_manager.auto_start_widgets()
    
    def add_widget(self):
        """Add a new widget - placeholder for future implementation"""
        self.widget_manager.add_widget()
    def toggle_gpu_monitor(self):
        """Toggle GPU Monitor widget"""
        self.widget_manager.toggle_gpu_monitor()
    
    def create_tray_icon(self):
        """Create system tray icon"""
        self.system_tray_manager.create_tray_icon()
    
    def show_control_panel(self):
        """Show the control panel window"""
        self.system_tray_manager.show_control_panel()
    
    def quit_application(self):
        """Quit the entire application"""
        self.system_tray_manager.quit_application()
    
    def closeEvent(self, event):
        """Handle window close event - hide to tray instead of closing"""
        event.ignore()
        self.hide()
    
    def event(self, event):
        """Handle custom events"""
        if event.type() == QEvent.User + 1:
            # Show control panel event from system tray
            self.system_tray_manager._show_control_panel_safe()
            return True
        return super().event(event)
    
    def resizeEvent(self, event):
        """Handle window resize event"""
        super().resizeEvent(event)
        # Reset cursor when window is resized
        self.setCursor(Qt.ArrowCursor)
    
    def enterEvent(self, event):
        """Handle mouse enter event"""
        super().enterEvent(event)
        # Update cursor when mouse enters the window based on position
        self.window_manager.update_cursor_on_enter(event.pos())


def main():
    """Main application entry point"""
    print("Starting Widgitron...")
    app = QApplication(sys.argv)
    
    # Set application font
    font = QFont()
    # Try to use system default sans-serif font
    font.setFamily("Segoe UI")  # Windows
    if not font.exactMatch():
        font.setFamily("SF Pro Display")  # macOS
    if not font.exactMatch():
        font.setFamily("Roboto")  # Linux/Android
    if not font.exactMatch():
        font.setFamily("Helvetica Neue")  # Fallback
    if not font.exactMatch():
        font.setFamily("Arial")  # Last fallback
    app.setFont(font)
    
    # Set application info
    app.setApplicationName("Widgitron")
    app.setOrganizationName("Widgitron")
    
    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'widgitron.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Create main window
    main_window = WidgitronMainWindow()
    
    print("Widgitron started. Check system tray for icon.")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
