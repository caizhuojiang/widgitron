"""
Widget Manager for Widgitron
Handles widget creation, management, and toggling
"""

from PyQt5.QtWidgets import QMessageBox


class WidgetManager:
    """Manages widget creation and lifecycle"""

    def __init__(self, main_window):
        self.main_window = main_window
        # Widget class mapping for dynamic instantiation
        self.widget_classes = {
            'gpu_monitor': ('widgets.gpu_monitor', 'GPUMonitor'),
            'paper_deadline': ('widgets.paper_deadline', 'PaperDeadline'),
        }

    def auto_start_widgets(self):
        """Auto-start widgets configured in their individual config files"""
        for widget_id, (module_name, class_name) in self.widget_classes.items():
            try:
                # Import the widget module
                module = __import__(module_name, fromlist=[class_name])
                widget_class = getattr(module, class_name)
                
                # Check if widget should auto-start
                config_path = f'configs/{widget_id}.json'
                try:
                    import json
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    if config.get('auto_start', True):
                        self._start_widget(widget_id)
                        # Update button state after auto-start
                        button_attr = f"{widget_id}_btn"
                        if hasattr(self.main_window, button_attr):
                            getattr(self.main_window, button_attr).setObjectName("widgetButtonActive")
                            getattr(self.main_window, button_attr).setStyle(getattr(self.main_window, button_attr).style())
                        print(f"Auto-started {widget_id}")
                except FileNotFoundError:
                    # If config doesn't exist, default to auto-start
                    self._start_widget(widget_id)
                    print(f"Auto-started {widget_id} (no config found)")
                except Exception as e:
                    print(f"Failed to check auto-start for {widget_id}: {e}")
            except Exception as e:
                print(f"Failed to auto-start {widget_id}: {e}")

    def toggle_widget(self, widget_id, button):
        """Toggle widget on/off"""
        if widget_id in self.main_window.active_widgets:
            # Close existing widget
            self.main_window.active_widgets[widget_id].close()
            del self.main_window.active_widgets[widget_id]
        else:
            # Create new widget
            try:
                self._start_widget(widget_id)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to launch {widget_id.replace('_', ' ').title()}:\n{str(e)}")
                return

        # Update button style
        if widget_id in self.main_window.active_widgets:
            button.setObjectName("widgetButtonActive")
        else:
            button.setObjectName("widgetButtonInactive")
        button.setStyle(button.style())  # Force style refresh

    def _start_widget(self, widget_id):
        """Start a widget by ID"""
        if widget_id not in self.widget_classes:
            raise ValueError(f"Unknown widget: {widget_id}")

        module_name, class_name = self.widget_classes[widget_id]
        module = __import__(module_name, fromlist=[class_name])
        widget_class = getattr(module, class_name)

        widget = widget_class()
        widget.show()
        self.main_window.active_widgets[widget_id] = widget

    def add_widget(self):
        """Add a new widget - placeholder for future implementation"""
        QMessageBox.information(self.main_window, "Add Widget", "Widget addition feature is under development.")