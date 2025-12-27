"""
System Tray Manager for Widgitron
Handles system tray icon and menu functionality
"""

import os
import threading
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PIL import Image
import pystray
from pystray import MenuItem as item


class SystemTrayManager:
    """Manages system tray icon and menu"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.tray_icon = None
        self.tray_thread = None

    def create_tray_icon(self):
        """Create system tray icon"""
        tray_config = self.main_window.config.get('tray_icon', {})
        tooltip = tray_config.get('tooltip', 'Widgitron')

        # Right-click menu with Exit option
        # The first menu item will be treated as default (left-click action)
        menu = (
            item('Show', self.show_control_panel),
            item('Exit', self.main_window.quit_application),
        )

        # Create icon with default menu item (Show) set to index 0
        icon_image = self.create_icon()
        self.tray_icon = pystray.Icon(
            "widgitron", 
            icon_image, 
            tooltip, 
            menu,
            default_menu_index=0  # Set "Show" as the default action for left-click
        )

        # Run in separate thread
        self.tray_thread = threading.Thread(target=self.tray_icon.run)
        self.tray_thread.daemon = True
        self.tray_thread.start()

    def create_icon(self):
        """Create system tray icon image"""
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'icons', 'widgitron.png')
        img = Image.open(icon_path)
        return img

    def show_control_panel(self):
        """Show the control panel window"""
        try:
            # Use QApplication to post event to main thread
            from PyQt5.QtCore import QEvent
            QApplication.postEvent(self.main_window, QEvent(QEvent.User + 1))
        except Exception as e:
            print(f"Error showing control panel: {e}")
            import traceback
            traceback.print_exc()

    def _show_control_panel_safe(self):
        """Show control panel in main thread"""
        try:
            # Ensure window is not minimized
            if self.main_window.isMinimized():
                self.main_window.showNormal()

            # Show the window
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

            # Force focus
            self.main_window.setFocus()
        except Exception as e:
            print(f"Error in _show_control_panel_safe: {e}")
            import traceback
            traceback.print_exc()

    def _show_control_panel(self):
        self.main_window.showNormal()
        self.main_window.activateWindow()
        self.main_window.raise_()

    def cleanup(self):
        """Clean up system tray resources"""
        if self.tray_icon:
            self.tray_icon.stop()
        
        # Only join if we are not in the tray thread to avoid deadlock
        if self.tray_thread and self.tray_thread.is_alive() and threading.current_thread() != self.tray_thread:
            self.tray_thread.join(timeout=1.0)

    def quit_application(self):
        """Quit the application"""
        self.cleanup()
        QApplication.instance().quit()