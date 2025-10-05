"""
Widget Manager for Widgitron
Handles widget creation, management, and toggling
"""

from PyQt5.QtWidgets import QMessageBox


class WidgetManager:
    """Manages widget creation and lifecycle"""

    def __init__(self, main_window):
        self.main_window = main_window

    def auto_start_widgets(self):
        """Auto-start widgets configured in widgitron.json"""
        enabled_widgets = self.main_window.config.get('widgets', {}).get('enabled', [])

        for widget_config in enabled_widgets:
            if widget_config.get('auto_start', False):
                widget_name = widget_config['name']
                try:
                    if widget_name == 'gpu_monitor':
                        self._start_gpu_monitor()
                        # Update button state after auto-start
                        if hasattr(self.main_window, 'gpu_monitor_btn'):
                            self.main_window.gpu_monitor_btn.setObjectName("widgetButtonActive")
                            self.main_window.gpu_monitor_btn.setStyle(self.main_window.gpu_monitor_btn.style())
                    # Add other widgets here in the future
                    print(f"Auto-started {widget_name}")
                except Exception as e:
                    print(f"Failed to auto-start {widget_name}: {e}")

    def toggle_widget(self, widget_id, button):
        """Toggle widget on/off"""
        if widget_id == 'gpu_monitor':
            self.toggle_gpu_monitor()
        # Add other widgets here

        # Update button style
        if widget_id in self.main_window.active_widgets:
            button.setObjectName("widgetButtonActive")
        else:
            button.setObjectName("widgetButtonInactive")
        button.setStyle(button.style())  # Force style refresh

    def toggle_gpu_monitor(self):
        """Toggle GPU Monitor widget"""
        widget_name = 'gpu_monitor'

        if widget_name in self.main_window.active_widgets:
            # Close existing
            self.main_window.active_widgets[widget_name].close()
            del self.main_window.active_widgets[widget_name]
            if hasattr(self.main_window, 'gpu_monitor_btn'):
                self.main_window.gpu_monitor_btn.setObjectName("widgetButtonInactive")
                self.main_window.gpu_monitor_btn.setStyle(self.main_window.gpu_monitor_btn.style())
        else:
            # Create new
            try:
                self._start_gpu_monitor()
                if hasattr(self.main_window, 'gpu_monitor_btn'):
                    self.main_window.gpu_monitor_btn.setObjectName("widgetButtonActive")
                    self.main_window.gpu_monitor_btn.setStyle(self.main_window.gpu_monitor_btn.style())
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to launch GPU Monitor:\n{str(e)}")

    def _start_gpu_monitor(self):
        """Start GPU Monitor widget"""
        from widgets.gpu_monitor import GPUMonitor
        gpu_monitor = GPUMonitor()
        gpu_monitor.show()
        self.main_window.active_widgets['gpu_monitor'] = gpu_monitor

    def add_widget(self):
        """Add a new widget - placeholder for future implementation"""
        QMessageBox.information(self.main_window, "Add Widget", "Widget addition feature is under development.")