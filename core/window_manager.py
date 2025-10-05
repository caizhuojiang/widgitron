"""
Window Manager for Widgitron
Handles window management functionality like dragging, resizing, maximizing
"""

from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtWidgets import QApplication


class WindowManager:
    """Manages window behavior like dragging, resizing, and state changes"""

    def __init__(self, main_window):
        self.main_window = main_window

        # Window dragging
        self.dragging = False
        self.drag_position = QPoint()
        self.drag_threshold = 10  # Minimum pixels to move before starting drag
        self.pending_restore = False  # Flag for pending window restore
        self.updating_styles = False  # Flag to prevent recursive style updates

        # Window resizing
        self.resizing = False
        self.resize_edge = None
        self.resize_margin = 15  # Pixel margin for resize detection (increased from 10)

    def mouse_press_event(self, event):
        """Handle mouse press for window dragging and resizing"""
        if event.button() == Qt.LeftButton:
            # Don't resize if maximized
            if not self.main_window.isMaximized():
                # Check for resize
                edge = self.get_resize_edge(event.pos())
                if edge:
                    self.resizing = True
                    self.resize_edge = edge
                    self.drag_position = event.globalPos()
                    event.accept()
                    return

            # Check if click is in title bar area for dragging
            if event.pos().y() >= 10 and event.pos().y() < 60:
                # If maximized, prepare for restore on drag
                if self.main_window.isMaximized():
                    self.pending_restore = True
                    self.drag_position = event.globalPos()
                else:
                    self.dragging = True
                    self.drag_position = event.globalPos() - self.main_window.frameGeometry().topLeft()
                event.accept()

    def mouse_move_event(self, event):
        """Handle mouse move for window dragging, resizing, and cursor changes"""
        if self.resizing and event.buttons() == Qt.LeftButton:
            # Handle resizing - keep resize cursor during resize
            # Set appropriate resize cursor
            if self.resize_edge in ['top', 'bottom']:
                self.main_window.setCursor(Qt.SizeVerCursor)
            elif self.resize_edge in ['left', 'right']:
                self.main_window.setCursor(Qt.SizeHorCursor)
            elif self.resize_edge in ['top-left', 'bottom-right']:
                self.main_window.setCursor(Qt.SizeFDiagCursor)
            elif self.resize_edge in ['top-right', 'bottom-left']:
                self.main_window.setCursor(Qt.SizeBDiagCursor)
            
            delta = event.globalPos() - self.drag_position
            self.drag_position = event.globalPos()

            geo = self.main_window.geometry()

            if 'right' in self.resize_edge:
                geo.setRight(geo.right() + delta.x())
            if 'left' in self.resize_edge:
                geo.setLeft(geo.left() + delta.x())
            if 'bottom' in self.resize_edge:
                geo.setBottom(geo.bottom() + delta.y())
            if 'top' in self.resize_edge:
                geo.setTop(geo.top() + delta.y())

            self.main_window.setGeometry(geo)
            event.accept()
        elif self.dragging and event.buttons() == Qt.LeftButton:
            # Handle dragging - only move if not resizing
            if not self.resizing:
                new_pos = event.globalPos() - self.drag_position
                # Ensure position is valid (not negative and within screen bounds)
                screen = QApplication.primaryScreen().availableGeometry()
                new_pos.setX(max(0, min(new_pos.x(), screen.width() - self.main_window.width())))
                new_pos.setY(max(0, min(new_pos.y(), screen.height() - self.main_window.height())))
                self.main_window.move(new_pos)
            event.accept()
        elif self.pending_restore and event.buttons() == Qt.LeftButton:
            # Check if drag distance exceeds threshold
            drag_distance = (event.globalPos() - self.drag_position).manhattanLength()
            if drag_distance > self.drag_threshold:
                # Restore window and start dragging
                self.main_window.showNormal()
                # Process events to ensure window state change is complete
                QApplication.processEvents()
                # Update button text and tooltip
                self.main_window.max_btn.setText("□")
                self.main_window.max_btn.setToolTip("Maximize")

                # Prevent recursive style updates during restore
                if not self.updating_styles:
                    self.updating_styles = True
                    # Restore margins for shadow
                    container = self.main_window.centralWidget()
                    container.layout().setContentsMargins(10, 10, 10, 10)
                    # Restore rounded corners
                    self.main_window.content_frame.setObjectName("contentFrame")
                    self.main_window.title_bar.setObjectName("titleBar")
                    self.main_window.sidebar.setObjectName("sidebar")
                    # Force style refresh
                    self.main_window.content_frame.setStyle(self.main_window.content_frame.style())
                    self.main_window.title_bar.setStyle(self.main_window.title_bar.style())
                    self.main_window.sidebar.setStyle(self.main_window.sidebar.style())
                    # Update container and force repaint after a short delay
                    container.update()
                    QTimer.singleShot(10, lambda: container.repaint())
                    self.updating_styles = False

                # Start dragging
                self.dragging = True
                self.pending_restore = False
                # Ensure window is properly positioned before dragging
                self.drag_position = event.globalPos() - self.main_window.frameGeometry().topLeft()
                # Validate position
                if self.drag_position.x() < 0 or self.drag_position.y() < 0:
                    self.drag_position = QPoint(max(0, self.drag_position.x()), max(0, self.drag_position.y()))
                event.accept()
        else:
            # Update cursor based on position
            if not self.main_window.isMaximized() and not self.dragging:
                edge = self.get_resize_edge(event.pos())
                if edge:
                    if edge in ['top', 'bottom']:
                        self.main_window.setCursor(Qt.SizeVerCursor)
                    elif edge in ['left', 'right']:
                        self.main_window.setCursor(Qt.SizeHorCursor)
                    elif edge in ['top-left', 'bottom-right']:
                        self.main_window.setCursor(Qt.SizeFDiagCursor)
                    elif edge in ['top-right', 'bottom-left']:
                        self.main_window.setCursor(Qt.SizeBDiagCursor)
                else:
                    self.main_window.setCursor(Qt.ArrowCursor)
            else:
                # When maximized or dragging, always use arrow cursor
                self.main_window.setCursor(Qt.ArrowCursor)

    def mouse_release_event(self, event):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.resizing = False
            self.resize_edge = None
            self.pending_restore = False  # Reset pending restore flag
            # Reset cursor to arrow
            self.main_window.setCursor(Qt.ArrowCursor)

    def mouse_double_click_event(self, event):
        """Handle mouse double click on title bar"""
        if event.button() == Qt.LeftButton:
            # Check if double click is in title bar area
            if event.pos().y() >= 10 and event.pos().y() < 60:
                self.toggle_maximize()
                event.accept()
                return

        # Call parent implementation for other cases
        super(type(self.main_window), self.main_window).mouseDoubleClickEvent(event)

    def get_resize_edge(self, pos):
        """Determine which edge of the window is under the mouse"""
        rect = self.main_window.rect()
        margin = self.resize_margin

        x = pos.x()
        y = pos.y()

        # Check edges directly (no shadow margin adjustment needed since mouse events are on main window)
        on_left = x <= margin
        on_right = x >= rect.width() - margin
        on_top = y <= margin
        on_bottom = y >= rect.height() - margin

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

    def update_cursor_on_enter(self, pos):
        """Update cursor when mouse enters the window"""
        if not self.main_window.isMaximized():
            edge = self.get_resize_edge(pos)
            if edge:
                if edge in ['top', 'bottom']:
                    self.main_window.setCursor(Qt.SizeVerCursor)
                elif edge in ['left', 'right']:
                    self.main_window.setCursor(Qt.SizeHorCursor)
                elif edge in ['top-left', 'bottom-right']:
                    self.main_window.setCursor(Qt.SizeFDiagCursor)
                elif edge in ['top-right', 'bottom-left']:
                    self.main_window.setCursor(Qt.SizeBDiagCursor)
            else:
                self.main_window.setCursor(Qt.ArrowCursor)
        else:
            self.main_window.setCursor(Qt.ArrowCursor)

    def toggle_maximize(self):
        """Toggle between maximized and normal window state"""
        if self.main_window.isMaximized():
            self.main_window.showNormal()
            # Process events to ensure window state change is complete
            QApplication.processEvents()
            self.main_window.max_btn.setText("□")
            self.main_window.max_btn.setToolTip("Maximize")
            # Restore margins for shadow
            container = self.main_window.centralWidget()
            container.layout().setContentsMargins(10, 10, 10, 10)
            # Restore rounded corners
            self.main_window.content_frame.setObjectName("contentFrame")
            self.main_window.title_bar.setObjectName("titleBar")
            self.main_window.sidebar.setObjectName("sidebar")
            # Force style refresh immediately and with delay
            self.main_window.content_frame.setStyle(self.main_window.content_frame.style())
            self.main_window.title_bar.setStyle(self.main_window.title_bar.style())
            self.main_window.sidebar.setStyle(self.main_window.sidebar.style())
            # Force repaint to ensure visual update
            self.main_window.content_frame.repaint()
            self.main_window.title_bar.repaint()
            self.main_window.sidebar.repaint()
            # Force container update to refresh shadow effect
            container.update()
            # Additional delayed refresh for safety
            QTimer.singleShot(10, lambda: self.main_window.content_frame.setStyle(self.main_window.content_frame.style()))
            QTimer.singleShot(10, lambda: self.main_window.title_bar.setStyle(self.main_window.title_bar.style()))
            QTimer.singleShot(10, lambda: container.repaint())
        else:
            self.main_window.showMaximized()
            self.main_window.max_btn.setText("❐")
            self.main_window.max_btn.setToolTip("Restore")
            # Remove margins when maximized to eliminate transparent border
            container = self.main_window.centralWidget()
            container.layout().setContentsMargins(0, 0, 0, 0)
            # Remove rounded corners when maximized
            self.main_window.content_frame.setObjectName("contentFrameMaximized")
            self.main_window.title_bar.setObjectName("titleBarMaximized")
            self.main_window.sidebar.setObjectName("sidebarMaximized")
            # Force style refresh
            self.main_window.content_frame.setStyle(self.main_window.content_frame.style())
            self.main_window.title_bar.setStyle(self.main_window.title_bar.style())
            self.main_window.sidebar.setStyle(self.main_window.sidebar.style())